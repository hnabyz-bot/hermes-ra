# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## [MISSION — 절대 잊지 말 것]

> **T3610의 Hermes는 지구최강의 의료기기 RA 전문가로 성장해야 한다.**

- Hermes는 H&abyz의 전속 RA 전문가다. 보조 도구가 아니다.
- n8n, OpenProject는 Hermes의 전문성을 소비하는 클라이언트다. Hermes의 정체성이 아니다.
- 이 저장소의 모든 작업은 **Hermes의 RA 전문성 향상**을 위한 것이어야 한다.
- 인프라 개선(API 서버, 인덱서)은 Hermes가 더 잘 성장하도록 지원하는 역할이다. 목적 그 자체가 아니다.

**성장 경로:**
1. `skills/ra-expert/SKILL.md` — RA 지식과 판단 기준을 깊게 쌓는다
2. `skills/ra-expert/references/` — 규정 원문 요약을 풍부하게 한다
3. NAS Qdrant RAG — 회사 실제 사례를 Hermes가 인용할 수 있게 한다
4. `ra-project/` + `MD-process/` — 사내 규정·절차를 Hermes 지식으로 흡수시킨다

**목표 이탈 경보:** 아래 상황이 발생하면 즉시 멈추고 이 섹션을 다시 읽는다.
- 새로운 LLM을 연동하거나 fallback 체인을 만들려는 충동
- hermes-api-server.py에 RA 판단 로직을 추가하려는 충동
- n8n/OP 파이프라인 개선이 주목적이 되는 상황
- Hermes TUI 대신 외부 API 호출로 RA 분석을 처리하는 상황

---

> **[2026-05-27 AI 엔진 현황]**
> T3610 서버의 Hermes RA Agent AI 엔진: **Nous Research Hermes Agent v0.14.0**
> LLM: **qwen3:30b** (GX10 NVIDIA GB10, provider: custom, base_url: GX10 Ollama, ollama_num_ctx: 65536)
> `hermes-oauth-gateway/`, `hermes-ra-api/` 는 rpi5p 아카이브이며 T3610에서는 사용하지 않는다.

---

## 프로젝트 개요

T3610의 Hermes를 **지구최강 의료기기 RA 전문가**로 성장시키는 프로젝트.

- MFDS(한국), CE MDR(EU), FDA(미국) 3개 시장을 커버하는 전문가 수준 판단 능력
- H&abyz 사내 규정, NAS 문서, 글로벌 규제 원문을 모두 아우르는 지식 체계
- RA 담당자가 판단을 위임할 수 있는 신뢰 가능한 전문가 에이전트

---

## AI 엔진 정보 (T3610 현재)

| 항목 | 경로/값 |
|------|---------|
| 바이너리 | `~/.local/bin/hermes` |
| 버전 | v0.14.0 |
| 설정 파일 | `~/.hermes/config.yaml` |
| RA 스킬 경로 | `~/.hermes/skills/ra-expert/` |
| 로그 | `~/.hermes/logs/agent.log` |
| LLM 모델 | `qwen3:30b` (provider: custom, GX10 Ollama) |
| LLM 엔드포인트 | `http://192.168.100.1:11434/v1` |
| 컨텍스트 윈도우 | 65,536 tokens (`model.ollama_num_ctx: 65536`) |
| GX10 GPU | NVIDIA GB10 (kernel: 6.17.0-1018-nvidia) |

---

## 주요 운영 명령어

### Hermes Agent 기본 사용

```bash
# RA 질의 (oneshot)
hermes -z "MFDS 의료기기 소프트웨어 허가 요건을 알려줘"

# 대화형 모드
hermes

# 서비스 상태 확인
sudo systemctl status hermes-gateway
sudo systemctl status hermes-api-server
```

### 서비스 관리

```bash
# 재시작
sudo systemctl restart hermes-gateway hermes-api-server

# 로그 실시간 확인
sudo journalctl -u hermes-gateway -f
sudo journalctl -u hermes-api-server -f
tail -f ~/.hermes/logs/agent.log

# API 서버 헬스체크 (포트 8642: gateway, 8643: API server)
curl http://localhost:8642/health
curl http://localhost:8643/health
```

### NAS 인덱싱

> **전제조건**: NAS가 `/mnt/nas-ra/`에 마운트되어 있어야 합니다.
> T3610에는 현재 NAS가 마운트되어 있지 않습니다. 마운트 후 실행하세요.

