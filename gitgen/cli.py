"""CLI 진입점: 인자 해석 → Git 수집 → (안전 모드) → 프롬프트 → AI 호출 → 검증/후처리 → 출력.

로그([INFO], [WARN] 등)는 stderr로, 생성 결과는 stdout으로 내보낸다.
그래서 `python main.py commit --raw 2>/dev/null > msg.txt` 처럼 결과만 따로 받을 수 있다.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Callable

from . import prompts
from .ai_client import API_KEY_ENV_VARS, AIError, GeminiClient, GenerationParams
from .formatter import (
    COMMIT_BODY_MAX_BULLETS,
    COMMIT_BODY_MAX_FILES,
    COMMIT_TITLE_MAX,
    COMMIT_TITLE_RECOMMENDED,
    PR_TITLE_MAX,
    count_file_mentions,
    drop_truncated_tail,
    finalize_commit,
    finalize_pr,
    parse_commit,
    parse_pr,
)
from .git_collector import Changes, GitError, collect_changes, ensure_repo_root
from .safe_mode import DEFAULT_MAX_FILES, DEFAULT_MAX_LINES, SafeModeConfig, apply_safe_mode

DEFAULT_MODEL = "gemini-3.8-flash"
DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = 1024
DEFAULT_TIMEOUT = 60.0
# 안전 모드가 꺼져 있어도 이보다 긴 diff는 잘라서 보낸다 (비용/한도 보호).
HARD_DIFF_CHAR_LIMIT = 60_000
MAX_AI_CALLS = 2  # 최초 1회 + 형식 오류 시 재생성 1회
FILE_LIST_LIMIT = 20  # 로그에 보여 줄 변경 파일 수

TOOL_DIR = Path(__file__).resolve().parent.parent


def log(level: str, msg: str) -> None:
    print(f"[{level}] {msg}", file=sys.stderr)


def load_dotenv(path: Path) -> None:
    """도구 폴더의 .env 를 읽어 아직 설정되지 않은 환경변수만 채운다."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.removeprefix("export ").strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


def get_api_key() -> str | None:
    for name in API_KEY_ENV_VARS:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


def _positive_int(value: str) -> int:
    n = int(value)
    if n <= 0:
        raise argparse.ArgumentTypeError("1 이상의 정수여야 합니다.")
    return n


def _temperature(value: str) -> float:
    t = float(value)
    if not 0.0 <= t <= 2.0:
        raise argparse.ArgumentTypeError("0.0 ~ 2.0 사이여야 합니다.")
    return t


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    ai = common.add_argument_group("AI API 파라미터")
    ai.add_argument("--model", default=DEFAULT_MODEL, help=f"Gemini 모델 이름 (기본: {DEFAULT_MODEL})")
    ai.add_argument(
        "--temperature", type=_temperature, default=DEFAULT_TEMPERATURE,
        help=f"0.0~2.0. 낮을수록 일관적, 높을수록 다양한 표현 (기본: {DEFAULT_TEMPERATURE})",
    )
    ai.add_argument(
        "--max-tokens", type=_positive_int, default=DEFAULT_MAX_TOKENS,
        help=f"최대 출력 토큰 수 (기본: {DEFAULT_MAX_TOKENS})",
    )
    ai.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="요청 제한 시간(초)")

    ctx = common.add_argument_group("입력/출력")
    ctx.add_argument("--context", help="AI에 함께 전달할 변경 이유 (예: --context \"로그인 실패 버그 수정\")")
    ctx.add_argument("--raw", action="store_true", help="구분선 없이 결과만 출력 (git commit -F 등에 사용)")
    ctx.add_argument("--dry-run", action="store_true", help="AI를 호출하지 않고 전송될 프롬프트만 출력")

    safe = common.add_argument_group("안전 모드")
    safe.add_argument("--safe-mode", action="store_true", help="민감정보 마스킹 + 전송량 제한 후 전송")
    safe.add_argument(
        "--max-files", type=_positive_int, default=None,
        help=f"안전 모드에서 보낼 최대 파일 수 (기본: {DEFAULT_MAX_FILES})",
    )
    safe.add_argument(
        "--max-lines", type=_positive_int, default=None,
        help=f"안전 모드에서 보낼 최대 diff 줄 수 (기본: {DEFAULT_MAX_LINES})",
    )
    safe.add_argument(
        "--mask-pattern", action="append", default=[], metavar="REGEX",
        help="추가 마스킹 정규식 (여러 번 지정 가능)",
    )

    parser = argparse.ArgumentParser(
        prog="python main.py",
        description="Git 변경 사항으로 커밋 메시지와 PR 초안을 생성합니다.",
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="{commit,pr}")
    sub.add_parser("commit", parents=[common], help="커밋 메시지 생성")
    pr = sub.add_parser("pr", parents=[common], help="PR 제목/본문 초안 생성")
    pr.add_argument(
        "--base", metavar="BRANCH",
        help="이미 커밋한 브랜치 변경을 <BRANCH>...HEAD 기준으로 요약 (예: --base main)",
    )
    return parser


