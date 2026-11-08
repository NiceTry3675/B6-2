"""AI 기반 Git 커밋 메시지 / PR 초안 생성기.

사용법:
    python main.py commit [옵션]
    python main.py pr [옵션]
    python main.py --help
"""

import sys

# 버전 검사를 패키지 import보다 먼저 한다. (패키지 코드는 3.10+ 문법을 쓴다)
if sys.version_info < (3, 10):
    sys.stderr.write(
        "[ERROR] Python 3.10 이상이 필요합니다. 현재 버전: %d.%d\n" % sys.version_info[:2]
    )
    sys.exit(1)

from gitgen.cli import run  # noqa: E402

if __name__ == "__main__":
    sys.exit(run())
