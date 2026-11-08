"""Gemini generateContent REST API 클라이언트.

SDK 없이 표준 라이브러리(urllib)로 HTTP 요청을 직접 만든다.
요청 구성 → 전송 → 응답 파싱 → 오류 분류가 이 파일 하나에 모여 있다.
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass

API_BASE = "https://generativelanguage.googleapis.com/v1beta"
API_KEY_ENV_VARS = ("GEMINI_API_KEY", "AI_API_KEY")


class AIError(Exception):
    """AI API 호출 실패. 메시지에 원인과 대응 방법을 담는다."""


@dataclass
class GenerationParams:
    model: str
    temperature: float
    max_tokens: int
    timeout: float = 60.0


@dataclass
class GenerationResult:
    text: str
    finish_reason: str
    prompt_tokens: int = 0
    output_tokens: int = 0

    @property
    def truncated(self) -> bool:
        return self.finish_reason == "MAX_TOKENS"


class GeminiClient:
    def __init__(self, api_key: str, params: GenerationParams):
        self.api_key = api_key
        self.params = params
        self.call_count = 0

    def build_request_body(self, system_prompt: str, user_prompt: str) -> dict:
        generation_config: dict = {
            "temperature": self.params.temperature,
            "maxOutputTokens": self.params.max_tokens,
        }
        # Gemini flash 계열은 기본으로 '생각(thinking)' 토큰을 수백 개 쓰는데, 이것도 maxOutputTokens에서 빠진다.
        # 커밋 메시지 정도에는 필요 없고 비용과 max_tokens 실험 결과를 흐리므로 끈다.
        # (pro 계열은 thinking을 끌 수 없어 그대로 둔다)
        if "flash" in self.params.model:
            generation_config["thinkingConfig"] = {"thinkingBudget": 0}
        return {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": generation_config,
        }

    def generate(self, system_prompt: str, user_prompt: str) -> GenerationResult:
        url = f"{API_BASE}/models/{self.params.model}:generateContent"
        body = json.dumps(self.build_request_body(system_prompt, user_prompt)).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                # 키를 URL(?key=)이 아니라 헤더로 보내 로그/프록시에 남지 않게 한다.
                "x-goog-api-key": self.api_key,
            },
        )
        self.call_count += 1
        try:
            with urllib.request.urlopen(req, timeout=self.params.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise AIError(describe_http_error(exc.code, _read_error_body(exc), self.params.model)) from exc
        except (socket.timeout, TimeoutError) as exc:
            raise AIError(
                f"요청 시간 초과({self.params.timeout:g}초). 네트워크 상태를 확인하거나 --timeout 값을 늘리세요."
            ) from exc
        except urllib.error.URLError as exc:
            raise AIError(f"네트워크 오류: {exc.reason}. 인터넷 연결을 확인하세요.") from exc
        except json.JSONDecodeError as exc:
            raise AIError("API 응답을 JSON으로 해석할 수 없습니다.") from exc
        return parse_response(payload)


def _read_error_body(exc: urllib.error.HTTPError) -> dict:
    try:
        return json.loads(exc.read().decode("utf-8"))
    except Exception:
        return {}


def describe_http_error(status: int, body: dict, model: str) -> str:
    err = body.get("error", {}) if isinstance(body, dict) else {}
    detail = err.get("message", "").strip()
    reasons = json.dumps(err.get("details", []))

    if "API_KEY_INVALID" in reasons or "API key not valid" in detail or status in (401, 403):
        cause = "인증 실패: API Key가 올바르지 않거나 권한이 없습니다. GEMINI_API_KEY 값을 확인하세요."
    elif status == 404:
        cause = f"모델을 찾을 수 없습니다: '{model}'. --model 값을 확인하세요."
    elif status == 429:
        cause = "요청 한도 초과(Rate limit/Quota). 잠시 후 다시 시도하세요."
    elif status == 400:
        cause = "잘못된 요청입니다. 모델 이름이나 --temperature, --max-tokens 값을 확인하세요."
    elif status >= 500:
        cause = "AI 서버 오류입니다. 잠시 후 다시 시도하세요."
    else:
        cause = "API 요청이 실패했습니다."
    return f"{cause} (HTTP {status}{': ' + detail if detail else ''})"


def parse_response(payload: dict) -> GenerationResult:
    candidates = payload.get("candidates") or []
    if not candidates:
        block = (payload.get("promptFeedback") or {}).get("blockReason")
        if block:
            raise AIError(f"요청이 안전 정책으로 차단되었습니다. (blockReason: {block})")
        raise AIError("API 응답에 생성 결과(candidates)가 없습니다.")

    cand = candidates[0]
    finish = cand.get("finishReason", "")
    parts = (cand.get("content") or {}).get("parts") or []
    # thought=True 인 파트는 모델의 생각 과정이므로 결과에서 뺀다.
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))

    if finish in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII"):
        raise AIError(f"응답이 안전 정책으로 차단되었습니다. (finishReason: {finish})")
    if not text.strip():
        if finish == "MAX_TOKENS":
            raise AIError(
                "max_tokens 한도에 걸려 빈 응답이 왔습니다. --max-tokens 값을 늘리세요. "
                "(thinking 모델은 생각 토큰도 이 한도에 포함됩니다.)"
            )
        raise AIError(f"빈 응답을 받았습니다. (finishReason: {finish or '없음'})")

    usage = payload.get("usageMetadata") or {}
    return GenerationResult(
        text=text,
        finish_reason=finish,
        prompt_tokens=usage.get("promptTokenCount", 0),
        output_tokens=usage.get("candidatesTokenCount", 0),
    )
