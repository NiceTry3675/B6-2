# 항목 1 시연 로그

실행 일시: 2026-11-12 14:01 / 커밋: 87abec5 / Python 3.14.10

명령은 모두 저장소 루트에서 가상환경을 켠 상태로 실행했습니다. 로그(stderr)와 결과(stdout)를 함께 담았습니다. 저장소의 절대 경로는 /path/to/B6-2 로 바꿔 적었습니다.

## 결과 요약

| 확인 항목 | 결과 | 위치 |
| --- | --- | --- |
| 변경 사항 없음 | 메시지 출력, 종료 코드 0 | 1 |
| API Key 없음 | `[ERROR]` 출력, 종료 코드 1 | 2 |
| 루트가 아닌 곳 | `[ERROR]` 출력, 종료 코드 1 | 3 |
| 커밋 메시지 | 제목 24자 + 불릿 1개 | 5 |
| PR 초안 | 제목 + Why / What / How to Test, 섹션마다 불릿 1개 이상 | 4, 4-2 |
| `max_tokens` 차이 | 재현됨. 40에서 불릿이 잘려 제목만 남고, 15에서는 제목이 끊겼을 수 있어 오류로 종료. PR은 60과 120에서 잘려 1회 재생성 후 자리표시 불릿 | 6-5 ~ 6-8 |
| `temperature` 차이 | **뚜렷하지 않음.** `0`과 `1.5` 모두 두 번의 제목이 서로 달랐고, `0`의 2번째와 `1.5`의 2번째는 제목이 같았음 | 6-1 ~ 6-4 |
| 안전 모드 | 전송량 제한(3/6 파일, 200/439줄), 마스킹 2건 | 7, D |
| 단위 테스트 | 57개 통과 | E |

`--base 7e0df43`을 쓴 실행(4, 7, 6-1 ~ 6-4, 6-7)은 커밋 `87abec5`에서 했습니다. 범위는 PR #1 머지 이후의 변경 전체(6개 파일, 439줄)입니다. 이후 커밋이 쌓이면 같은 명령의 범위가 달라집니다.

## A. 작업 트리가 깨끗한 상태

### 1. 변경 사항 없음

```text
$ python main.py commit
[INFO] 변경 사항이 없습니다. 커밋 메시지를 생성하지 않고 종료합니다.
(종료 코드: 0)
```

### 2. API Key 없음

```text
$ GEMINI_API_KEY= AI_API_KEY= python main.py commit
[ERROR] GEMINI_API_KEY 환경변수가 설정되지 않았습니다.
        예) export GEMINI_API_KEY="YOUR_KEY"
(종료 코드: 1)
```

### 3. 프로젝트 루트가 아닌 곳에서 실행

```text
$ (cd gitgen && python ../main.py commit)
[ERROR] 프로젝트 루트 디렉토리에서 실행하세요. (루트: /path/to/B6-2)
(종료 코드: 1)
```

### 4. PR 제목/본문 초안 (기본값: temperature 0.3)

