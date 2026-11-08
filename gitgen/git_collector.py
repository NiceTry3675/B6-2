"""Git 변경 사항 수집.

git status / git diff 실행 결과만 다룬다. AI 호출이나 프롬프트에 대해서는 모른다.
그래서 AI 없이도 이 모듈만 따로 테스트할 수 있다.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path


class GitError(Exception):
    """Git 명령 실행 실패 또는 실행 환경이 올바르지 않을 때."""


@dataclass
class ChangedFile:
    status: str  # 예: "M", "A", "D", "R", "??"
    path: str


@dataclass
class Changes:
    branch: str
    mode: str  # "staged" | "working-tree" | "base:<branch>"
    files: list[ChangedFile] = field(default_factory=list)
    diff: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.files and not self.diff.strip()

    @property
    def diff_line_count(self) -> int:
        return len(self.diff.splitlines())


def _run_git(args: list[str], cwd: Path, ok_codes: tuple[int, ...] = (0,)) -> str:
    # core.quotepath=false: 한글 파일명이 "\355\225\234" 처럼 이스케이프되지 않게 한다.
    cmd = ["git", "-c", "core.quotepath=false", *args]
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise GitError("git 명령을 찾을 수 없습니다. Git이 설치되어 있는지 확인하세요.") from exc
    if proc.returncode not in ok_codes:
        msg = proc.stderr.strip() or proc.stdout.strip()
        raise GitError(f"`{' '.join(cmd[3:])}` 실행 실패: {msg}")
    return proc.stdout


def ensure_repo_root(cwd: Path) -> Path:
    """cwd가 Git 저장소의 루트 디렉토리인지 확인한다."""
    try:
        top = _run_git(["rev-parse", "--show-toplevel"], cwd).strip()
    except GitError as exc:
        raise GitError(
            "Git 저장소가 아닙니다. Git이 초기화된 프로젝트 루트에서 실행하세요. (git init)"
        ) from exc
    if Path(top).resolve() != cwd.resolve():
        raise GitError(f"프로젝트 루트 디렉토리에서 실행하세요. (루트: {top})")
    return Path(top)


def current_branch(cwd: Path) -> str:
    name = _run_git(["branch", "--show-current"], cwd).strip()
    return name or "(detached HEAD)"


def _has_head(cwd: Path) -> bool:
    return bool(_run_git(["rev-parse", "--verify", "-q", "HEAD"], cwd, ok_codes=(0, 1)).strip())


def parse_status(porcelain: str) -> tuple[list[ChangedFile], list[ChangedFile], list[ChangedFile]]:
    """`git status --porcelain` 출력을 (staged, unstaged, untracked)로 나눈다."""
    staged: list[ChangedFile] = []
    unstaged: list[ChangedFile] = []
    untracked: list[ChangedFile] = []
    for line in porcelain.splitlines():
        if len(line) < 4:
            continue
        x, y, path = line[0], line[1], line[3:]
        if " -> " in path:  # rename: "old -> new"
            path = path.split(" -> ", 1)[1]
        path = path.strip('"')
        if x == "?" and y == "?":
            untracked.append(ChangedFile("??", path))
            continue
        if x not in (" ", "?"):
            staged.append(ChangedFile(x, path))
        if y not in (" ", "?"):
            unstaged.append(ChangedFile(y, path))
    return staged, unstaged, untracked


def _untracked_diff(path: str, cwd: Path) -> str:
    # 새 파일은 git diff에 나오지 않으므로 /dev/null 과 비교해 diff 형태로 만든다.
    # --no-index 는 차이가 있으면 종료 코드 1을 돌려준다.
    return _run_git(["diff", "--no-index", "--", "/dev/null", path], cwd, ok_codes=(0, 1))


def collect_changes(cwd: Path, base: str | None = None) -> Changes:
    """변경 사항을 수집한다.

    - base 지정: `git diff <base>...HEAD` (브랜치에서 커밋한 변경, PR용)
    - staged 변경이 있으면: `git diff --cached` (실제로 커밋될 내용)
    - 없으면: `git diff HEAD` + 추적하지 않는 새 파일
    """
    branch = current_branch(cwd)

    if base:
        rng = f"{base}...HEAD"
        name_status = _run_git(["diff", "--name-status", rng], cwd)
        files = []
        for line in name_status.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                files.append(ChangedFile(parts[0][0], parts[-1]))
        diff = _run_git(["diff", rng], cwd)
        return Changes(branch=branch, mode=f"base:{base}", files=files, diff=diff)

    porcelain = _run_git(["status", "--porcelain", "--untracked-files=all"], cwd)
    staged, unstaged, untracked = parse_status(porcelain)

    if staged:
        diff = _run_git(["diff", "--cached"], cwd)
        return Changes(branch=branch, mode="staged", files=staged, diff=diff)

    diff = _run_git(["diff", "HEAD"] if _has_head(cwd) else ["diff"], cwd)
    for f in untracked:
        diff += _untracked_diff(f.path, cwd)
    return Changes(branch=branch, mode="working-tree", files=unstaged + untracked, diff=diff)