def prepare_diff(changes: Changes, args: argparse.Namespace) -> str:
    diff = changes.diff
    limits_given = args.max_files is not None or args.max_lines is not None or args.mask_pattern
    if limits_given and not args.safe_mode:
        log("INFO", "--max-files/--max-lines/--mask-pattern 옵션이 있어 안전 모드를 켭니다.")
        args.safe_mode = True

    if args.safe_mode:
        config = SafeModeConfig(
            max_files=args.max_files or DEFAULT_MAX_FILES,
            max_lines=args.max_lines or DEFAULT_MAX_LINES,
            extra_patterns=args.mask_pattern,
        )
        diff, report = apply_safe_mode(diff, config)
        log("SAFE", report.summary())
        if report.excluded_files:
            log("SAFE", "내용 제외 파일: " + ", ".join(report.excluded_files))

    if len(diff) > HARD_DIFF_CHAR_LIMIT:
        log("WARN", f"diff가 {len(diff):,}자로 커서 앞 {HARD_DIFF_CHAR_LIMIT:,}자만 보냅니다. --safe-mode 사용을 권장합니다.")
        diff = diff[:HARD_DIFF_CHAR_LIMIT] + "\n... (diff가 길어 이후 생략)\n"
    return diff


def generate_with_retry(
    client: GeminiClient,
    system_prompt: str,
    user_prompt: str,
    parse: Callable[[str], tuple[object, list[str]]],
):
    """1회 생성 → 파싱 문제가 있으면 문제점을 알려주고 1회만 재생성한다."""
    log("INFO", f"AI API 요청 중... (model={client.params.model}, "
                f"temperature={client.params.temperature}, max_tokens={client.params.max_tokens})")
    result = client.generate(system_prompt, user_prompt)
    _log_usage(result)
    parsed, problems = parse(result.text)

    if problems and client.call_count < MAX_AI_CALLS:
        log("WARN", "형식 문제 발견 → 1회 재생성합니다: " + " / ".join(problems))
        retry_prompt = prompts.build_retry_prompt(user_prompt, result.text, problems)
        result = client.generate(system_prompt, retry_prompt)
        _log_usage(result)
        parsed, problems = parse(result.text)

    if result.truncated:
        note = drop_truncated_tail(parsed)
        if note:
            log("FIX", note)
    if problems:
        log("WARN", "재생성 후에도 남은 문제는 후처리로 보완합니다: " + " / ".join(problems))
    return parsed


def _log_usage(result) -> None:
    if result.truncated:
        log("WARN", "max_tokens 한도에 도달해 응답이 잘렸습니다. 필요하면 --max-tokens 값을 늘리세요.")
    if result.prompt_tokens or result.output_tokens:
        log("INFO", f"토큰 사용량: 입력 {result.prompt_tokens}, 출력 {result.output_tokens}")


