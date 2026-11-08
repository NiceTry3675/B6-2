"""프롬프트 구성.

AI에게 줄 '역할 + 출력 규칙(system)'과 '변경 맥락(user)'을 분리해서 만든다.
출력 규칙의 숫자(길이 제한 등)는 formatter.py의 검증 규칙과 같은 상수를 쓴다.
"""

from __future__ import annotations

from .formatter import (
    COMMIT_BODY_MAX_BULLETS,
    COMMIT_BODY_MAX_FILES,
    COMMIT_TITLE_MAX,
    COMMIT_TITLE_RECOMMENDED,
    PR_SECTIONS,
    PR_TITLE_MAX,
)
from .git_collector import Changes

COMMIT_TYPES = "feat, fix, docs, refactor, test, chore, style, perf, build, ci"

COMMIT_SYSTEM = f"""너는 코드 변경을 읽고 Git 커밋 메시지를 작성하는 시니어 개발자다.

[출력 형식]
<type>: <제목>

- <핵심 변경 1>
- <핵심 변경 2>

[규칙]
- 첫 줄은 Conventional Commits 형식의 제목 1줄이다. type은 {COMMIT_TYPES} 중 하나.
- 제목은 한국어로, {COMMIT_TITLE_RECOMMENDED}자 이내(절대 {COMMIT_TITLE_MAX}자 초과 금지)로 쓰고 마침표를 찍지 않는다.
- 제목은 "~ 추가", "~ 수정"처럼 명사형으로 끝낸다.
- 제목 다음 빈 줄 1개, 그 아래 본문은 "- "로 시작하는 불릿 1~{COMMIT_BODY_MAX_BULLETS}개다. 핵심 변경만 중요한 순서로 쓴다.
- 본문 전체에서 변경된 파일 또는 모듈 이름은 대표적인 것 1~{COMMIT_BODY_MAX_FILES}개만 언급한다. 파일을 나열하지 않는다.
- 여러 변경이 섞여 있으면 가장 중요한 변경을 제목으로, 그다음 중요한 변경을 불릿으로 쓴다.
- diff에 없는 내용은 지어내지 않는다. `[MASKED:...]`로 가려진 값은 추측하지 않는다.
- 커밋 메시지 외의 설명, 인사말, 코드 블록(```)은 출력하지 않는다."""

PR_SYSTEM = f"""너는 코드 변경을 읽고 Pull Request 제목과 본문 초안을 작성하는 시니어 개발자다.

[출력 형식] 아래 구조를 정확히 지킨다.
TITLE: <type>: <PR 제목>

## Why
- <변경 배경/문제>

## What
- <핵심 변경 사항>

## How to Test
- <리뷰어가 따라 할 수 있는 확인 방법>

[규칙]
- 첫 줄은 "TITLE: "로 시작하고, 제목은 한국어로 {PR_TITLE_MAX}자 이내다. type은 {COMMIT_TYPES} 중 하나.
- 섹션 헤더는 {", ".join(f"'## {s}'" for s in PR_SECTIONS)} 세 개를 이 순서대로 쓴다.
- 각 섹션은 "- "로 시작하는 불릿을 최소 1개, 최대 5개 쓴다.
- Why: 변경 이유를 쓴다. 사용자가 준 변경 이유가 있으면 우선 반영하고, 없으면 diff에서 드러나는 범위로만 추론한다.
- What: 변경된 파일/모듈 이름을 포함해 무엇이 바뀌었는지 쓴다.
- How to Test: 실행할 명령이나 확인할 동작을 구체적으로 쓴다.
- diff에 없는 내용(이슈 번호, 성능 수치 등)은 지어내지 않는다. `[MASKED:...]`로 가려진 값은 추측하지 않는다.
- 위 형식 외의 설명, 인사말, 코드 블록(```)은 출력하지 않는다."""


def build_user_prompt(changes: Changes, diff_text: str, context: str | None) -> str:
    file_lines = "\n".join(f"- [{f.status}] {f.path}" for f in changes.files) or "- (없음)"
    scope = {
        "staged": "git add 된(staged) 변경",
        "working-tree": "작업 트리의 전체 변경(staged + unstaged + 새 파일)",
    }.get(changes.mode, f"브랜치에서 커밋된 변경 ({changes.mode.split(':', 1)[-1]}...HEAD)")

    parts = [
        f"[브랜치] {changes.branch}",
        f"[범위] {scope}",
        f"[변경 파일 {len(changes.files)}개]\n{file_lines}",
    ]
    if context:
        parts.append(f"[변경 이유 (작성자 제공)]\n{context}")
    parts.append(f"[git diff]\n{diff_text}")
    return "\n\n".join(parts)


def build_retry_prompt(user_prompt: str, previous_output: str, problems: list[str]) -> str:
    problem_lines = "\n".join(f"- {p}" for p in problems)
    return (
        f"{user_prompt}\n\n"
        f"[이전 응답]\n{previous_output}\n\n"
        f"[이전 응답의 문제]\n{problem_lines}\n\n"
        "위 문제를 고쳐서 출력 형식을 정확히 지킨 결과만 다시 작성하라."
    )
