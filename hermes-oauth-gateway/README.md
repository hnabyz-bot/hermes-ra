# Hermes OAuth Gateway

**OpenAI-compatible API gateway for Hermes Agent and n8n**  
ChatGPT Pro (Codex CLI) + GitHub Copilot Pro (Copilot CLI) 구독을 활용한 API 과금 제로 LLM 게이트웨이

**GitHub Issue**: [#13 Hermes 구독형 OAuth LLM 게이트웨이](https://github.com/hnabyz-bot/abyz-lab-pm/issues/13)  
**Status**: Phase 0-5 Complete (2026-05-10)  
**Gateway**: http://localhost:5055 (production) | port 5055

---

## 목차

- [개요](#개요)
- [아키텍처](#아키텍처)
- [설치](#설치)
- [설정](#설정)
- [API 엔드포인트](#api-엔드포인트)
- [n8n 통합](#n8n-통합)
- [운영 & 모니터링](#운영--모니터링)
- [트러블슈팅](#트러블슈팅)
- [향후 계획](#향후-계획)

---

## 개요

Hermes OAuth Gateway는 **API 과금 없이** ChatGPT Pro와 GitHub Copilot Pro 구독을 활용하여 Hermes Agent와 n8n에 LLM 기능을 제공합니다.

**핵심 가치:**
- API 키 종량제 없음 (구독료만 사용)
- OpenAI-compatible REST API (기존 OpenAI 코드 호환)
- 다중 모델 지원 (GPT-5, O3, Claude, Gemini)
- 안전한 OAuth 기반 인증 (공식 CLI를 통한 subprocess 호출)
- SQLite 기반 세션 로깅 및 통계

**제약사항:**
- Codex CLI: ChatGPT Pro 기본 모델만 지원 (gpt-5.5)
- Copilot CLI: Copilot Pro 구독 계정 필요
- OAuth 토큰: ~7일마다 재인증 필요

---

## 아키텍처

```
┌─────────────────────────────────────────┐
│  Client (n8n, Hermes Agent)              │
│  POST /v1/chat/completions               │
│  Authorization: Bearer sk-hermes-*       │
└────────────────┬────────────────────────┘
                 │
         ┌───────▼────────┐
         │  FastAPI       │
         │  Gateway :5055 │
         │  (asyncio)     │
         └───┬────────────┘
             │
    ┌────────┴─────────┐
    │                  │
┌───▼──────┐      ┌────▼──────────┐
│ Codex    │      │  Copilot CLI   │
│ CLI v1   │      │  (gh copilot)  │
│(gpt-5.5) │      │ (claude-*/...)│
└────┬─────┘      └────┬──────────┘
     │                 │
┌────▼────┐      ┌─────▼──────┐
│ChatGPT  │      │ GitHub      │
│ Pro     │      │ Copilot Pro │
│(hnabyz) │      │ (holee9)    │
└─────────┘      └────────────┘

SQLite: sessions.db
├─ requests (api_key, model, track, tokens, created_at)
└─ (확장 테이블 예정)

Config: routes.yaml (모델 → track 라우팅)
```

**작동 흐름:**
1. Client가 `/v1/chat/completions`로 요청 (model: claude-sonnet-4 등)
2. Gateway가 routes.yaml에서 track 결정 (codex_cli vs copilot_cli)
3. 해당 track의 CLI subprocess 비동기 실행
4. 응답을 OpenAI-compatible JSON으로 변환
5. SQLite에 요청 로깅
6. Client에 반환

---

## 설치

### 사전 요구사항

- **Host**: Linux (Raspberry Pi 5 / Ubuntu 22.04 등)
- **Python**: 3.11+
- **CLI 도구:**
  - `codex` v0.128.0+ (Codex CLI, ChatGPT Pro 인증 완료)
  - `gh` v2.92.0+ (GitHub CLI, holee9 계정 등록)
  - `git`, `systemctl`, `sudo`

### 설치 단계

**1. 저장소 클론 (이미 존재할 경우 스킵)**
```bash
cd /home/raspi5p/workspace/n8n-stack
git clone https://github.com/hnabyz-bot/abyz-lab-pm.git  # 또는 기존 경로 사용
cd hermes-oauth-gateway
```

**2. Python 가상환경 설정**
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

**3. CLI 인증 (사전 완료, 재확인용)**

**Codex CLI (ChatGPT Pro):**
```bash
# 이미 인증됨 (hnabyz-bot 계정, ~/.codex/auth.json)
/home/raspi5p/.hermes/node/bin/codex --version
/home/raspi5p/.hermes/node/bin/codex exec --json "2+2" 2>&1 | head -10
```

**GitHub Copilot CLI (Copilot Pro):**
```bash
# holee9 계정으로 OAuth 인증됨 (~/.copilot/auth.json)
/home/raspi5p/.hermes/node/bin/copilot --version
/home/raspi5p/.hermes/node/bin/copilot -p "list files" --allow-all-tools 2>&1 | head -10
```

**4. systemd 서비스 등록**
```bash
sudo cp hermes-oauth-gateway.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable hermes-oauth-gateway
sudo systemctl start hermes-oauth-gateway

# 확인
sudo systemctl status hermes-oauth-gateway
```

**5. 헬스 체크**
```bash
curl -s http://localhost:5055/health | python3 -m json.tool
# 예상: {"status": "ok"}
```

---

## 설정

### routes.yaml

모델명 → CLI track 매핑. 패턴 매칭으로 자동 라우팅됩니다.

```yaml
default: codex_cli  # 기본값: Codex track

models:
  # Track A: Codex CLI (ChatGPT Pro)
  - match: "gpt-5*"
    track: codex_cli
    upstream_model: "{model}"
    # 예: gpt-5 → Codex CLI의 gpt-5.5 기본값 사용
    #    gpt-5-latest → gpt-5.5

  - match: "o3*"
    track: codex_cli
    upstream_model: "{model}"

  - match: "gpt-4*"
    track: codex_cli
    upstream_model: "{model}"

  # Track B: Copilot CLI (GitHub Copilot Pro)
  - match: "claude-sonnet-*"
    track: copilot_cli
    upstream_model: "claude-sonnet-4"

  - match: "claude-*"
    track: copilot_cli
    upstream_model: "{model}"

  - match: "gemini-*"
    track: copilot_cli
    upstream_model: "{model}"

tracks:
  codex_cli:
    bin: "/home/raspi5p/.hermes/node/bin/codex"
    timeout: 120
    skip_git_repo_check: true

  copilot_cli:
    bin: "gh"
    timeout: 60
```

**모델 추가 방법:**
1. routes.yaml에 새 `match` 규칙 추가
2. Gateway 재시작: `sudo systemctl restart hermes-oauth-gateway`
3. `/v1/models` 엔드포인트에서 자동 노출

### API 키 관리

`gateway.py` 내 `VALID_KEYS`:

```python
VALID_KEYS = {"sk-hermes-dev", "sk-hermes-n8n"}
```

**새 키 추가:**
```python
VALID_KEYS = {"sk-hermes-dev", "sk-hermes-n8n", "sk-hermes-custom"}
```

> **보안**: 프로덕션에서는 `~/.hermes/.env` 같은 환경 파일에서 로드하도록 수정 권장.

---

## API 엔드포인트

### POST /v1/chat/completions

OpenAI API와 호환되는 채팅 엔드포인트.

**요청:**
```bash
curl -X POST http://localhost:5055/v1/chat/completions \
  -H "Authorization: Bearer sk-hermes-dev" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5",
    "messages": [
      {"role": "user", "content": "Hello, tell me a joke"}
    ],
    "temperature": 0.7
  }'
```

**응답:**
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1715339400,
  "model": "gpt-5",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Why did the AI go to school? To improve its learning model!"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 15097,
    "completion_tokens": 23,
    "total_tokens": 15120
  }
}
```

**파라미터:**
| 파라미터 | 타입 | 설명 |
|---|---|---|
| `model` | string | 모델명 (gpt-5, claude-sonnet-4, gemini-* 등) |
| `messages` | array | 메시지 배열 `[{"role": "user", "content": "..."}, ...]` |
| `temperature` | float | (선택) 응답 다양성 (0-1, 기본값 0.7) |

**응답 코드:**
- `200 OK` — 성공
- `400 Bad Request` — 파라미터 오류
- `401 Unauthorized` — 키 오류
- `503 Service Unavailable` — Gateway 서비스 오류

### GET /v1/models

지원 모델 목록 반환.

```bash
curl -s http://localhost:5055/v1/models \
  -H "Authorization: Bearer sk-hermes-dev" | python3 -m json.tool
```

**응답:**
```json
{
  "object": "list",
  "data": [
    {
      "id": "gpt-5-latest",
      "object": "model",
      "created": 0,
      "owned_by": "hermes-oauth-gateway"
    },
    {
      "id": "claude-sonnet-4",
      "object": "model",
      "created": 0,
      "owned_by": "hermes-oauth-gateway"
    }
  ]
}
```

### GET /health

서비스 상태 확인.

```bash
curl -s http://localhost:5055/health
# {"status": "ok"}
```

---

## n8n 통합

### Credential 설정

n8n UI (http://localhost:3000) → **Settings → Credentials → OpenAI (또는 Create New):**

| 필드 | 값 |
|---|---|
| **Display name** | Hermes Gateway |
| **API Key** | `sk-hermes-n8n` |
| **Base URL** | `http://host.docker.internal:5055/v1` |
| **Models** | (선택사항, 자동 로드 가능) |

**중요**: Base URL은 반드시 `v1` 경로 포함!

### Workflow 예제

**Workflow**: "Hermes Gateway Test"

**Nodes:**
1. **Manual Trigger** (수동 시작)
2. **OpenAI Chat** node:
   - Credential: `Hermes Gateway` (위에서 생성)
   - Model: `gpt-5` (또는 `claude-sonnet-4`)
   - Messages:
     ```json
     [
       {
         "role": "user",
         "content": "{{ $input.first().json.question }}"
       }
     ]
     ```
3. **Debug Output** (결과 확인)

**실행 결과:**
```json
{
  "message": "제시한 질문에 대한 답변...",
  "usage": {}
}
```

### Docker 내부 검증

```bash
# n8n 컨테이너에서 gateway 접근 확인
docker exec n8n-stack-n8n-1 wget -qO- \
  http://host.docker.internal:5055/health | python3 -m json.tool
```

---

## 운영 & 모니터링

### 로그 확인

**실시간 로그:**
```bash
journalctl -u hermes-oauth-gateway -f --no-pager
```

**최근 로그:**
```bash
journalctl -u hermes-oauth-gateway -n 100
```

**에러만 필터:**
```bash
journalctl -u hermes-oauth-gateway -p err
```

### 세션 통계

**Track별 요청 수:**
```bash
sqlite3 /home/raspi5p/workspace/n8n-stack/hermes-oauth-gateway/sessions.db << 'EOF'
SELECT
  track,
  COUNT(*) as requests,
  SUM(input_tokens) as total_input_tokens,
  SUM(output_tokens) as total_output_tokens,
  AVG(input_tokens) as avg_input,
  AVG(output_tokens) as avg_output
FROM requests
GROUP BY track
ORDER BY requests DESC;
EOF
```

**API 키별 통계:**
```bash
sqlite3 /home/raspi5p/workspace/n8n-stack/hermes-oauth-gateway/sessions.db << 'EOF'
SELECT
  api_key,
  COUNT(*) as requests,
  MIN(created_at) as first_use,
  MAX(created_at) as last_use
FROM requests
GROUP BY api_key
ORDER BY requests DESC;
EOF
```

### 서비스 관리

**상태 확인:**
```bash
systemctl status hermes-oauth-gateway
```

**재시작:**
```bash
sudo systemctl restart hermes-oauth-gateway
```

**활성화/비활성화:**
```bash
sudo systemctl enable hermes-oauth-gateway   # 부팅 시 자동 시작
sudo systemctl disable hermes-oauth-gateway  # 자동 시작 해제
```

**로그 저장:**
```bash
journalctl -u hermes-oauth-gateway -p err > /tmp/gateway-errors.log
```

---

## 트러블슈팅

### 503 Service Unavailable

**증상**: `curl: (7) Failed to connect to localhost port 5055`

**진단:**
```bash
systemctl status hermes-oauth-gateway
journalctl -u hermes-oauth-gateway -n 50 --no-pager
netstat -tlnp 2>/dev/null | grep 5055
```

**해결:**
```bash
# 서비스 재시작
sudo systemctl restart hermes-oauth-gateway

# 포트 점유 확인 및 해제
sudo lsof -i :5055
sudo kill -9 <PID>
```

### 401 Unauthorized

**증상**: `{"detail": "Invalid key"}`

**원인**: API 키 오류 또는 Bearer 형식 오류

**확인:**
```bash
# 키 형식 확인
curl http://localhost:5055/v1/models \
  -H "Authorization: Bearer sk-hermes-dev"
# 정상: 200 + 모델 목록
```

### Timeout (120초 이상)

**증상**: `[Codex timeout]` 또는 `[Copilot timeout]`

**원인**: 장시간 요청 또는 CLI 응답 지연

**해결:**
```yaml
# routes.yaml에서 timeout 증가
tracks:
  codex_cli:
    timeout: 300  # 120 → 300초
```

재시작:
```bash
sudo systemctl restart hermes-oauth-gateway
```

### OAuth 토큰 만료

**증상**: Codex/Copilot 응답 없음, "No authentication information found"

**원인**: OAuth 토큰 ~7일 만료

**해결:**

**Codex (ChatGPT Pro):**
```bash
/home/raspi5p/.hermes/node/bin/codex login
# 브라우저에서 ChatGPT Pro로 로그인 후 승인
```

**Copilot (GitHub Copilot Pro):**
```bash
# holee9 계정으로 로그인
gh auth switch holee9
# (이미 인증됨, 필요시 재인증)
```

재시작:
```bash
sudo systemctl restart hermes-oauth-gateway
```

### n8n에서 "Cannot resolve host"

**증상**: n8n workflow에서 credential test 실패

**원인**: Docker extra_hosts 미설정 또는 gateway 서비스 미시작

**해결:**
```bash
# 1. gateway 서비스 확인
systemctl is-active hermes-oauth-gateway

# 2. docker-compose.yml에 extra_hosts 확인
grep -A 5 "extra_hosts" /home/raspi5p/workspace/n8n-stack/docker-compose.yml
# 예상: host.docker.internal:host-gateway

# 3. n8n 컨테이너 재시작
docker-compose -f /home/raspi5p/workspace/n8n-stack/docker-compose.yml restart n8n

# 4. 컨테이너 내부 테스트
docker exec n8n-stack-n8n-1 wget -qO- http://host.docker.internal:5055/health
```

### sqlite3 CLI 없음

**증상**: `Command 'sqlite3' not found`

**해결:**
```bash
# Python 모듈 사용
python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('/home/raspi5p/workspace/n8n-stack/hermes-oauth-gateway/sessions.db')
cursor = conn.cursor()
cursor.execute('SELECT track, COUNT(*) FROM requests GROUP BY track;')
for row in cursor:
    print(row)
EOF
```

---

## 향후 계획

### Phase 6 (계획)
- [ ] **Token 파싱 로직**: Copilot CLI 응답에서 token 정보 추출 (현재: 0 토큰 기록)
- [ ] **OpenAI API Fallback**: Codex OAuth 만료 시 OpenAI API 키로 자동 전환
- [ ] **Rate Limiting**: API 요청 제한 (초당 10 req/user 등)
- [ ] **Hermes Agent Native 통합**: config.yaml에서 gateway 직접 호출
- [ ] **Grafana Dashboard**: SQLite 데이터 시각화

### 보안 개선
- [ ] API 키를 `~/.hermes/.env`에서 로드 (현재: hardcoded)
- [ ] TLS/HTTPS 지원 (현재: HTTP)
- [ ] Rate limit + DDoS 방어
- [ ] 요청 로깅 암호화 (현재: plaintext SQLite)

### 성능 최적화
- [ ] Redis 캐싱 (자주 호출되는 모델 응답)
- [ ] Connection pooling (CLI subprocess 재사용)
- [ ] 대용량 응답 스트리밍 (현재: 전체 로드)

---

## 파일 구조

```
hermes-oauth-gateway/
├── gateway.py                 # FastAPI 메인 애플리케이션
├── codex_driver.py            # Codex CLI subprocess 관리
├── copilot_driver.py          # Copilot CLI subprocess 관리 (Track B)
├── session_store.py           # SQLite 세션 로깅
├── routes.yaml                # 모델 라우팅 규칙
├── requirements.txt           # Python 의존성
├── hermes-oauth-gateway.service  # systemd unit file
├── sessions.db                # SQLite 데이터베이스 (자동 생성)
├── venv/                      # Python 가상환경
├── README.md                  # 이 문서
├── ARCHITECTURE.md            # 아키텍처 설계 (상세)
└── SETUP.md                   # 설치 가이드 (상세)
```

---

## 라이선스

Internal use only (Hnabyz DR Lab)

---

## 참고 자료

- [GitHub Issue #13](https://github.com/hnabyz-bot/abyz-lab-pm/issues/13)
- [Codex CLI Documentation](https://openai.com/index/codeinterpreter/)
- [GitHub Copilot CLI](https://github.blog/2024-01-github-copilot-in-the-cli-is-now-available)
- [n8n OpenAI Node](https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.openai/)

---

**Last Updated**: 2026-05-10  
**Version**: 1.0.0  
**Maintainer**: Hnabyz DR Lab