```text
$ python main.py pr --base 7e0df43
[INFO] 현재 브랜치: fix/file-mention-and-truncated-title
[INFO] Git status 수집 완료: 6개 파일 변경 감지 (7e0df43...HEAD 기준)
         M  README.md
         M  gitgen/cli.py
         M  gitgen/formatter.py
         M  gitgen/prompts.py
         M  tests/test_cli.py
         M  tests/test_formatter.py
[INFO] Git diff 수집 완료: 439줄
[INFO] AI API 요청 중... (model=gemini-3.8-flash, temperature=0.3, max_tokens=1024)
[INFO] 토큰 사용량: 입력 7960, 출력 371
[INFO] AI API 호출 횟수: 1회
[CHECK] PR 제목 35자 (최대 80자), 섹션 불릿: Why 2개, What 4개, How to Test 2개
[DONE] PR 초안 생성 완료

--- PR Title ---
fix: 커밋 본문 불릿 수 제한 및 제목 절단 감지 로직 추가

--- PR Body ---
## Why
- `max_tokens` 한도로 인해 제목 줄에서 생성이 잘렸을 때 불완전한 제목이 그대로 출력되는 문제가 있었습니다.
- 커밋 본문 품질 유지를 위해 본문 불릿 수(최대 2개)와 언급 파일 수에 대한 코드 차원의 제한 및 검증 로직이 필요했습니다.

## What
- `gitgen/formatter.py`: 제목 잘림 가능 여부 판별(`title_may_be_cut`), 커밋 본문 불릿 2개 초과 시 절단 처리, 본문 내 파일 언급 수 집계(`count_file_mentions`), `OutputError` 예외 추가
- `gitgen/cli.py`: 생성 응답 절단 시 제목 누락 확인 후 `OutputError` 발생 처리, 변경 파일 목록 로그 출력(최대 20개), 본문 파일 언급 수 `[CHECK]` 로그 추가
- `gitgen/prompts.py`: 커밋 본문 불릿 수(1~2개) 및 대표 파일 언급 수(1~3개) 프롬프트 가이드라인 조정
- `README.md`, `tests/test_cli.py`, `tests/test_formatter.py`: 변경된 로그 형식 반영, 불릿 제한, 파일 언급 카운팅 및 절단 처리 관련 단위 테스트 추가

## How to Test
- `pytest` 또는 `python -m unittest discover tests` 실행하여 테스트 통과 확인
- `python main.py commit --max-tokens 40` 등의 명령으로 토큰 제한 상황에서 제목 절단 감지 및 미완성 불릿 제거 로그 동작 확인
----------------------
(종료 코드: 0)
```

### 7. 안전 모드 - 전송량 제한 (프롬프트 본문은 생략)

```text
$ python main.py pr --base 7e0df43 --dry-run --safe-mode 2>&1 >/dev/null
[INFO] 현재 브랜치: fix/file-mention-and-truncated-title
[INFO] Git status 수집 완료: 6개 파일 변경 감지 (7e0df43...HEAD 기준)
         M  README.md
         M  gitgen/cli.py
         M  gitgen/formatter.py
         M  gitgen/prompts.py
         M  tests/test_cli.py
         M  tests/test_formatter.py
[INFO] Git diff 수집 완료: 439줄
[SAFE] 마스킹 0건(없음), 민감 파일 제외 0개, 전송 파일 3/6, 전송 줄 200/439
[INFO] --dry-run: AI API를 호출하지 않습니다. 전송될 프롬프트를 출력합니다.
(종료 코드: 0)
```

## B. temperature 비교

