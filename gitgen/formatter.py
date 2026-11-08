"""AI 출력 파싱 · 형식 검증 · 후처리.

흐름
1. parse_*    : AI가 준 자유 텍스트를 구조(제목/불릿/섹션)로 읽고, 고칠 수 없는 문제를 찾는다.
2. 문제가 있으면 cli가 AI에 1회 재생성을 요청한다.
3. finalize_* : 코드로 고칠 수 있는 것(제목 길이, 마침표, 불릿 기호, 빈 섹션)을 후처리한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

COMMIT_TITLE_RECOMMENDED = 50
COMMIT_TITLE_MAX = 72
COMMIT_BODY_MAX_BULLETS = 2  # 요구사항: 핵심 변경 사항 1~2개를 불릿으로 요약
COMMIT_BODY_MAX_FILES = 3  # 요구사항: 변경된 파일(또는 모듈) 1~3개 언급
PR_TITLE_MAX = 80
PR_SECTIONS = ("Why", "What", "How to Test")
PLACEHOLDER_BULLET = "(AI가 작성하지 못함 - 직접 작성 필요)"

_BULLET_RX = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
_LABEL_RX = re.compile(
    r"^\s*\**\s*(?:TITLE|PR\s*Title|Commit\s*Message|제목|커밋\s*메시지)\s*\**\s*[:：]\s*",
    re.IGNORECASE,
)
_SECTION_RX = re.compile(r"^\s*(?:#{1,6}\s*|\*\*\s*)(why|what|how\s+to\s+test)\b", re.IGNORECASE)
_CONVENTIONAL_RX = re.compile(r"^[a-z]+(?:\([^)]+\))?!?: \S")


@dataclass
class CommitMessage:
    title: str
    body: list[str] = field(default_factory=list)  # 불릿 내용 (기호 제외)

    def render(self) -> str:
        if not self.body:
            return self.title
        return self.title + "\n\n" + "\n".join(f"- {b}" for b in self.body)


@dataclass
class PRDraft:
    title: str
    sections: dict[str, list[str]] = field(default_factory=dict)

    def render_body(self) -> str:
        blocks = []
        for name in PR_SECTIONS:
            bullets = "\n".join(f"- {b}" for b in self.sections.get(name, []))
            blocks.append(f"## {name}\n{bullets}")
        return "\n\n".join(blocks)


def clean_output(text: str) -> str:
    """앞뒤 공백과 전체를 감싼 코드 블록(```)을 걷어낸다."""
    text = text.strip()
    m = re.match(r"^```[\w-]*\n(.*?)\n?```$", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    return text


def _strip_title(line: str) -> str:
    line = _LABEL_RX.sub("", line.strip())
    line = line.lstrip("#").strip().strip("`*\"'").strip()
    return line


def _bullet_text(line: str) -> str:
    return _BULLET_RX.sub("", line).strip()


def truncate_title(title: str, limit: int) -> str:
    """limit 글자 이하로 자른다. 가능하면 단어(공백) 경계에서 자른다."""
    if len(title) <= limit:
        return title
    cut = title[:limit]
    space = cut.rfind(" ")
    if space >= limit // 2:
        cut = cut[:space]
    return cut.rstrip(" ,.;:-")


def _tidy_title(title: str) -> str:
    return title.rstrip("。.").strip()


def drop_truncated_tail(parsed: "CommitMessage | PRDraft") -> str | None:
    """max_tokens로 응답이 잘렸을 때, 중간에 끊긴 마지막 불릿을 버린다."""
    if isinstance(parsed, CommitMessage):
        if parsed.body:
            return f"응답이 잘려 미완성 불릿을 제거했습니다: '{parsed.body.pop()}'"
        return None
    for name in reversed(list(parsed.sections)):
        if parsed.sections[name]:
            return f"응답이 잘려 '## {name}'의 미완성 불릿을 제거했습니다: '{parsed.sections[name].pop()}'"
    return None


# ---------------------------------------------------------------- commit


def parse_commit(text: str) -> tuple[CommitMessage, list[str]]:
    lines = clean_output(text).splitlines()
    title = ""
    body: list[str] = []
    for line in lines:
        if not title:
            if line.strip():
                title = _strip_title(line)
            continue
        if line.strip():
            body.append(_bullet_text(line))

    problems = []
    if not title:
        problems.append("커밋 제목(첫 줄)이 없습니다.")
    return CommitMessage(title=title, body=body), problems


