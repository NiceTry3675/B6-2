# AI Git 커밋/PR 초안 생성기

`git status`와 `git diff`로 변경 사항을 모아 Gemini API에 보내고, **커밋 메시지**와 **PR 제목/본문 초안**을 터미널에 출력하는 Python CLI 도구입니다.

- 외부 패키지 없이 Python 표준 라이브러리만 사용합니다. Gemini REST API는 `urllib`로 직접 호출합니다.
- 생성 결과는 길이·형식 규칙으로 검증하고, 형식이 깨졌을 때는 **1회만** 다시 생성합니다.
- `--safe-mode`를 켜면 API Key, 이메일 같은 민감정보를 가리고 전송량을 제한한 뒤 보냅니다.
- 이 도구는 초안을 출력하는 데서 끝납니다. `git commit`, `git push`, PR 생성은 사용자가 결과를 검토한 뒤 직접 합니다.

---

## 1. 설치

**필요 환경**: Python 3.10 이상, Git

```bash
git clone https://github.com/<your-id>/<repo>.git
cd <repo>
python3 --version
```

설치할 패키지는 없습니다. macOS 기본 `python3`가 3.9라면 3.10 이상을 설치하고 가상환경을 만드세요.

```bash
brew install python@3.12
python3.12 -m venv .venv
source .venv/bin/activate
```

## 2. API Key 설정