같은 변경(PR #2, 6개 파일 261줄)에 값만 바꿔 두 번씩 실행했습니다. 비교하기 쉽게 로그는 빼고 결과만 담았습니다.

### 6-1. --temperature 0 (1번째)

```text
$ python main.py pr --base 7e0df43 --temperature 0 2>/dev/null

--- PR Title ---
fix: 토큰 초과 시 잘린 제목 감지 및 커밋 본문 파일 언급 검증 로직 추가

--- PR Body ---
## Why
- `max_tokens` 한도로 인해 제목 중간에서 생성이 끊겼을 때 불완전한 텍스트가 결과물로 출력되는 문제가 있었습니다.
- 커밋 본문 생성 시 불릿 개수가 지나치게 많아지거나 변경 파일 언급 여부를 명확히 파악하기 어려웠습니다.

## What
- `gitgen/formatter.py`: 제목이 도중에 잘렸는지 확인하는 `title_may_be_cut()` 및 AI 출력 오류를 나타내는 `OutputError` 추가, 커밋 본문 최대 불릿 수(2개) 초과 시 후처리 로직 추가, 본문 내 변경 파일 언급 개수를 세는 `count_file_mentions()` 추가
- `gitgen/cli.py`: 응답 토큰 초과 시 제목 절단 여부를 판별해 `OutputError`를 발생시키고 실패 처리하도록 개선, CLI 실행 로그에 변경 파일 목록 및 커밋 본문의 파일 언급 통계 출력 추가
- `gitgen/prompts.py`: 커밋 본문 불릿 수(최대 2개) 및 대표 파일/모듈 언급 수(최대 3개) 제한 프롬프트 반영
- `README.md`: 변경된 커밋 본문 규칙, CLI 출력 로그 예시 및 `max_tokens` 관련 설명 갱신
- `tests/test_cli.py`, `tests/test_formatter.py`: 불릿 수 초과 제거, 파일 언급 수 판별(조사 포함/제외), 응답 잘림 시 제목 및 불릿 처리 관련 테스트 케이스 추가

## How to Test
- `python -m unittest tests/test_formatter.py tests/test_cli.py` 명령을 실행해 신규 추가된 단위 테스트들이 통과하는지 확인합니다.
- 변경 파일이 있는 상태에서 `python main.py commit --max-tokens 20` 등 매우 낮은 토큰 값을 지정해 제목 절단 시 에러 메시지와 함께 종료되는지 확인합니다.
- 커밋 메시지 생성 시 콘솔 로그에 변경 파일 목록과 파일 언급 통계가 정상 출력되는지 확인합니다.
----------------------
(종료 코드: 0)
```

### 6-2. --temperature 0 (2번째)

```text
$ python main.py pr --base 7e0df43 --temperature 0 2>/dev/null

--- PR Title ---
fix: 제목 잘림 감지 오류 처리 및 커밋 본문 품질 규칙 강화

--- PR Body ---
## Why
- `max_tokens` 도달로 커밋/PR 제목이 완성되지 않고 끊겼을 때 불완전한 결과물이 그대로 출력되는 문제가 있었습니다.
- 커밋 본문의 불릿 수와 파일 언급에 대한 명확한 상한 및 품질 검증 기준이 코드로 강제되지 않았습니다.

## What
- `gitgen/formatter.py`: 제목 잘림 가능성을 판단하는 `title_may_be_cut` 및 `OutputError` 추가, 커밋 본문 최대 불릿 수(2개) 초과 시 후처리 로직 및 `count_file_mentions` 파일 언급 수 집계 함수 구현
- `gitgen/cli.py`: 제목 잘림 시 `OutputError`를 발생시켜 결과 출력을 중단하도록 개선, 변경 파일 목록 로그(최대 20개) 및 본문 파일 언급 수 검증 로그 추가
- `gitgen/prompts.py`: 커밋 본문 불릿 수(1~2개) 및 대표 파일/모듈 언급 수(1~3개)에 맞춰 시스템 프롬프트 규칙 수정
- `README.md`, `tests/test_cli.py`, `tests/test_formatter.py`: 변경된 규칙 반영 문서화 및 관련 단위 테스트 추가

## How to Test
- `python -m unittest tests/test_formatter.py tests/test_cli.py` 명령을 실행해 단위 테스트 통과 여부 확인
- CLI 실행 시 `--max-tokens`를 극도로 낮게 주었을 때 제목 미완성 오류가 정상 발생하고 종료되는지 확인
- 변경 사항이 있는 저장소에서 `python main.py commit` 실행 후 본문 불릿 수 제한(최대 2개) 및 파일 언급 수 검증 로그 출력 확인
----------------------
(종료 코드: 0)
```

### 6-3. --temperature 1.5 (1번째)

```text
$ python main.py pr --base 7e0df43 --temperature 1.5 2>/dev/null

--- PR Title ---
fix: 커밋 본문 불릿 수 제한, 파일 언급 집계 및 미완성 제목 오류 처리 추가

--- PR Body ---
## Why
- `max_tokens` 한도로 인해 제목 줄에서 생성이 끊겼을 때 불완전한 결과물이 그대로 출력되는 문제가 있었습니다.
- 커밋 본문이 장황해지지 않도록 핵심 불릿 수(1~2개)와 언급 파일 수(1~3개)에 대한 품질 기준을 코드로 보장하고 로그로 검증할 필요가 있었습니다.

## What
- `gitgen/formatter.py`: 불완전한 제목 여부를 판단하는 `title_may_be_cut()`, 본문 언급 파일 수를 계산하는 `count_file_mentions()`, 최대 불릿 수(2개) 초과 시 잘라내는 `finalize_commit()` 로직 및 `OutputError` 추가
- `gitgen/cli.py`: 토큰 한도로 제목이 잘렸을 때 `OutputError` 발생 및 오류 처리, 상태 수집 시 변경 파일 목록(최대 20개) 출력, 커밋 생성 후 본문 불릿 및 언급 파일 수 집계 로그 출력 추가
- `gitgen/prompts.py`: 커밋 본문 불릿 수(1~2개) 및 대표 파일/모듈 언급 수(1~3개) 규칙을 프롬프트에 반영
- `tests/test_cli.py`, `tests/test_formatter.py`: 불릿 수 초과 처리, 한국어 조사를 포함한 파일 언급 카운트, 토큰 잘림에 따른 제목/불릿 처리 관련 단위 테스트 추가
- `README.md`: 변경된 커밋 메시지 규칙 및 로그 출력 예시, 잘린 제목 관련 오류 안내 갱신

## How to Test
- `pytest` 또는 `python -m unittest discover tests` 명령어로 신규 단위 테스트 통과 확인
- 커밋 변경 사항이 있는 상태에서 `python main.py commit` 실행 후 변경 파일 목록 출력 및 본문 불릿/언급 파일 수 `[CHECK]` 로그 확인
- `python main.py commit --max-tokens 20`과 같이 극단적으로 낮은 토큰 값을 주어 제목 미완성 오류 안내 메시지가 정상 출력되는지 확인
----------------------
(종료 코드: 0)
```

### 6-4. --temperature 1.5 (2번째)

```text
$ python main.py pr --base 7e0df43 --temperature 1.5 2>/dev/null

--- PR Title ---
fix: 제목 잘림 감지 오류 처리 및 커밋 본문 품질 규칙 강화

--- PR Body ---
## Why
- `max_tokens` 도달로 인해 응답이 제목 줄에서 중간에 잘렸을 때 불완전한 결과물이 그대로 출력되는 문제가 있었습니다.
- 커밋 본문이 길어지거나 불필요하게 파일이 나열되는 것을 방지하고, 본문에서 언급된 변경 파일 수를 가시화할 필요가 있었습니다.

## What
- `gitgen/formatter.py`: 불완전한 제목 잘림을 확인하는 `title_may_be_cut()`, 본문 내 파일 언급 수를 집계하는 `count_file_mentions()`, 예외 클래스 `OutputError` 추가 및 커밋 본문 불릿을 최대 2개로 제한하는 후처리 로직 구현
- `gitgen/cli.py`: 제목이 잘렸을 때 `OutputError`를 발생시켜 결과 출력을 차단하도록 처리하고, 수집된 변경 파일 목록(최대 20개) 및 본문 파일 언급 수 로그 출력 추가
- `gitgen/prompts.py`: 커밋 본문 불릿 수(1~2개) 및 대표 파일/모듈 언급 수(1~3개)에 대한 프롬프트 규칙 보강
- `tests/test_cli.py`, `tests/test_formatter.py`: 제목 잘림 예외 처리, 불릿 수 제한 자르기, 파일 언급 카운트 및 한국어 조사 처리 관련 단위 테스트 추가
- `README.md`: 변경된 커밋 본문 품질 규칙, 파일 목록 로그 및 잘린 제목 오류 처리 동작 내용 반영

## How to Test
- `python -m unittest tests/test_formatter.py tests/test_cli.py` 명령을 실행해 신규 추가된 테스트가 통과하는지 확인
- 변경 사항이 있는 저장소에서 `python main.py commit` 실행 후 변경 파일 목록 출력과 `[CHECK]` 로그의 불릿 수/언급 파일 수가 정상 표기되는지 확인
- `python main.py commit --max-tokens 20` 등 극단적으로 작은 토큰으로 실행하여 `[ERROR] max_tokens 한도에 걸려 제목이 완성되지 않았을 수 있어...` 오류와 함께 종료 코드 1로 끝나는지 확인
----------------------
(종료 코드: 0)
```

## C. 임시 변경이 있는 상태 (커밋 메시지, max_tokens 비교)

`gitgen/cli.py`의 `DEFAULT_TIMEOUT`을 `60.0`에서 `30.0`으로 바꾼 뒤 실행했고, 끝난 뒤 `git restore`로 되돌렸습니다.

### 변경 내용

```text
$ git diff --stat
 gitgen/cli.py | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)
(종료 코드: 0)
```

### 5. 커밋 메시지 (기본값: max_tokens 1024)

```text
$ python main.py commit
[INFO] Git status 수집 완료: 1개 파일 변경 감지 (작업 트리 전체 기준)
         M  gitgen/cli.py
[INFO] Git diff 수집 완료: 13줄
[INFO] AI API 요청 중... (model=gemini-3.8-flash, temperature=0.3, max_tokens=1024)
[INFO] 토큰 사용량: 입력 593, 출력 39
[INFO] AI API 호출 횟수: 1회
[CHECK] 커밋 제목 24자 (권장 50자 / 최대 72자), 본문 불릿 1개 (최대 2개), 언급 파일 1개 (권장 1~3개)
[DONE] 커밋 메시지 생성 완료

--- Commit Message ---
chore: 기본 API 요청 타임아웃 단축

- `gitgen/cli.py`의 `DEFAULT_TIMEOUT` 값을 60초에서 30초로 변경
----------------------
(종료 코드: 0)
```

### 6-5. --max-tokens 40

```text
$ python main.py commit --max-tokens 40
[INFO] Git status 수집 완료: 1개 파일 변경 감지 (작업 트리 전체 기준)
         M  gitgen/cli.py
[INFO] Git diff 수집 완료: 13줄
[INFO] AI API 요청 중... (model=gemini-3.8-flash, temperature=0.3, max_tokens=40)
[WARN] max_tokens 한도에 도달해 응답이 잘렸습니다. 필요하면 --max-tokens 값을 늘리세요.
[INFO] 토큰 사용량: 입력 593, 출력 36
[FIX] 응답이 잘려 미완성 불릿을 제거했습니다: '`gitgen/cli.py`에서 기본 타임아웃을 60초에서 30초로'
[INFO] AI API 호출 횟수: 1회
[CHECK] 커밋 제목 20자 (권장 50자 / 최대 72자), 본문 불릿 0개 (최대 2개), 언급 파일 0개 (권장 1~3개)
[DONE] 커밋 메시지 생성 완료

--- Commit Message ---
chore: 기본 타임아웃 시간 변경
----------------------
(종료 코드: 0)
```

### 6-6. --max-tokens 15

```text
$ python main.py commit --max-tokens 15
[INFO] Git status 수집 완료: 1개 파일 변경 감지 (작업 트리 전체 기준)
         M  gitgen/cli.py
[INFO] Git diff 수집 완료: 13줄
[INFO] AI API 요청 중... (model=gemini-3.8-flash, temperature=0.3, max_tokens=15)
[WARN] max_tokens 한도에 도달해 응답이 잘렸습니다. 필요하면 --max-tokens 값을 늘리세요.
[INFO] 토큰 사용량: 입력 593, 출력 11
[ERROR] max_tokens 한도에 걸려 제목이 완성되지 않았을 수 있어 결과를 출력하지 않습니다. --max-tokens 값을 늘리세요.
[INFO] AI API 호출 횟수: 1회
(종료 코드: 1)
```

### 4-2. PR 제목/본문 초안 (같은 임시 변경, --base 없이)

```text
$ python main.py pr
[INFO] 현재 브랜치: fix/file-mention-and-truncated-title
[INFO] Git status 수집 완료: 1개 파일 변경 감지 (작업 트리 전체 기준)
         M  gitgen/cli.py
[INFO] Git diff 수집 완료: 13줄
[INFO] AI API 요청 중... (model=gemini-3.8-flash, temperature=0.3, max_tokens=1024)
[INFO] 토큰 사용량: 입력 632, 출력 147
[INFO] AI API 호출 횟수: 1회
[CHECK] PR 제목 31자 (최대 80자), 섹션 불릿: Why 1개, What 1개, How to Test 2개
[DONE] PR 초안 생성 완료

--- PR Title ---
chore: CLI의 기본 요청 타임아웃을 30초로 단축

--- PR Body ---
## Why
- API 요청의 기본 대기 시간이 길어 응답 지연 시 불필요하게 오래 대기하는 문제를 방지하기 위해 기본 타임아웃 값을 조정합니다.

## What
- `gitgen/cli.py`에서 `DEFAULT_TIMEOUT` 값을 기존 60.0초에서 30.0초로 변경

## How to Test
- `gitgen/cli.py` 코드에서 `DEFAULT_TIMEOUT` 상수가 `30.0`으로 설정되어 있는지 확인
- CLI 명령어를 실행하여 API 호출이 정상 동작하는지 확인
----------------------
(종료 코드: 0)
```

### 6-8. PR에 --max-tokens 60 (같은 임시 변경)

```text
$ python main.py pr --max-tokens 60
[INFO] 현재 브랜치: fix/file-mention-and-truncated-title
[INFO] Git status 수집 완료: 1개 파일 변경 감지 (작업 트리 전체 기준)
         M  gitgen/cli.py
[INFO] Git diff 수집 완료: 13줄
[INFO] AI API 요청 중... (model=gemini-3.8-flash, temperature=0.3, max_tokens=60)
[WARN] max_tokens 한도에 도달해 응답이 잘렸습니다. 필요하면 --max-tokens 값을 늘리세요.
[INFO] 토큰 사용량: 입력 632, 출력 56
[WARN] 형식 문제 발견 → 1회 재생성합니다: '## What' 섹션이 없습니다. / '## How to Test' 섹션이 없습니다.
[WARN] max_tokens 한도에 도달해 응답이 잘렸습니다. 필요하면 --max-tokens 값을 늘리세요.
[INFO] 토큰 사용량: 입력 747, 출력 56
[WARN] 재생성 후에도 남은 문제는 후처리로 보완합니다: '## What' 섹션에 불릿이 없습니다. / '## How to Test' 섹션이 없습니다.
[FIX] '## What' 섹션이 비어 있어 자리표시 불릿을 넣었습니다.
[FIX] '## How to Test' 섹션이 비어 있어 자리표시 불릿을 넣었습니다.
[INFO] AI API 호출 횟수: 2회
[CHECK] PR 제목 30자 (최대 80자), 섹션 불릿: Why 1개, What 1개, How to Test 1개
[DONE] PR 초안 생성 완료

--- PR Title ---
chore: CLI 기본 요청 타임아웃을 30초로 단축

--- PR Body ---
## Why
- API 요청 시 과도하게 긴 대기 시간을 줄이고 빠른 피드백을 제공하기 위해 기본 타임아웃 값을 조정합니다.

## What
- (AI가 작성하지 못함 - 직접 작성 필요)

## How to Test
- (AI가 작성하지 못함 - 직접 작성 필요)
----------------------
(종료 코드: 0)
```

### 6-7. PR에 --max-tokens 120 (작업 트리를 되돌린 뒤 실행, 변경 파일 목록 6줄 생략)

```text
$ python main.py pr --base 7e0df43 --max-tokens 120 2>&1 | grep -v '^         '
[INFO] 현재 브랜치: fix/file-mention-and-truncated-title
[INFO] Git status 수집 완료: 6개 파일 변경 감지 (7e0df43...HEAD 기준)
[INFO] Git diff 수집 완료: 439줄
[INFO] AI API 요청 중... (model=gemini-3.8-flash, temperature=0.3, max_tokens=120)
[WARN] max_tokens 한도에 도달해 응답이 잘렸습니다. 필요하면 --max-tokens 값을 늘리세요.
[INFO] 토큰 사용량: 입력 7960, 출력 116
[WARN] 형식 문제 발견 → 1회 재생성합니다: '## How to Test' 섹션이 없습니다.
[WARN] max_tokens 한도에 도달해 응답이 잘렸습니다. 필요하면 --max-tokens 값을 늘리세요.
[INFO] 토큰 사용량: 입력 8124, 출력 116
[FIX] 응답이 잘려 '## What'의 미완성 불릿을 제거했습니다: '`gitgen/formatter.py`: 제목 잘'
[WARN] 재생성 후에도 남은 문제는 후처리로 보완합니다: '## How to Test' 섹션이 없습니다.
[FIX] '## What' 섹션이 비어 있어 자리표시 불릿을 넣었습니다.
[FIX] '## How to Test' 섹션이 비어 있어 자리표시 불릿을 넣었습니다.
[INFO] AI API 호출 횟수: 2회
[CHECK] PR 제목 36자 (최대 80자), 섹션 불릿: Why 2개, What 1개, How to Test 1개
[DONE] PR 초안 생성 완료

--- PR Title ---
fix: 제목 잘림 감지 오류 처리 및 커밋 본문 품질 기준 강화

--- PR Body ---
## Why
- `max_tokens` 한도 도달 시 제목 줄 중간에서 응답이 끊겨 미완성된 제목이 그대로 출력되는 문제가 있었습니다.
- 커밋 본문이 길어지거나 파일 언급이 과도해지는 것을 방지하고, 본문 품질 기준(불릿 수 제한 및 파일 언급 집계)을 보장할 필요가 있었습니다.

## What
- (AI가 작성하지 못함 - 직접 작성 필요)

## How to Test
- (AI가 작성하지 못함 - 직접 작성 필요)
----------------------
(종료 코드: 0)
```

## D. 마스킹 시연

가짜 비밀값이 든 임시 파일 `demo_secret.py`를 만들어 실행했고, 끝난 뒤 지웠습니다. 프롬프트에서 해당 줄만 뽑았습니다.

### 안전 모드 OFF

```text
$ python main.py commit --dry-run 2>&1 | grep -E '^\[SAFE\]|^\+(ADMIN|DB)_'
+ADMIN_EMAIL = "admin@example.com"
+DB_PASSWORD = "p@ssw0rd-example"
(종료 코드: 0)
```

### 안전 모드 ON

```text
$ python main.py commit --dry-run --safe-mode 2>&1 | grep -E '^\[SAFE\]|^\+(ADMIN|DB)_'
[SAFE] 마스킹 2건(secret_literal 1, email 1), 민감 파일 제외 0개, 전송 파일 1/1, 전송 줄 8/8
+ADMIN_EMAIL = "[MASKED:email]"
+DB_PASSWORD = "[MASKED:secret_literal]"
(종료 코드: 0)
```

## E. 단위 테스트

### 테스트 전체

```text
$ python -m unittest discover -s tests -t . 2>&1 | tail -4
----------------------------------------------------------------------
Ran 57 tests in 1.079s

OK
(종료 코드: 0)
```