def finalize_commit(msg: CommitMessage) -> tuple[CommitMessage, list[str]]:
    notes: list[str] = []
    title = _tidy_title(msg.title)
    if len(title) > COMMIT_TITLE_MAX:
        notes.append(f"커밋 제목이 {len(title)}자라 최대 {COMMIT_TITLE_MAX}자로 잘랐습니다.")
        title = truncate_title(title, COMMIT_TITLE_MAX)
    elif len(title) > COMMIT_TITLE_RECOMMENDED:
        notes.append(f"커밋 제목이 {len(title)}자로 권장 길이({COMMIT_TITLE_RECOMMENDED}자)를 넘습니다.")
    if title and not _CONVENTIONAL_RX.match(title):
        notes.append("커밋 제목이 '<type>: <요약>' 형식이 아닙니다.")

    # 본문 최소 품질 기준: 불릿을 최대 2개로 맞춘다. 프롬프트가 중요한 순서로 쓰게 하므로 뒤쪽을 버린다.
    body = list(msg.body)
    if len(body) > COMMIT_BODY_MAX_BULLETS:
        dropped = body[COMMIT_BODY_MAX_BULLETS:]
        body = body[:COMMIT_BODY_MAX_BULLETS]
        notes.append(
            f"커밋 본문 불릿이 {len(body) + len(dropped)}개라 앞의 {COMMIT_BODY_MAX_BULLETS}개만 남겼습니다. "
            f"(제거: {' / '.join(dropped)})"
        )
    return CommitMessage(title=title, body=body), notes


def count_file_mentions(lines: list[str], paths: list[str]) -> int:
    """본문에 변경 파일이 몇 개 언급됐는지 센다. 전체 경로나 파일 이름이 나오면 언급으로 본다."""
    text = "\n".join(lines)

    def mentioned(word: str) -> bool:
        # test_cli.py 안의 cli.py 처럼 다른 이름의 일부로 들어간 경우는 세지 않는다.
        return bool(word) and re.search(rf"(?<![\w./-]){re.escape(word)}(?![\w-])", text) is not None

    count = 0
    for path in paths:
        name = path.rstrip("/").rsplit("/", 1)[-1]
        if mentioned(path) or mentioned(name):
            count += 1
    return count


# ---------------------------------------------------------------- PR


def parse_pr(text: str) -> tuple[PRDraft, list[str]]:
    title = ""
    sections: dict[str, list[str]] = {}
    current: str | None = None

    for line in clean_output(text).splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        m = _SECTION_RX.match(stripped)
        if m:
            key = m.group(1).lower()
            current = "How to Test" if key.startswith("how") else key.capitalize()
            sections.setdefault(current, [])
            continue
        if current is None:
            if not title and not stripped.startswith("#"):
                title = _strip_title(stripped)
            continue
        item = _bullet_text(stripped)
        if item:
            sections[current].append(item)

    problems = []
    if not title:
        problems.append("PR 제목(TITLE: ...)이 없습니다.")
    for name in PR_SECTIONS:
        if name not in sections:
            problems.append(f"'## {name}' 섹션이 없습니다.")
        elif not sections[name]:
            problems.append(f"'## {name}' 섹션에 불릿이 없습니다.")
    return PRDraft(title=title, sections=sections), problems


def finalize_pr(draft: PRDraft) -> tuple[PRDraft, list[str]]:
    notes: list[str] = []
    title = _tidy_title(draft.title)
    if not title:
        title = "(PR 제목 직접 작성 필요)"
        notes.append("PR 제목이 없어 자리표시자를 넣었습니다.")
    elif len(title) > PR_TITLE_MAX:
        notes.append(f"PR 제목이 {len(title)}자라 최대 {PR_TITLE_MAX}자로 잘랐습니다.")
        title = truncate_title(title, PR_TITLE_MAX)

    sections = {}
    for name in PR_SECTIONS:
        bullets = draft.sections.get(name) or []
        if not bullets:
            bullets = [PLACEHOLDER_BULLET]
            notes.append(f"'## {name}' 섹션이 비어 있어 자리표시 불릿을 넣었습니다.")
        sections[name] = bullets
    return PRDraft(title=title, sections=sections), notes