API Key는 환경변수로만 받습니다. 코드에는 키가 없습니다.
[Google AI Studio](https://aistudio.google.com/apikey)에서 키를 발급받아 아래 방법 중 하나로 설정합니다.

**방법 1. 터미널에서 export**

```bash
export GEMINI_API_KEY="YOUR_KEY"
```

**방법 2. 도구 폴더의 `.env` 파일**

```bash
cp .env.example .env
```

`.env`의 `GEMINI_API_KEY=YOUR_KEY` 값을 실제 키로 바꿉니다. 도구가 실행될 때 `.env`를 읽지만, 이미 설정된 환경변수는 덮어쓰지 않습니다. `.env`는 `.gitignore`에 포함되어 있어 커밋되지 않습니다.

> `GEMINI_API_KEY`가 없으면 `AI_API_KEY`도 확인합니다.

## 3. 사용법

명령은 **Git 저장소의 루트 디렉토리**에서 실행해야 합니다.

```bash
python main.py commit
```

```bash
python main.py pr
```

다른 프로젝트에서 쓸 때는 그 프로젝트 루트로 이동한 뒤 이 도구의 `main.py` 경로를 지정합니다.

```bash
python /path/to/this-repo/main.py commit
```

### 어떤 변경을 읽나요?

| 상황 | 사용하는 명령 | 설명 |
| --- | --- | --- |
| `git add`한 변경이 있음 | `git diff --cached` | 실제로 커밋될 내용만 요약합니다 |
| staged 변경이 없음 | `git diff HEAD` + 새 파일 | 작업 트리 전체 변경을 요약합니다 |
| `pr --base main` | `git diff main...HEAD` | 브랜치에서 이미 커밋한 변경을 요약합니다 |

### 옵션

| 옵션 | 기본값 | 설명 |
| --- | --- | --- |
| `--model` | `gemini-3.8-flash` | 사용할 Gemini 모델 |
| `--temperature` | `0.3` | 0.0~2.0. 낮을수록 같은 입력에 비슷한 결과, 높을수록 표현이 다양해집니다 |
| `--max-tokens` | `1024` | 최대 출력 토큰 수. 너무 작으면 응답이 중간에 잘립니다 |
| `--timeout` | `60` | 요청 제한 시간(초) |
| `--context "..."` | - | 변경 이유를 직접 알려 줍니다. PR의 Why 섹션 품질이 좋아집니다 |
| `--raw` | - | 구분선 없이 결과만 출력합니다 |
| `--dry-run` | - | AI를 호출하지 않고 전송될 프롬프트만 출력합니다 (비용 없음) |
| `--safe-mode` | 꺼짐 | 민감정보 마스킹 + 전송량 제한 ([6장](#6-안전-모드---safe-mode)) |
| `--max-files` | `10` | 안전 모드에서 보낼 최대 파일 수 |
| `--max-lines` | `200` | 안전 모드에서 보낼 최대 diff 줄 수 |
| `--mask-pattern REGEX` | - | 추가 마스킹 정규식 (여러 번 지정 가능) |
| `--base BRANCH` | - | (`pr` 전용) `<BRANCH>...HEAD` 기준으로 요약 |

`--max-files`, `--max-lines`, `--mask-pattern` 중 하나라도 주면 안전 모드가 자동으로 켜집니다.

### 생성 결과를 실제 커밋에 쓰기

로그(`[INFO]` 등)는 stderr로, 결과는 stdout으로 나갑니다. 그래서 결과만 파일로 받을 수 있습니다.

```bash
python main.py commit --raw > /tmp/msg.txt
```

내용을 확인하고 필요하면 고친 다음 커밋합니다.

```bash
git commit -F /tmp/msg.txt
```

## 4. 출력 예시

아래는 이 저장소에서 실제로 실행한 결과입니다.

### 커밋 메시지

커밋 본문 규칙을 보강한 변경(staged 파일 5개)에 실행한 결과입니다.

```text
$ python main.py commit --context "요구사항 4.3 커밋 본문 최소 품질 기준(불릿 1~2개, 파일 1~3개 언급)을 코드로 보장"
[INFO] Git status 수집 완료: 5개 파일 변경 감지 (staged 변경 기준)
         M  gitgen/cli.py
         M  gitgen/formatter.py
         M  gitgen/prompts.py
         M  tests/test_cli.py
         M  tests/test_formatter.py
[INFO] Git diff 수집 완료: 172줄
[INFO] AI API 요청 중... (model=gemini-3.8-flash, temperature=0.3, max_tokens=1024)
[INFO] 토큰 사용량: 입력 3349, 출력 73
[INFO] AI API 호출 횟수: 1회
[CHECK] 커밋 제목 36자 (권장 50자 / 최대 72자), 본문 불릿 2개 (최대 2개), 언급 파일 2개 (권장 1~3개)
[DONE] 커밋 메시지 생성 완료

--- Commit Message ---
feat: 커밋 본문 불릿 수 제한 및 파일 언급 검증 로직 추가

- `formatter.py`에 커밋 본문 최대 불릿 수(2개) 제한 및 언급 파일 수 집계 함수 추가
- `cli.py` 및 프롬프트에 커밋 본문 품질 기준 반영과 변경 파일 상세 로그 출력 추가
----------------------
```

### PR 제목/본문

첫 구현 변경(16개 파일)에 실행한 결과입니다. 변경 파일 목록 16줄은 생략했습니다.

```text
$ python main.py pr --context "커밋 메시지와 PR 설명을 매번 손으로 쓰는 시간을 줄이기 위해"
[INFO] 현재 브랜치: main
[INFO] Git status 수집 완료: 16개 파일 변경 감지 (작업 트리 전체 기준)
         (변경 파일 목록 16줄 생략)
[INFO] Git diff 수집 완료: 1594줄
[INFO] AI API 요청 중... (model=gemini-3.8-flash, temperature=0.3, max_tokens=1024)
[INFO] 토큰 사용량: 입력 21201, 출력 318
[INFO] AI API 호출 횟수: 1회
[CHECK] PR 제목 46자 (최대 80자), 섹션 불릿: Why 1개, What 5개, How to Test 3개
[DONE] PR 초안 생성 완료

--- PR Title ---
feat: Gemini 기반 Git 커밋 메시지 및 PR 초안 자동 생성 도구 구현

--- PR Body ---
## Why
- 커밋 메시지와 PR 설명을 매번 손으로 쓰는 시간을 줄이기 위해

## What
- Git 변경 사항을 수집하고 untracked 파일을 처리하는 `gitgen/git_collector.py` 추가
- 외부 SDK 의존 없이 표준 라이브러리(urllib)로 구현한 Gemini API 클라이언트 `gitgen/ai_client.py` 추가
- 민감 파일 제외 및 정규식 기반 개인정보/시크릿 마스킹을 수행하는 `gitgen/safe_mode.py` 추가
- AI 응답 파싱, 포맷팅 및 오류 시 1회 재생성/후처리를 담당하는 `gitgen/formatter.py`, `gitgen/prompts.py`, `gitgen/cli.py` 추가
- CLI 진입점 `main.py` 및 각 모듈 단위 테스트(`tests/test_*.py`) 추가

## How to Test
- `python3 -m unittest discover -s tests` 실행을 통해 단위 테스트 전체 통과 확인
- `python main.py commit --dry-run` 및 `python main.py pr --dry-run` 실행으로 프롬프트 생성 동작 확인
- `.env`에 `GEMINI_API_KEY`를 설정한 후 `python main.py commit` 또는 `python main.py pr`을 실행하여 커밋 및 PR 초안 출력 확인
----------------------
```

### 오류와 예외 상황

```text
# API Key 미설정
[ERROR] GEMINI_API_KEY 환경변수가 설정되지 않았습니다.
        예) export GEMINI_API_KEY="YOUR_KEY"

# 잘못된 API Key
[ERROR] AI API 호출 실패 - 인증 실패: API Key가 올바르지 않거나 권한이 없습니다. GEMINI_API_KEY 값을 확인하세요. (HTTP 400: API key not valid. Please pass a valid API key.)

# 없는 모델
[ERROR] AI API 호출 실패 - 모델을 찾을 수 없습니다: 'no-such-model'. --model 값을 확인하세요. (HTTP 404: ...)

# 변경 사항 없음
[INFO] 변경 사항이 없습니다. 커밋 메시지를 생성하지 않고 종료합니다.

# 프로젝트 루트가 아닌 곳에서 실행
[ERROR] 프로젝트 루트 디렉토리에서 실행하세요. (루트: /path/to/repo)

# max_tokens가 너무 작아 제목이 완성되지 않음
[ERROR] max_tokens 한도에 걸려 제목이 완성되지 않았을 수 있어 결과를 출력하지 않습니다. --max-tokens 값을 늘리세요.
```

네트워크 오류, 요청 시간 초과, 요청 한도 초과(429), 서버 오류(5xx), 안전 정책 차단도 원인을 담은 메시지를 출력하고 종료 코드 1로 끝납니다.

## 5. 출력 형식 규칙과 검증

| 항목 | 규칙 | 처리 방식 |
| --- | --- | --- |
| 커밋 제목 | 50자 이내 권장, 최대 72자 | 72자를 넘으면 단어 경계에서 자르고, 50자를 넘으면 경고합니다 |
| 커밋 본문 | 선택. 있으면 핵심 변경 불릿 1~2개 + 대표 파일/모듈 1~3개 언급 | 불릿 기호를 `- `로 통일합니다. 불릿이 2개를 넘으면 앞의 2개만 남기고, 언급한 파일 수를 `[CHECK]` 로그로 보여 줍니다 |
| PR 제목 | 최대 80자 | 넘으면 자릅니다 |
| PR 본문 | `## Why`, `## What`, `## How to Test` + 섹션마다 불릿 1개 이상 | 섹션이 없거나 비면 **1회 재생성**합니다. 그래도 비면 자리표시 불릿을 넣고 경고합니다 |

**재생성과 후처리를 함께 쓰는 이유**

- 제목 길이와 마침표처럼 코드로 확실히 고칠 수 있는 문제는 **후처리**합니다. 추가 비용이 없습니다.
- PR 섹션 누락처럼 내용을 새로 써야 하는 문제는 코드로 지어낼 수 없습니다. 그래서 무엇이 틀렸는지 알려 주고 **1회만 재생성**합니다.
- 재생성은 최대 1회입니다. 그래서 한 번 실행할 때 API 호출은 많아야 2회이고, 호출 횟수는 매번 로그로 출력됩니다.
- `max_tokens`에 걸려 응답이 잘리면 중간에 끊긴 마지막 불릿을 버리고 `[FIX]` 로그로 알려 줍니다. 제목 뒤에 아무것도 없어서 제목까지 끊겼을 수 있으면 결과를 출력하지 않고 오류로 끝냅니다.

## 6. 안전 모드 (`--safe-mode`)

`git diff`에는 API Key, 비밀번호, 개인정보가 섞여 들어갈 수 있습니다. 안전 모드를 켜면 diff를 외부 AI로 보내기 전에 아래 정책을 적용합니다.

### 정책

| 단계 | 기준 | 동작 |
| --- | --- | --- |
| 1. 민감 파일 제외 | `.env`, `.env.*` (`.env.example` 제외), `*.pem`, `*.key`, `*.p12`, `*.pfx`, `*.keystore`, `id_rsa*`, `id_ed25519*`, `credentials*` | 파일 이름만 남기고 diff 내용은 보내지 않습니다 |
| 2. 패턴 마스킹 | 아래 표의 기본 규칙 12개 + `--mask-pattern` | 일치한 부분을 `[MASKED:<규칙>]`으로 바꿉니다 |
| 3. 파일 수 제한 | 최대 **10개** 파일 (`--max-files`) | 넘는 파일은 생략하고 생략한 개수를 표시합니다 |
| 4. 줄 수 제한 | 최대 **200줄** (`--max-lines`) | 넘는 줄은 생략하고 생략한 줄 수를 표시합니다 |

| 규칙 이름 | 대상 |
| --- | --- |
| `private_key` | `-----BEGIN ... PRIVATE KEY-----` 블록 |
| `google_api_key` | `AIza`로 시작하는 39자 키 |
| `openai_anthropic_key` | `sk-`, `sk-ant-`, `sk-proj-` 키 |
| `github_token` | `ghp_`, `gho_`, `github_pat_` 등 |
| `aws_access_key` | `AKIA` / `ASIA` + 16자 |
| `slack_token` | `xoxb-`, `xoxp-` 등 |
| `jwt` | `eyJ...` 형태의 JWT |
| `secret_literal` | `password = "값"`처럼 이름에 key/secret/token/password가 들어간 변수에 문자열을 넣는 코드 (값만 가림) |
| `env_secret` | `.env` 스타일의 `API_TOKEN=값` (값만 가림) |
| `email` | 이메일 주소 |
| `kr_rrn`, `kr_phone` | 주민등록번호, 휴대전화 번호 |

`max_tokens = args.max_tokens` 같은 일반 코드는 가리지 않도록, 비밀값 규칙은 **문자열 리터럴**이나 **대문자 환경변수 대입**에만 적용합니다.

안전 모드를 켜지 않아도 diff가 60,000자를 넘으면 앞부분만 보내고 경고합니다. 비용과 요청 한도를 지키기 위해서입니다.

### 안전 모드 ON/OFF 비교

가짜 비밀값이 들어 있는 테스트 저장소(새 파일 14개, diff 114줄)에서 `--dry-run`으로 실제 전송될 내용을 비교했습니다.

```bash
python main.py commit --dry-run
```

```bash
python main.py commit --dry-run --safe-mode
```

| 전송 내용 | OFF | ON |
| --- | --- | --- |
| `.env` | `+SECRET_TOKEN=example-secret-value` | `(safe-mode: 민감 파일로 판단되어 내용을 전송하지 않음)` |
| Google API Key | `+GEMINI_KEY = "AIzaSyFAKE_EXAMPLE_KEY_1234567890abcdEF"` | `+GEMINI_KEY = "[MASKED:google_api_key]"` |
| 이메일 | `+ADMIN_EMAIL = "admin@example.com"` | `+ADMIN_EMAIL = "[MASKED:email]"` |
| 비밀번호 | `+DB_PASSWORD = "p@ssw0rd-example"` | `+DB_PASSWORD = "[MASKED:secret_literal]"` |
| 전화번호 | `+SUPPORT_PHONE = "010-1234-5678"` | `+SUPPORT_PHONE = "[MASKED:kr_phone]"` |
| 일반 설정값 | `+MAX_TOKENS = 1024` | `+MAX_TOKENS = 1024` (그대로) |
| 전송량 | 14개 파일 / 114줄 | 10개 파일 / 77줄 (`4개 파일 생략`) |

ON일 때 출력되는 요약 로그:

```text
[SAFE] 마스킹 4건(google_api_key 1, secret_literal 1, email 1, kr_phone 1), 민감 파일 제외 1개, 전송 파일 10/14, 전송 줄 77/114
[SAFE] 내용 제외 파일: .env
```

정책을 조정한 예시입니다. 사내 규칙을 추가하고 전송량을 더 줄입니다.

```bash
python main.py commit --dry-run --max-files 3 --max-lines 30 --mask-pattern 'MAX_TOKENS = \d+'
```

```text
[SAFE] 마스킹 5건(google_api_key 1, secret_literal 1, email 1, kr_phone 1, custom_1 1), 민감 파일 제외 1개, 전송 파일 3/14, 전송 줄 21/114
```

> 마스킹은 알려진 패턴만 잡습니다. 모든 민감정보를 막는다고 보장할 수 없습니다. 민감한 저장소에서는 `--dry-run`으로 전송 내용을 먼저 확인하세요.

## 7. 파라미터가 결과에 주는 영향

| 파라미터 | 낮게 | 높게 | 이 도구의 기본값 |
| --- | --- | --- | --- |
| `temperature` | 같은 diff에 거의 같은 문장이 나옵니다. 규칙을 잘 지킵니다 | 단어 선택과 문장 구성이 실행마다 달라집니다. 규칙을 어길 가능성이 커집니다 | `0.3`: 커밋 메시지는 창의성보다 일관성이 중요해서 낮게 잡았습니다 |
| `max_tokens` | 응답이 중간에 잘립니다. 잘린 불릿은 버리고, 제목까지 잘렸을 수 있으면 오류로 끝냅니다 | 길이 제한이 넉넉해집니다. 실제 길이는 프롬프트 규칙(불릿 개수)이 정합니다 | `1024`: 실측 출력이 커밋 약 140토큰, PR 약 320토큰이라 여유를 2~3배 이상 두었습니다 |

4장의 커밋 예시와 같은 변경에서 `--max-tokens 40`으로 실행하면 응답이 잘립니다. 미완성 불릿은 버리고 제목만 남습니다. 기본값(1024)으로 실행했을 때는 불릿 2개가 나왔습니다.

```text
[WARN] max_tokens 한도에 도달해 응답이 잘렸습니다. 필요하면 --max-tokens 값을 늘리세요.
[INFO] 토큰 사용량: 입력 3302, 출력 36
[FIX] 응답이 잘려 미완성 불릿을 제거했습니다: 'formatter.py에 본문 불릿을 최대 2개로 제한하고 파일'
[CHECK] 커밋 제목 34자 (권장 50자 / 최대 72자), 본문 불릿 0개 (최대 2개), 언급 파일 0개 (권장 1~3개)

--- Commit Message ---
feat: 커밋 본문 불릿 수 제한 및 파일 언급 검증 추가
----------------------
```

Gemini flash 모델은 답하기 전에 "생각(thinking)" 토큰을 수백 개 쓰는데, 이 토큰도 `max_tokens`에서 빠집니다. 그래서 flash 모델을 쓸 때는 thinking을 끕니다(`thinkingBudget: 0`). pro 모델은 thinking을 끌 수 없으니 `--max-tokens`를 넉넉히 주세요.

## 8. 비용과 사용 권장 사항

- 한 번 실행할 때 API 호출은 기본 **1회**, 형식 오류가 있을 때만 **최대 2회**입니다. 호출 횟수와 토큰 사용량은 매번 로그에 나옵니다.
- 입력 토큰은 diff 크기에 비례합니다. 위 예시는 1,594줄 diff에 입력 약 21,000토큰이 들었습니다. 큰 변경에서는 `--safe-mode`의 파일/줄 제한으로 전송량을 줄이세요.
- 커밋은 작은 단위로 나눠 `git add`한 뒤 실행하면 비용이 줄고 요약 품질도 좋아집니다.
- 프롬프트를 확인하거나 테스트할 때는 `--dry-run`을 쓰세요. API를 호출하지 않습니다.
- 요청 한도 초과(429)가 나면 잠시 기다렸다가 다시 실행하세요. 도구가 자동으로 재시도하지 않는 이유는 호출 횟수를 예측할 수 있게 하기 위해서입니다.
- 생성된 문구는 **초안**입니다. AI는 diff에 없는 배경(Why)을 추측할 수 있으니 반드시 검토한 뒤 사용하세요.

## 9. 프로젝트 구조

```text
main.py                  # 진입점 (Python 버전 확인 후 cli.run 호출)
gitgen/
  cli.py                 # 인자 해석과 전체 흐름 조립, 로그/결과 출력
  git_collector.py       # git status / git diff 실행과 결과 정리
  safe_mode.py           # 민감 파일 제외, 패턴 마스킹, 전송량 제한
  prompts.py             # system/user 프롬프트 구성
  ai_client.py           # Gemini REST 호출, 응답 파싱, 오류 분류
  formatter.py           # 출력 파싱, 형식 검증, 후처리, 렌더링
tests/                   # 단위 테스트 (AI는 mock 처리, Git은 임시 저장소 사용)
```

각 모듈은 하나의 역할만 맡습니다. 예를 들어 `git_collector`는 AI를 모르고, `ai_client`는 Git을 모릅니다. 모듈을 조립하는 곳은 `cli.py` 하나뿐입니다. 그래서 AI 제공자를 바꿀 때는 `ai_client.py`와 `cli.py`의 연결 부분만 고치면 되고, 각 부분을 API 비용 없이 따로 테스트할 수 있습니다.

## 10. 테스트

```bash
python -m unittest discover -s tests -t .
```

API를 호출하지 않습니다. Git 관련 테스트는 임시 저장소를 만들어 실제 `git` 명령으로 검증합니다.