```bash
# NAS 마운트 확인
ls /mnt/nas-ra/ 2>/dev/null || echo "NAS 마운트 필요"

# 변경 파일만 증분 인덱싱 (cron 02:00 KST 자동 실행)
python /opt/hermes-ra/nas_indexer.py

# 강제 전체 재인덱싱 (신규 PC 초기화 후)
python /opt/hermes-ra/nas_indexer.py --force-reindex

# Qdrant 컬렉션 상태 확인
python3 -c "
import urllib.request, json
resp = json.loads(urllib.request.urlopen('http://localhost:6333/collections').read())
for c in resp['result']['collections']:
    info = json.loads(urllib.request.urlopen(f'http://localhost:6333/collections/{c[\"name\"]}').read())
    print(c['name'], info['result'].get('points_count','?'), 'points')
"
```

### GX10 연결 (AI 컴퓨팅 노드)

```bash
# SSH 접속 — 2.5G 직결 (최우선)
ssh gx10                              # → 192.168.100.1 (2.5G)

# GX10 Ollama 접근
curl http://192.168.100.1:11434/api/tags

# 신규 PC 전체 셋업
sudo bash ops/scripts/setup_new_pc.sh --restore-snapshot ~/.hermes/snapshots/restore/
```

---

## 아키텍처 (T3610 현재 구조)

```
[n8n WF: ra-request-to-op_v5 (rpi5p:5678)]
    ↓ POST http://10.20.6.140:8643/v1/chat/completions
[hermes-api-server.py :8643]   ← /opt/hermes-ra/hermes-api-server.py
    ├─ 메일 메타데이터 파싱 (subject, sender, attachments)
    ├─ 리치 컨텍스트 빌드 → hermes -z "<context>"
    └─ wp_comment JSON 구조 응답 구성
         ↓
[Nous Hermes Agent v0.13.0]   ← ~/.hermes/ (바이너리: ~/.local/bin/hermes)
    ├─ ~/.hermes/skills/ra-expert/   ← 이 저장소 skills/ra-expert/ 심링크
    │   ├─ SKILL.md  (MFDS + CE MDR + FDA 510(k))
    │   ├─ scripts/rag_search.py  (Qdrant 검색)
    │   └─ references/  (규정 요약 markdown)
    ├─ Qdrant :6333 (nas_ra_docs 84,592 points)
    │     ↑ /mnt/nas-ra/ (CIFS, NAS IP: 100.126.59.10)
    └─ GX10 Ollama :11434 (nomic-embed-text, 2.5G 직결)
         ↓
[wp_comment JSON] → n8n → OpenProject WP 댓글 등록

[/opt/hermes-ra/ — 인프라 전용]
├─ hermes-api-server.py  (HTTP bridge)
├─ nas_indexer.py        (NAS→Qdrant, cron 02:00)
├─ meta_extractor.py     (문서 분류)
└─ skills/ra-expert/     (← ~/.hermes/skills/ra-expert 심링크 대상)
```

**핵심 분리 원칙:**
- `~/.hermes/skills/ra-expert/` = 에이전트 인텔리전스 (RA 전문 지식, 판단 기준)
- `/opt/hermes-ra/` = 인프라 (NAS 인덱싱, HTTP 브리지, 임베딩 파이프라인)
- n8n이 Gmail을 1분 주기로 폴링 → RA 메일 감지 → `hermes-api-server.py` 호출
- Hermes Agent가 NAS Qdrant RAG 검색 + RA 전문 스킬로 분석
- 결과를 wp_comment JSON으로 반환 → n8n이 OpenProject WP 댓글 등록

---

## 이 저장소의 파일 역할

| 경로 | 역할 | 상태 |
|------|------|------|
| `skills/ra-expert/SKILL.md` | RA 전문 에이전트 스킬 (MFDS/CE/FDA) | **핵심** |
| `skills/ra-expert/scripts/rag_search.py` | Qdrant NAS 문서 검색 헬퍼 | **핵심** |
| `skills/ra-expert/references/` | 규정 요약 마크다운 (3개 시장) | **핵심** |
| `scripts/hermes-api-server.py` | OpenAI-compat HTTP 브리지 (:8643) | **활성** |
| `scripts/nas_indexer.py` | NAS 증분 인덱서 (cron 02:00) | **활성** |
| `scripts/nas_indexer_v2.py` | NAS 인덱서 v2 (메타데이터 통합) | 개발본 |
| `scripts/meta_extractor.py` | 문서 메타데이터 분류 (온톨로지) | **활성** |
| `scripts/index_ra_knowledge.py` | RA 지식베이스 인덱싱 | **활성** |
| `scripts/index_github_repos.py` | GitHub 저장소 인덱싱 | **활성** |
| `config/dotenv/hermes.env.example` | 환경변수 키 목록 | 참고용 |
| `config/systemd/` | systemd 서비스 파일 (실제: `/etc/systemd/system/`) | 참고용 |
| `workflows/ra-request-to-op_v5.json` | n8n 활성 워크플로우 | **활성** |
| `scripts/nas_scanner.py` | rpi5p n8n PostgreSQL 전용 | **LEGACY** |
| `scripts/ra_analyze.py` | Ollama 직접 호출 (hermes -z로 대체됨) | **LEGACY** |
| `hermes-oauth-gateway/` | rpi5p 3-model 게이트웨이 | **LEGACY** |
| `hermes-ra-api/` | rpi5p v5.2 Triple Model | **LEGACY** |
| `ra_api_server.py` (루트, scripts/, ops/scripts/) | rpi5p Python API 서버 | **삭제됨** (2026-05-26) |

