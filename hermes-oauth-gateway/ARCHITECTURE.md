# Hermes OAuth Gateway — 아키텍처 상세 설계

**Document Version**: 1.0  
**Date**: 2026-05-10  
**GitHub Issue**: [#13](https://github.com/hnabyz-bot/abyz-lab-pm/issues/13)

## 목차
1. [설계 원칙](#설계-원칙)
2. [전체 아키텍처](#전체-아키텍처)
3. [컴포넌트 상세](#컴포넌트-상세)
4. [데이터 흐름](#데이터-흐름)
5. [보안 모델](#보안-모델)
6. [확장성 고려사항](#확장성-고려사항)

## 설계 원칙

### 1. API 과금 제로 (Zero-Cost LLM API)
- 종량제 OpenAI/Anthropic API 키 대신 기존 구독료 (ChatGPT Pro, Copilot Pro) 활용
- OAuth 토큰을 직접 관리하지 않음 → CLI subprocess를 통해 공식 인증 사용
- 법적 위험 회피: ToS 위반 경로 제외 (Claude Code OAuth, Gemini OAuth 등)

### 2. OpenAI-Compatible API
- 기존 OpenAI SDK/클라이언트 코드 호환성 유지
- `/v1/chat/completions`, `/v1/models` 표준 엔드포인트
- JSON 응답 스키마 호환

### 3. 안전한 인증 (Secure OAuth)
- 토큰을 메모리에 보관하지 않음 → CLI subprocess가 기본 인증 사용
- keyring/DBus secret-service를 통한 토큰 저장 (systemd 환경변수 필수)
- 요청 기반 토큰 조회 (per-request OAuth)

### 4. 확장 가능한 라우팅 (Pattern-based Routing)
- routes.yaml을 통한 모델명 → track 패턴 매칭
- 새 CLI/모델 추가 시 코드 변경 최소화
- fnmatch를 통한 유연한 패턴 지원

## 전체 아키텍처

```
[Client Layer]
  ├─ n8n (workflow)
  ├─ Hermes Agent
  └─ Custom API (curl 등)
        │
        │ HTTP POST /v1/chat/completions
        │ Authorization: Bearer sk-hermes-*
        ▼
[API Gateway Layer]
  FastAPI (asyncio)
    ├─ Request validation
    ├─ Key verification
    ├─ Message extraction
    ├─ Route resolution
    └─ Async subprocess dispatch
        │
        ├─ Track A (Codex CLI)        Track B (Copilot CLI)
        │      │                           │
        ▼      ▼                           ▼
[CLI Execution Layer]
    codex exec --json       gh copilot -p --allow-all-tools
        │                            │
        ▼                            ▼
[OAuth/Auth Layer]
    ~/.codex/auth.json          ~/.copilot/auth.json
    (Codex OAuth token)         (Copilot OAuth token)
    ChatGPT Pro (hnabyz)        Copilot Pro (holee9)
        │                            │
        ▼                            ▼
[LLM Service]
    OpenAI (gpt-5.5)         GitHub Copilot (claude-sonnet-4, ...)
        │                            │
        └────────────┬───────────────┘
                     │
                     ▼
[Response Parsing]
    JSONL parser (Codex)
    Text parser (Copilot)
        │
        ▼
[OpenAI-Compatible Response]
    {
      "id": "chatcmpl-...",
      "choices": [{"message": {"content": "..."}}],
      "usage": {...}
    }
        │
        ▼
[Logging & Analytics]
    SQLite sessions.db
    ├─ Track A metrics
    ├─ Track B metrics
    └─ Per-key usage
        │
        ▼
[Client Response]
```

## 컴포넌트 상세

### 1. gateway.py (FastAPI 애플리케이션)

**책임:**
- HTTP 요청 수신 및 검증
- Bearer token 인증
- 모델 라우팅 해석
- Subprocess 비동기 실행
- OpenAI-compatible JSON 응답 생성
- SQLite 로깅

**주요 함수:**
```python
async def verify_key(authorization: str) -> str
  # Bearer token 검증

def resolve_route(model: str) -> dict
  # routes.yaml 기반 track 결정

async def chat_completions(request: dict, key: str) -> dict
  # 메인 엔드포인트
  # 1. 메시지 추출
  # 2. 라우팅 결정
  # 3. codex_driver / copilot_driver 호출
  # 4. 응답 변환
  # 5. 로깅

@app.get("/v1/models")
async def list_models(key: str) -> dict
  # routes.yaml의 모든 모델 노출
```

**asyncio 사용 이유:**
- 다중 동시 요청 처리 (n8n workflows 병렬)
- CLI subprocess 기다리는 동안 다른 요청 처리
- 단일 스레드 Python 이벤트 루프로 GIL 회피

### 2. codex_driver.py (Codex CLI 관리)

**책임:**
- Codex subprocess 생성 및 실행
- JSONL 스트림 파싱
- Token 정보 추출 (turn.completed 이벤트)
- 타임아웃/에러 처리
- 응답 정규화

**JSONL 이벤트 스키마:**
```json
{"type":"thread.started","thread_id":"..."}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"..."}}
{"type":"turn.completed","usage":{"input_tokens":N,"output_tokens":M}}
```

**주요 함수:**
```python
async def run_codex_exec(prompt: str, model: str, timeout: int) -> dict
  # {
  #   "text": "최종 응답",
  #   "input_tokens": N,
  #   "output_tokens": M
  # }
```

**제약사항:**
- ChatGPT 계정 모드: `-m` 플래그 불지원 (gpt-5.5만 사용)
- 외부 모델 지정 불가 → routes.yaml에서 upstream_model 고정

### 3. copilot_driver.py (Copilot CLI 관리)

**책임:**
- Copilot CLI subprocess 생성
- Text 응답 파싱
- DBus/keyring 환경변수 주입 (systemd 호환성)
- 타임아웃/에러 처리

**주요 함수:**
```python
async def run_copilot(prompt: str, timeout: int = 60) -> dict
  # gh copilot -p "<prompt>" --allow-all-tools
  # {
  #   "text": "응답",
  #   "input_tokens": 0,  # 아직 파싱 안 됨
  #   "output_tokens": 0
  # }
```

**주의사항:**
- Copilot CLI는 JSON 아님 → text로 응답
- Token 정보 미노출 (향후 정규식 파서 추가 예정)
- `--allow-all-tools` 플래그로 shell/code 모든 응답 허용

### 4. session_store.py (SQLite 로깅)

**테이블 구조:**
```sql
CREATE TABLE requests (
  id INTEGER PRIMARY KEY,
  api_key TEXT,           -- sk-hermes-dev / sk-hermes-n8n
  model TEXT,             -- 요청 모델명
  track TEXT,             -- codex_cli / copilot_cli
  input_tokens INTEGER,   -- 입력 토큰 (0 if unavailable)
  output_tokens INTEGER,  -- 출력 토큰
  created_at REAL         -- Unix timestamp
);
```

**쓰기:**
```python
def log_request(api_key: str, model: str, track: str, input_tokens: int, output_tokens: int)
  # SQLite INSERT (thread-safe lock 사용)
```

**조회 (운영용):**
```sql
SELECT track, COUNT(*) FROM requests GROUP BY track;
SELECT api_key, COUNT(*) FROM requests GROUP BY api_key;
SELECT model, AVG(input_tokens), AVG(output_tokens) FROM requests GROUP BY model;
```

### 5. routes.yaml (라우팅 규칙)

**구조:**
```yaml
default: codex_cli  # 기본값

models:
  - match: "패턴"        # fnmatch 와일드카드
    track: "track_name"  # codex_cli / copilot_cli
    upstream_model: "..." # 외부 모델명

tracks:
  codex_cli:
    bin: "..."
    timeout: N
    skip_git_repo_check: true
  copilot_cli:
    bin: "..."
    timeout: N
```

**패턴 매칭:**
- `gpt-5*` → gpt-5, gpt-5-latest, gpt-5-preview 등
- `claude-*` → claude-sonnet-4, claude-opus 등
- `*-latest` → 모든 -latest 모델

## 데이터 흐름

### 정상 흐름 (Happy Path)

```
1. Client Request
   POST /v1/chat/completions
   {
     "model": "claude-sonnet-4",
     "messages": [{"role": "user", "content": "Hi"}]
   }

2. Authentication
   Bearer sk-hermes-dev 확인
   VALID_KEYS 검증

3. Routing
   routes.yaml: match "claude-sonnet-*" → track: copilot_cli

4. Message Extraction
   마지막 user 메시지: "Hi"

5. CLI Execution
   await run_copilot("Hi", timeout=60)
   └─ subprocess: gh copilot -p "Hi" --allow-all-tools
   └─ stdout: "Sure, hi there! How can I help you?"

6. Response Transform
   {
     "text": "Sure, hi there! How can I help you?",
     "input_tokens": 0,
     "output_tokens": 0
   }

7. OpenAI Format
   {
     "id": "chatcmpl-xyz123",
     "object": "chat.completion",
     "model": "claude-sonnet-4",
     "choices": [{
       "message": {"role": "assistant", "content": "Sure..."}
     }],
     "usage": {"prompt_tokens": 0}
   }

8. Logging
   INSERT INTO requests (api_key, model, track, ...) VALUES (...)

9. Response Send
   HTTP 200 + JSON
```

### 에러 흐름

```
Scenario A: Invalid Key
  2. Authentication FAIL
  └─ HTTP 401 Unauthorized
  └─ Log: (로그 안 함)

Scenario B: Unknown Model
  3. Routing FAIL
  └─ Track not found
  └─ HTTP 400 Bad Request
  └─ Message: "Unknown track"

Scenario C: CLI Timeout
  5. CLI Execution
  └─ asyncio.TimeoutError after 60s
  └─ Return: {"text": "[Copilot timeout]", "input_tokens": 0}
  └─ HTTP 200 (응답으로 반환)
  └─ Log: OK (timeout을 콘텐츠로 표기)

Scenario D: CLI Error
  5. CLI Execution
  └─ subprocess returncode != 0
  └─ stderr: "Copilot CLI not installed"
  └─ Return: {"text": "[Copilot error: ...]"}
  └─ HTTP 200
  └─ Log: OK
```

## 보안 모델

### 1. 인증 (Authentication)

**Mechanism**: Bearer Token (sk-hermes-*)
```
Authorization: Bearer sk-hermes-dev
                       └─ 40-char random token
```

**Verification**:
```python
if not authorization.startswith("Bearer "):
    raise 401 Unauthorized
key = authorization[7:]  # "sk-hermes-dev"
if key not in VALID_KEYS:
    raise 401 Unauthorized
```

**장점:**
- HTTP Bearer 표준 준수
- OpenAI API와 호환
- 간단하고 stateless

**한계:**
- URL에 노출 위험 (HTTPS 필수, 현재 미지원)
- Token 로테이션 메커니즘 없음 (향후 추가)
- 하드코딩 (현재) → .env 로드로 개선 필요

### 2. OAuth 인증 (CLI 레벨)

**Codex:**
- ~/.codex/auth.json (파일 기반)
- ChatGPT Pro 계정 OAuth token 저장
- Codex CLI가 자동 로드

**Copilot:**
- ~/.copilot/auth.json 또는 ~/.config/gh (gh-copilot 통합)
- GitHub Copilot Pro 계정 OAuth token 저장
- systemd에 XDG_RUNTIME_DIR, DBUS_SESSION_BUS_ADDRESS 필수 (keyring 접근)

**특징:**
- Gateway가 토큰을 직접 다루지 않음 (CLI가 관리)
- Token 만료 시 CLI에서만 재인증
- 각 subprocess가 독립적인 인증 세션

### 3. 메시지 유효성 검증

```python
if not messages:
    raise 400 Bad Request ("messages required")

user_message = None
for msg in reversed(messages):
    if msg.get("role") == "user":
        user_message = msg.get("content", "")
        break

if not user_message:
    raise 400 Bad Request ("No user message")
```

### 4. Subprocess 샌드박싱 (제한사항)

**현재 미구현:**
- stdin/stdout 격리: DEVNULL 사용으로 stdin 차단, 임시 완화
- 디렉토리 제한: subprocess는 호스트 전체 접근 가능
- 리소스 제한: 타임아웃만 구현 (CPU/메모리 한계 없음)

**향후 개선:**
- 컨테이너/chroot 격리 (Docker 활용)
- ulimit 설정 (메모리/CPU 제한)
- 디렉토리 whitelist (특정 경로만 접근)

### 5. 로깅 & 감시

**현재:**
- SQLite: plaintext 로깅 (암호화 없음)
- journalctl: systemd 로그에 요청 기록

**향후:**
- 요청/응답 암호화 (SQLite encryption)
- 민감한 정보 마스킹 (token, password 등)
- 감시 알림 (비정상 트래픽 탐지)

## 확장성 고려사항

### 1. 새 CLI 트랙 추가

**Step 1: Driver 작성**
```python
# new_driver.py
async def run_new_cli(prompt: str, timeout: int) -> dict:
    # subprocess 실행 및 파싱
    return {"text": "...", "input_tokens": 0, "output_tokens": 0}
```

**Step 2: gateway.py 수정**
```python
from new_driver import run_new_cli

# chat_completions 함수에 분기 추가
elif route["track"] == "new_track":
    result = await run_new_cli(prompt)
```

**Step 3: routes.yaml 수정**
```yaml
models:
  - match: "new-model-*"
    track: new_track
    upstream_model: "{model}"

tracks:
  new_track:
    bin: "/path/to/cli"
    timeout: 120
```

**Step 4: 재시작**
```bash
sudo systemctl restart hermes-oauth-gateway
```

### 2. 마이크로서비스 분리 (향후)

현재: 단일 FastAPI 프로세스
```
Client → FastAPI (gateway.py)
         ├─ codex_driver
         ├─ copilot_driver
         └─ session_store
```

향후: 마이크로서비스 아키텍처
```
Client → API Gateway (authentication, routing)
         ├─ Codex Service (codex_driver)
         ├─ Copilot Service (copilot_driver)
         ├─ Session Service (SQLite → Redis/PostgreSQL)
         └─ Analytics Service (Grafana)
```

**이점:**
- 독립적 스케일링 (Codex 부하 > Copilot)
- 장애 격리 (한 CLI 문제가 다른 cli에 영향 없음)
- 다중 인스턴스 배포

### 3. 캐싱 전략 (향후)

**현재:** 없음 (모든 요청이 CLI 실행)

**향후:**
```python
# Redis 캐시
cache.get(f"{model}:{hash(prompt)}")
if not cached:
    result = await run_cli(prompt)
    cache.set(f"{model}:{hash(prompt)}", result, ttl=3600)
```

**고려사항:**
- 동일 prompt에 동일 응답? (아니면 스트리밍/multi-turn 필요)
- Cache invalidation (모델 업데이트 시)
- 메모리 사용량

---

**End of Document**