def print_block(header: str, body: str) -> None:
    print(f"--- {header} ---")
    print(body)


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_dotenv(TOOL_DIR / ".env")
    cwd = Path.cwd()

    api_key = get_api_key()
    if not api_key and not args.dry_run:
        log("ERROR", f"{API_KEY_ENV_VARS[0]} 환경변수가 설정되지 않았습니다.")
        print(f'        예) export {API_KEY_ENV_VARS[0]}="YOUR_KEY"', file=sys.stderr)
        return 1

    try:
        ensure_repo_root(cwd)
        changes = collect_changes(cwd, base=getattr(args, "base", None))
    except GitError as exc:
        log("ERROR", str(exc))
        return 1

    if changes.is_empty:
        target = "커밋 메시지를" if args.command == "commit" else "PR 초안을"
        log("INFO", f"변경 사항이 없습니다. {target} 생성하지 않고 종료합니다.")
        if args.command == "pr" and not getattr(args, "base", None):
            log("INFO", "이미 커밋한 브랜치 변경으로 PR 초안을 만들려면 --base main 처럼 기준 브랜치를 지정하세요.")
        return 0

    if args.command == "pr":
        log("INFO", f"현재 브랜치: {changes.branch}")
    scope = {"staged": "staged 변경 기준", "working-tree": "작업 트리 전체 기준"}.get(
        changes.mode, f"{changes.mode.split(':', 1)[-1]}...HEAD 기준"
    )
    log("INFO", f"Git status 수집 완료: {len(changes.files)}개 파일 변경 감지 ({scope})")
    for f in changes.files[:FILE_LIST_LIMIT]:
        print(f"         {f.status:<2} {f.path}", file=sys.stderr)
    if len(changes.files) > FILE_LIST_LIMIT:
        print(f"         ... 외 {len(changes.files) - FILE_LIST_LIMIT}개", file=sys.stderr)
    log("INFO", f"Git diff 수집 완료: {changes.diff_line_count}줄")

    try:
        diff_text = prepare_diff(changes, args)
    except ValueError as exc:
        log("ERROR", str(exc))
        return 1

    system_prompt = prompts.COMMIT_SYSTEM if args.command == "commit" else prompts.PR_SYSTEM
    user_prompt = prompts.build_user_prompt(changes, diff_text, args.context)

    if args.dry_run:
        log("INFO", "--dry-run: AI API를 호출하지 않습니다. 전송될 프롬프트를 출력합니다.")
        print_block("System Prompt", system_prompt)
        print_block("User Prompt", user_prompt)
        return 0

    client = GeminiClient(
        api_key,
        GenerationParams(
            model=args.model,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            timeout=args.timeout,
        ),
    )

    try:
        if args.command == "commit":
            parsed = generate_with_retry(client, system_prompt, user_prompt, parse_commit)
            final, notes = finalize_commit(parsed)
        else:
            parsed = generate_with_retry(client, system_prompt, user_prompt, parse_pr)
            final, notes = finalize_pr(parsed)
    except AIError as exc:
        log("ERROR", f"AI API 호출 실패 - {exc}")
        log("INFO", f"AI API 호출 횟수: {client.call_count}회")
        return 1

    for note in notes:
        log("FIX", note)
    log("INFO", f"AI API 호출 횟수: {client.call_count}회")

    if args.command == "commit":
        mentioned = count_file_mentions(final.body, [f.path for f in changes.files])
        log("CHECK", f"커밋 제목 {len(final.title)}자 (권장 {COMMIT_TITLE_RECOMMENDED}자 / 최대 {COMMIT_TITLE_MAX}자), "
                     f"본문 불릿 {len(final.body)}개 (최대 {COMMIT_BODY_MAX_BULLETS}개), "
                     f"언급 파일 {mentioned}개 (권장 1~{COMMIT_BODY_MAX_FILES}개)")
        log("DONE", "커밋 메시지 생성 완료")
        if args.raw:
            print(final.render())
        else:
            print()
            print_block("Commit Message", final.render())
            print("-" * 22)
    else:
        counts = ", ".join(f"{k} {len(v)}개" for k, v in final.sections.items())
        log("CHECK", f"PR 제목 {len(final.title)}자 (최대 {PR_TITLE_MAX}자), 섹션 불릿: {counts}")
        log("DONE", "PR 초안 생성 완료")
        if args.raw:
            print(final.title)
            print()
            print(final.render_body())
        else:
            print()
            print_block("PR Title", final.title)
            print()
            print_block("PR Body", final.render_body())
            print("-" * 22)
    return 0
