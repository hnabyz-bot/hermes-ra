# Hermes RA 프로젝트 진행 지침서

> 작성일: 2026-05-22
> 기준 저장소: [hnabyz-bot/hermes-ra](https://github.com/hnabyz-bot/hermes-ra)
> 현재 엔진: Nous Research Hermes Agent v0.13.0 on T3610

이 문서는 작업을 시작할 때 빠르게 기준을 맞추기 위한 진행 지침서다. 상세 운영 설명은 `README.md`, Claude Code 작업 규칙은 `CLAUDE.md`, 운영 철학은 `HERMES_RA_PHILOSOPHY.md`를 우선한다.

## 1. 현재 시스템 기준

### 1.1 활성 아키텍처

```text
[Gmail 수신]
    -> n8n ra-request-to-op_v5, 1분 폴링
    -> hermes-api-server :8643, scripts/hermes-api-server.py
    -> NAS RAG 검색, Qdrant :6333, nas_ra_docs
    -> hermes-gateway :8642, hermes -z oneshot
    -> OpenProject WP 댓글 자동 등록
```

### 1.2 노드와 네트워크

| 노드 | 역할 | 2.5G 직결 | LAN | Tailscale |
|------|------|-----------|-----|-----------|
| T3610 | Hermes RA 메인 서버 | 192.168.100.200 | 10.20.6.140 | 100.119.79.28 |
| GX10 | AI 컴퓨팅 노드 | 192.168.100.1 | 10.20.6.141 | 100.78.1.7 |

GX10은 Ollama `:11434`, Portainer `:9000`을 담당한다. GX10과의 통신은 2.5G 직결망을 우선한다.
n8n과 OpenProject는 **rpi5p**에서 운영된다.

## 2. 저장소 파일 분류

### 2.1 활성 파일

| 경로 | 역할 |
|------|------|
| `scripts/hermes-api-server.py` | OpenAI 호환 HTTP 래퍼, 기본 포트 `8643` |
| `scripts/nas_indexer.py` | NAS 증분 인덱싱, cron 02:00 KST 기준 |
| `scripts/nas_indexer_v2.py` | NAS 인덱서 v2 개발본 |
| `scripts/nas_scanner.py` | NAS 변경 감지 |
| `scripts/ra_analyze.py` | 단일 RA 질의 분석 테스트 |
| `scripts/index_github_repos.py` | GitHub 저장소 인덱싱 |
| `scripts/index_ra_knowledge.py` | RA 지식베이스 인덱싱 |
| `scripts/extract_mail_qa.py` | 메일 QA 추출 |
| `scripts/meta_extractor.py` | 메타데이터 추출 |
| `config/systemd/` | T3610 systemd 서비스 템플릿 |
| `config/dotenv/` | 환경변수 예시 파일 |
| `workflows/` | n8n 워크플로우 JSON |
| `README.md` | 사용자/운영 문서 |
| `CLAUDE.md` | AI 코딩 작업 지침 |
| `PROJECT_GUIDE.md` | 진행 기준 요약 |

### 2.2 아카이브 또는 레거시 파일

| 경로 | 기준 |
|------|------|
| `hermes-oauth-gateway/` | rpi5p 3-model gateway 아카이브 |
| `hermes-ra-api/` | rpi5p v5.2 Triple Model 아카이브 |
| `ra_api_server.py` | 루트의 rpi5p Python API 서버 |
| `ops/scripts/ra_api_server.py` | 이전 운영 스크립트 |

레거시 파일은 마이그레이션 검증이나 아카이브 정리 목적이 아니면 수정하지 않는다.

## 3. Git 운영 기준

### 3.1 원격 동기화

작업 시작 전에는 원격을 먼저 확인한다.

```bash
git status --short --branch
git fetch origin --prune
git pull --ff-only
```

충돌 가능성이 있거나 로컬 수정이 많으면 `pull` 전에 변경 파일을 분류한다.

### 3.2 로컬 전용 dot 파일

다음 항목은 개인 도구 설정과 훅, 로컬 MCP 실행 정보가 섞이므로 원격에 등록하지 않는다.

```text
.claude/
.moai/
.mcp.json
.codex/
```

팀 공용 설정이 필요해지면 실제 개인 설정을 올리지 말고, 별도 예시 파일이나 문서로 최소 설정만 작성한다.

## 4. 작업 시작 체크리스트

```bash
# 1. Git 상태
git status --short --branch

# 2. 서비스 상태
sudo systemctl status hermes-gateway hermes-api-server

# 3. API 헬스체크
curl http://localhost:8642/health
curl http://localhost:8643/health

# 4. Qdrant 컬렉션 상태
python3 -c "
import json, urllib.request
resp = json.loads(urllib.request.urlopen('http://localhost:6333/collections').read())
for c in resp['result']['collections']:
    name = c['name']
    info = json.loads(urllib.request.urlopen(f'http://localhost:6333/collections/{name}').read())
    print(name, info['result'].get('points_count', '?'), 'points')
"

# 5. NAS 마운트 확인
ls /mnt/nas-ra/ 2>/dev/null || echo "NAS 마운트 필요"

# 6. Hermes oneshot 확인
hermes -z "MFDS 의료기기 소프트웨어 허가 요건을 간략히 알려줘"
```

## 5. 개발 및 검증 규칙

- `scripts/hermes-api-server.py` 변경 후에는 `curl http://localhost:8643/health`와 실제 `/v1/chat/completions` 호출로 확인한다.
- `scripts/nas_indexer.py` 변경 후에는 작은 테스트 경로로 먼저 검증한다. `--force-reindex`는 명시적으로 필요할 때만 사용한다.
- systemd 서비스 파일은 gateway `8642`, API server `8643`, `HERMES_BIN=/home/abyz-lab/.local/bin/hermes` 기준을 유지한다.
- RA 답변 품질 변경은 단순 실행 성공이 아니라 실제 RA 질의와 출처 문서 포함 여부로 확인한다.
- 레거시 rpi5p 코드 수정은 별도 목적이 있을 때만 진행하고, T3610 활성 경로와 섞지 않는다.

## 6. 환경변수 관리

실제 환경 파일은 `/opt/hermes/.env`에 둔다. 저장소에는 예시 파일만 둔다.

```bash
GLM_API_KEY=sk_xxxxx
OPENPROJECT_API_KEY=xxxxx
OPENPROJECT_BASE_URL=https://plm.abyz-lab.work
QDRANT_URL=http://localhost:6333
OLLAMA_URL=http://localhost:11434
NAS_RA_PATH=/mnt/nas-ra/공통자료/RA
API_SERVER_KEY=<secret>
HERMES_BIN=/home/abyz-lab/.local/bin/hermes
API_SERVER_PORT=8643
```

`.env`, 인증서, 키, NAS credential 원본은 커밋하지 않는다. 필요한 값은 `config/dotenv/*.example`, `config/nas/*.example`로만 공유한다.

## 7. 서비스 포트

| 서비스 | 포트 | 위치 |
|--------|------|------|
| hermes-gateway | 8642 | T3610 |
| hermes-api-server | 8643 | T3610 |
| Qdrant | 6333 | T3610 |
| Ollama | 11434 | GX10 또는 T3610 |
| n8n | 5678 | rpi5p |
| Portainer | 9000 | GX10 |
| OpenProject | 443 | plm.abyz-lab.work |

## 8. Definition of Done

작업 완료는 다음을 만족해야 한다.

| 단계 | 확인 방법 |
|------|-----------|
| 설정 반영 | 실제 배포 경로 또는 systemd 환경에 반영됐는지 확인 |
| 동작 검증 | `hermes -z` 또는 API 헬스체크가 성공하는지 확인 |
| E2E 검증 | 실제 RA 질의가 n8n, API, Hermes, OpenProject 흐름에서 동작하는지 확인 |
| 출처 확인 | 답변에 NAS 문서 또는 지식베이스 출처가 포함되는지 확인 |
| Git 정리 | 로컬 전용 파일은 ignore 처리하고 공유 파일만 커밋 |

`/tmp` 테스트만 통과했거나, Hermes CLI 검증 없이 파일만 수정한 상태는 완료로 보지 않는다.

## 9. 남은 우선순위

| 우선순위 | 항목 | 기준 |
|----------|------|------|
| P1 | `workflows/ra-request-to-op_v5.json` 확보 | n8n 활성 워크플로우를 export 해서 저장소와 맞춘다 |
| P2 | NAS 마운트 상태 점검 | T3610에서 `/mnt/nas-ra/` 마운트 후 인덱싱을 검증한다 |
| P3 | OpenProject 댓글 흐름 확인 | 실제 WP 댓글 생성까지 E2E로 확인한다 |
| P4 | 레거시 코드 정리 계획 | rpi5p 아카이브를 유지, 분리, 삭제 중 하나로 결정한다 |

## 10. 개발 원칙

모든 개발 결정은 다음 질문으로 판단한다.

1. RA 담당자의 판단 부담을 줄이는가?
2. NAS 지식과 기존 문서를 더 잘 활용하는가?
3. 실수 가능성을 줄이고 검증 가능성을 높이는가?

Hermes RA는 보조 도구가 아니라 RA 전문 AI 에이전트다. 기능 추가보다 실제 업무 신뢰도와 출처 기반 답변 품질을 우선한다.
