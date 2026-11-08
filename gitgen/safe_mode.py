"""안전 모드: AI API로 보내기 전에 diff에서 민감정보를 가리고 전송량을 제한한다.

정책 (기본값)
1. 민감 파일 제외: .env, .env.* (.env.example 제외), *.pem, *.key, *.p12, *.pfx,
   id_rsa / id_ed25519 등 SSH 키, credentials* 파일은 diff 내용을 아예 보내지 않는다.
2. 패턴 마스킹: API Key/토큰/비밀번호 대입문/이메일/전화번호/주민등록번호 등을
   정규표현식으로 찾아 `[MASKED:<규칙>]`로 바꾼다. --mask-pattern 으로 규칙을 추가할 수 있다.
3. 전송량 제한: 최대 파일 수(기본 10개), 최대 줄 수(기본 200줄)까지만 보낸다.
"""

from __future__ import annotations

import fnmatch
import re
from collections import Counter
from dataclasses import dataclass, field

DEFAULT_MAX_FILES = 10
DEFAULT_MAX_LINES = 200

SENSITIVE_FILE_PATTERNS = [
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "id_rsa*",
    "id_dsa*",
    "id_ecdsa*",
    "id_ed25519*",
    "credentials*",
    "*.keystore",
]
SENSITIVE_FILE_ALLOW = [".env.example", ".env.sample", ".env.template"]

# (이름, 정규식). 순서가 중요하다: 구체적인 규칙이 먼저 와야 일반 규칙에 먹히지 않는다.
DEFAULT_RULES: list[tuple[str, str]] = [
    ("private_key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    ("google_api_key", r"AIza[0-9A-Za-z_\-]{35}"),
    ("openai_anthropic_key", r"sk-(?:ant-|proj-)?[A-Za-z0-9_\-]{20,}"),
    ("github_token", r"(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})"),
    ("aws_access_key", r"(?:AKIA|ASIA)[0-9A-Z]{16}"),
    ("slack_token", r"xox[abprs]-[A-Za-z0-9\-]{10,}"),
    ("jwt", r"eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"),
    # 비밀값 대입문. 키 이름은 남기고 값만 가린다.
    # 코드의 `max_tokens = args.max_tokens` 같은 일반 변수까지 가리지 않도록
    # (1) 따옴표로 감싼 문자열 리터럴, (2) .env 스타일 대문자 KEY=값 두 경우만 본다.
    (
        "secret_literal",
        r"(?i)(?P<keep>\b[\w.\-]*(?:api[_\-]?key|secret|token|passw(?:or)?d|pwd|access[_\-]?key)[\w.\-]*"
        r"[\"']?\s*[:=]\s*(?P<q>[\"']))(?P<value>(?!\[MASKED)[^\"'\s]{6,})(?=(?P=q))",
    ),
    (
        "env_secret",
        r"(?m)(?P<keep>^[+\- ]?\s*(?:export\s+)?[A-Z0-9_]*(?:API_?KEY|SECRET|TOKEN|PASSWORD|PASSWD|PWD|ACCESS_?KEY)"
        r"[A-Z0-9_]*=)(?P<value>(?!\[MASKED)[^\s\"']{6,})",
    ),
    ("email", r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
    ("kr_rrn", r"\b\d{6}-[1-4]\d{6}\b"),
    ("kr_phone", r"\b01[016789]-?\d{3,4}-?\d{4}\b"),
]


@dataclass
class SafeModeConfig:
    max_files: int = DEFAULT_MAX_FILES
    max_lines: int = DEFAULT_MAX_LINES
    extra_patterns: list[str] = field(default_factory=list)


@dataclass
class SafeModeReport:
    masked: Counter = field(default_factory=Counter)
    excluded_files: list[str] = field(default_factory=list)
    total_files: int = 0
    sent_files: int = 0
    total_lines: int = 0
    sent_lines: int = 0

    def summary(self) -> str:
        masked = ", ".join(f"{k} {v}" for k, v in self.masked.items()) or "없음"
        parts = [
            f"마스킹 {sum(self.masked.values())}건({masked})",
            f"민감 파일 제외 {len(self.excluded_files)}개",
            f"전송 파일 {self.sent_files}/{self.total_files}",
            f"전송 줄 {self.sent_lines}/{self.total_lines}",
        ]
        return ", ".join(parts)


def split_diff_by_file(diff: str) -> list[tuple[str, str]]:
    """diff 텍스트를 (파일 경로, 해당 파일 diff) 목록으로 나눈다."""
    chunks: list[tuple[str, str]] = []
    current: list[str] = []
    current_path = ""
    for line in diff.splitlines(keepends=True):
        if line.startswith("diff --git "):
            if current:
                chunks.append((current_path, "".join(current)))
            current = [line]
            current_path = _path_from_header(line)
        else:
            current.append(line)
    if current:
        chunks.append((current_path, "".join(current)))
    return chunks


def _path_from_header(header: str) -> str:
    # "diff --git a/foo/bar.py b/foo/bar.py" -> "foo/bar.py"
    rest = header[len("diff --git "):].strip()
    if " b/" in rest:
        return rest.rsplit(" b/", 1)[1]
    return rest.split(" ", 1)[-1]


def is_sensitive_file(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    if name in SENSITIVE_FILE_ALLOW:
        return False
    return any(fnmatch.fnmatch(name, pat) for pat in SENSITIVE_FILE_PATTERNS)


def compile_rules(extra_patterns: list[str]) -> list[tuple[str, re.Pattern]]:
    rules = [(name, re.compile(pat)) for name, pat in DEFAULT_RULES]
    for i, pat in enumerate(extra_patterns, start=1):
        try:
            rules.append((f"custom_{i}", re.compile(pat)))
        except re.error as exc:
            raise ValueError(f"--mask-pattern 정규식 오류 ({pat!r}): {exc}") from exc
    return rules


def mask_text(text: str, rules: list[tuple[str, re.Pattern]], counter: Counter) -> str:
    for name, rx in rules:
        def repl(m: re.Match, _name: str = name) -> str:
            counter[_name] += 1
            if "keep" in rx.groupindex:
                return f"{m.group('keep')}[MASKED:{_name}]"
            return f"[MASKED:{_name}]"

        text = rx.sub(repl, text)
    return text


def apply_safe_mode(diff: str, config: SafeModeConfig) -> tuple[str, SafeModeReport]:
    rules = compile_rules(config.extra_patterns)
    report = SafeModeReport()
    chunks = split_diff_by_file(diff)
    report.total_files = len(chunks)
    report.total_lines = len(diff.splitlines())

    out: list[str] = []
    lines_left = config.max_lines
    for path, chunk in chunks:
        if report.sent_files >= config.max_files or lines_left <= 0:
            break
        if is_sensitive_file(path):
            report.excluded_files.append(path)
            chunk = f"diff --git a/{path} b/{path}\n(safe-mode: 민감 파일로 판단되어 내용을 전송하지 않음)\n"
        else:
            chunk = mask_text(chunk, rules, report.masked)

        lines = chunk.splitlines(keepends=True)
        sent = min(len(lines), lines_left)
        out.extend(lines[:sent])
        if sent < len(lines):
            out.append(f"... (safe-mode: 줄 수 제한으로 이 파일의 {len(lines) - sent}줄 생략)\n")
        lines_left -= sent
        report.sent_files += 1
        report.sent_lines += sent

    skipped = report.total_files - report.sent_files
    if skipped > 0:
        out.append(f"... (safe-mode: 파일/줄 수 제한으로 {skipped}개 파일 생략)\n")
    return "".join(out), report