---

## 환경변수 (실제 파일: `/opt/hermes-ra/.env`)

```bash
OPENPROJECT_API_KEY=xxxxx
OPENPROJECT_BASE_URL=https://plm.abyz-lab.work
QDRANT_URL=http://localhost:6333
OLLAMA_URL=http://192.168.100.1:11434  # GX10 2.5G 직결 (임베딩)
EMBED_MODEL=qwen3-embedding:latest
NAS_RA_PATH=/mnt/nas-ra/공통자료/RA
API_SERVER_KEY=<secret>            # hermes-api-server.py Bearer 인증
HERMES_BIN=/home/abyz-lab/.local/bin/hermes
HERMES_RA_DIR=/opt/hermes-ra
```

---

## 인프라 네트워크

| 노드 | IP (2.5G 직결) | IP (LAN) | Tailscale |
|------|---------------|----------|-----------|
| T3610 | 192.168.100.200 | 10.20.6.140 | 100.119.79.28 |
| GX10 | 192.168.100.1 | 10.20.6.141 | 100.78.1.7 |

GX10 서비스: Ollama (:11434), Portainer (:9000)

rpi5p 서비스: n8n (:5678), OpenProject (plm.abyz-lab.work)

**GX10 통신 우선순위**: 2.5G 직결(192.168.100.x) > Tailscale > LAN

---

## SCOPE BOUNDARIES (HARD RULES) — 절대 경계

이 규칙들은 매 작업 시작 전 반드시 확인한다. 위반 시 즉시 중단하고 수정한다.

### [HARD-0] 미션 — Hermes는 지구최강 RA 전문가로 성장해야 한다

**이 프로젝트의 존재 이유는 단 하나다: T3610의 Hermes를 의료기기 RA 분야에서 세계 최고 수준의 전문가로 성장시키는 것.**

- Hermes는 특정 파이프라인(n8n→OP)의 부품이 아니다. n8n과 OP는 클라이언트 중 하나다
- Hermes는 TUI에서 직접 질의해도 세계 최고 수준의 RA 분석을 내놓아야 한다
- 모든 작업의 최종 판단 기준: "이 작업이 Hermes의 RA 전문성을 향상시키는가?"
  - YES → 진행
  - NO, 인프라 유지보수 → 최소한으로, RA 전문성에 방해되지 않는 범위에서
  - NO, 새 파이프라인/연동 → 중단하고 미션 재확인

**Hermes의 성장 = SKILL.md + references/ + 지식베이스(ra-project, MD-process) + NAS RAG 고도화**

### [HARD-1] Nous Hermes Agent는 PRIMARY 엔진이다

**Nous Research Hermes Agent v0.13.0 (`hermes -z --skills ra-expert`)는 항상 PRIMARY 호출 대상이다.**

- GLM, OpenRouter, 기타 LLM API는 Hermes 실패 시 fallback으로만 허용
- Hermes를 last resort로 강등하는 코드는 목표 위반이다
- 이 프로젝트는 Hermes를 자체 개발하는 게 아니라 **Hermes를 성장시키는** 프로젝트다

위반 패턴:
```python
# WRONG: 외부 LLM을 primary로, Hermes를 last resort로 두는 구조
if EXTERNAL_LLM_KEY:
    response = _call_external_llm(prompt)  # ← 위반
if not response:
    result = subprocess.run(["hermes", "-z", ...])  # ← Hermes가 last resort
```

올바른 패턴:
```python
# CORRECT: Hermes를 primary로, 외부 LLM은 불필요 (제거)
result = subprocess.run(["hermes", "-z", context, "--skills", "ra-expert"])  # primary only
```

### [HARD-2] RA 판단 로직은 SKILL.md에만 존재한다

**이메일 분류 규칙, WP 제목 형식, 규제 판단 기준 — 모든 RA 도메인 지식은 `skills/ra-expert/SKILL.md`에만 존재해야 한다.**

- Python/JS 코드에 RA 판단 로직을 하드코딩하면 안 된다
- `hermes-api-server.py`는 순수한 "얇은 HTTP 브리지"여야 한다 (인증, 라우팅, 결과 포맷만)
- SKILL.md를 수정해야 에이전트 능력이 향상되어야 한다. 코드 수정으로 RA 능력이 향상되면 설계가 잘못된 것이다

위반 징후:
- `build_ra_prompt()`처럼 RA 분류 규칙을 Python 함수 안에 긴 문자열로 하드코딩
- 이메일 유형 판별 로직이 SKILL.md가 아닌 코드에 있음

### [HARD-3] 인프라 코드 vs 인텔리전스 코드 분리

| 계층 | 경로 | 허용 내용 |
|------|------|---------|
| 인텔리전스 | `skills/ra-expert/` | RA 전문 지식, 판단 기준, 규정 요약 |
| 인프라 | `scripts/`, `ops/scripts/` | HTTP 브리지, NAS 인덱싱, 임베딩 파이프라인 |

인프라 코드(`scripts/`)가 RA 판단 로직을 포함하면 경계 위반이다.

### [HARD-4] 자체 AI 에이전트 개발 금지

**새로운 LLM 호출 체인, 멀티모델 캐스케이드, 자체 에이전트 프레임워크를 만들면 안 된다.**

- rpi5p의 3-model cascade(`hermes-oauth-gateway/`, `hermes-ra-api/`)는 이미 폐기된 설계다
- Hermes Agent의 스킬 시스템을 활용하는 것이 올바른 접근이다
- 새 LLM 통합이 필요하다면 Hermes config(`~/.hermes/config.yaml`)를 통해 설정한다

---

## 알려진 목표 이탈 이력

### [수정완료 2026-05-26] hermes-api-server.py — 엔진 우선순위 역전

**위반 내용**: GLM-4-Air primary, hermes last resort. `build_ra_prompt()`가 SKILL.md 분류 로직을 Python에 중복.
**수정 내용**: GLM/OpenRouter 전면 제거. `hermes -z --skills ra-expert` 단독 primary. `build_context()`로 축소(메타데이터+RAG만). 이메일 분류 규칙을 SKILL.md로 이전.

### [수정완료 2026-05-26] SKILL.md — Hermes를 파이프라인 부품으로 앵커링

**위반 내용**: SKILL.md가 `Always produce a JSON response (wp_comment)` 강제. frontmatter에 "produces wp_comment JSON for OpenProject" 명시. Hermes가 TUI 직접 질의에도 OP 댓글 봇처럼 행동.
**수정 내용**: Response Mode Detection 추가. Mode A(기본, 전문가 자연어 분석) / Mode B(파이프라인 컨텍스트 감지 시 wp_comment JSON) 분리. Hermes 정체성을 RA 전문가로 재정의. frontmatter에서 OP 고정 문구 제거.

---

## Definition of Done (DoD)

이슈를 완료로 처리하려면 아래 **전부** 충족해야 한다:

1. **스킬/설정 변경**: `~/.hermes/skills/ra-expert/` 또는 `~/.hermes/config.yaml`에 반영
2. **동작 검증**: `hermes -z "RA 질의"` 로 전문가 수준 응답 확인
3. **E2E 검증**: 실제 RA 케이스로 전체 파이프라인 동작 확인 (출처 문서 명시 포함)

`/tmp` 스크립트 테스트만, rpi5p 코드 수정, `hermes` CLI 검증 없이 완료 처리 — 모두 DoD 위반.

---

## 개발 원칙

운영 철학 전문: `HERMES_RA_PHILOSOPHY.md`

- RA Expert Skill: `skills/ra-expert/SKILL.md` (이 저장소) — setup_new_pc.sh가 `~/.hermes/skills/ra-expert/`로 심링크
- 스킬 수정 후 hermes 재시작 없이 바로 반영 (파일 기반 로드)
- 스킬 포맷 가이드: `~/.hermes/hermes-agent/skills/software-development/hermes-agent-skill-authoring/SKILL.md`
- 지식베이스(ra-project, MD-process)는 매일 07:00 자동 pull

---

## 신규 PC 이전

```bash
# 방법 A: Qdrant 스냅샷 이전 (권장)
bash ops/scripts/qdrant_backup.sh ~/.hermes/snapshots/backup_$(date +%Y%m%d)
# → 신규 PC로 rsync 후:
sudo bash ops/scripts/setup_new_pc.sh --restore-snapshot ~/.hermes/snapshots/restore/

# 방법 B: NAS 재인덱싱 (스냅샷 없을 때)
sudo bash ops/scripts/setup_new_pc.sh --reindex
```

상세: `docs/migration/MIGRATION_GUIDE.md`
