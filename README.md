> **[DEPRECATED — 2026-06-08]**
> 이 레포는 **아카이브 예정**입니다. ra-hermes-multi-agent 멀티 에이전트 시스템이 MVP 검증을 완료했습니다.
> 운영 스크립트 5종은 [ra-hermes-multi-agent/scripts/](https://github.com/holee9/ra-hermes-multi-agent/tree/main/scripts)로 이전 완료.
> 관련 이슈: holee9/ra-hermes-multi-agent#14

# Hermes RA — Regulatory Affairs AI Agent

[![Latest Release](https://img.shields.io/github/v/release/hnabyz-bot/hermes-ra)](https://github.com/hnabyz-bot/hermes-ra/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> **[2026-05-27 T3610 운영 체제]**
> AI 엔진: **Nous Research Hermes Agent v0.14.0**
> LLM: **qwen3:30b** (GX10 NVIDIA GB10 GPU 추론, ~24 tokens/sec)
> 3계층 지식소스(NAS Qdrant RAG + ra-project + MD-process) 통합 완료.
> 기존 rpi5p 기반 3-Model Architecture는 아카이브입니다.

**Hermes RA**는 의료기기 규제 대응(Regulatory Affairs)을 AI 전문가 수준으로 수행하는 에이전트입니다.  
MFDS·CE MDR·FDA 3개 시장 규제 지식과 회사 NAS 원본 문서를 결합해, 출처 문서를 명시하는 고품질 RA 분석을 제공합니다.

---

## 현재 시스템 (2026-05-27 기준)

| 항목 | 내용 |
|------|------|
| AI 엔진 | Nous Research Hermes Agent v0.14.0 |
| 바이너리 | `~/.local/bin/hermes` |
| 설정 파일 | `~/.hermes/config.yaml` |
| **LLM 모델** | `qwen3:30b` (GX10 Ollama, NVIDIA GB10 GPU, ~24 tokens/sec) |
| **컨텍스트 윈도우** | 65,536 tokens (`model.ollama_num_ctx: 65536`) |
| RA 스킬 경로 | `~/.hermes/skills/ra-expert/` → `/opt/hermes-ra/skills/ra-expert/` |
| **지식소스 Layer 1** | NAS Qdrant RAG — `nas_ra_docs` 컬렉션 (Docker, `:6333`) |
| **지식소스 Layer 2** | ra-project — 규제 지식베이스 (holee9/ra-project, 매일 07:00 pull) |
| **지식소스 Layer 3** | MD-process — QMS/SOP 절차서 (holee9/MD-process, 매일 07:05 pull) |
| 임베딩 모델 | `qwen3-embedding:latest` (GX10 Ollama, 4096차원, `/api/embed`) |
| GX10 GPU | NVIDIA GB10 (Grace Blackwell, 128GB 통합 메모리) |
| GX10 연결 | 2.5G 직결 (192.168.100.200 → 192.168.100.1) |
| GX10 커널 | `6.17.0-1018-nvidia` (NVIDIA 드라이버 포함) |

---

## 3계층 지식 아키텍처

```
RA 질의
  │
  ├─ Layer 1: NAS Qdrant RAG
  │    회사 원본 문서 (인증서, DHF, 성적서, 과거 인허가 이력)
  │    → 출처 인용: filename + excerpt
  │
  ├─ Layer 2: ra-project 규제 지식베이스
  │    구조화된 MFDS/CE MDR/FDA 규제 markdown
  │    holee9/ra-project (매일 07:00 자동 pull)
  │    → 인용: 파일 경로 + 섹션 헤딩
  │
  └─ Layer 3: MD-process QMS/SOP
       ISO 13485, 설계개발관리, 위험관리, PMS 절차서
       holee9/MD-process (매일 07:05 자동 pull)
       → 인용: 파일 경로 + 섹션 헤딩
```

모든 RA 질의는 3계층 전체를 검색하고, wp_comment JSON의 `source_docs` 필드에 출처를 명시합니다.

---

## 시스템 흐름도

```
[RA 메일 / 규제 질의]
         ↓
[n8n WF: ra-request-to-op_v5 (rpi5p:5678)]  ← Gmail 1분 주기 폴링
         ↓
[hermes-api-server.py :8643 (T3610)]
    ├─ 메일 메타데이터 파싱 (subject, sender, attachments)
    ├─ 리치 컨텍스트 빌드 → hermes -z "<context>"
    └─ wp_comment JSON 구조 응답 구성
         ↓
[Nous Hermes Agent v0.14.0 (T3610)]
    ├── RA Expert Skill (~/.hermes/skills/ra-expert/)
    │   ├─ SKILL.md (MFDS + CE MDR 2017/745 + FDA 510(k)) — 3계층 검색 지침 포함
    │   ├─ scripts/rag_search.py (Qdrant 검색 — qwen3-embedding:latest)
    │   └─ references/ (규정 요약 마크다운)
    ├── [Layer 1] NAS Qdrant RAG (:6333, Docker)
    │     ↑ /mnt/nas-ra/ (CIFS, NAS IP: 100.126.59.10)
    │     ↑ nas_indexer.py (매일 02:00 자동 인덱싱)
    ├── [Layer 2] ra-project (~/.hermes/config.yaml MCP filesystem)
    │     holee9/ra-project — 규제 지식베이스
    ├── [Layer 3] MD-process (~/.hermes/config.yaml MCP filesystem)
    │     holee9/MD-process — QMS/SOP 절차서
    └── GX10 Ollama (:11434, qwen3:30b LLM + qwen3-embedding:latest)
         ↓
[wp_comment JSON] → n8n (rpi5p) → OpenProject WP 댓글 등록
```

---

## 자동화 스케줄

| 시각 | 작업 | 로그 |
|------|------|------|
| 07:00 | ra-project git pull (규제 지식베이스 최신화) | `/var/log/hermes-ra-sync.log` |
| 07:05 | MD-process git pull (QMS/SOP 최신화) | `/var/log/hermes-ra-sync.log` |
| 07:10 | hermes-ra git pull + skills /opt/ 동기화 | `/var/log/hermes-ra-sync.log` |
| 02:00 | NAS 증분 인덱싱 (`nas_indexer.py`) | `/var/log/hermes-nas-indexer.log` |

---

## 빠른 시작

### 1단계: 저장소 클론 및 셋업

```bash
git clone https://github.com/hnabyz-bot/hermes-ra.git
cd hermes-ra

# 신규 PC 자동 셋업 (Qdrant 스냅샷 복원)
sudo bash ops/scripts/setup_new_pc.sh --restore-snapshot ~/.hermes/snapshots/restore/
```

### 2단계: Qdrant 시작 (Docker)

```bash
# Qdrant Docker 컨테이너 시작 (영속 스토리지 포함)
docker run -d \
  --name qdrant \
  --restart unless-stopped \
  -p 6333:6333 \
  -v /opt/hermes-ra/qdrant_storage:/qdrant/storage \
  qdrant/qdrant:latest

# 상태 확인
curl http://localhost:6333/collections
```

> 기존 qdrant_storage 볼륨이 없으면 빈 컨테이너로 시작됩니다.  
> NAS 마운트 후 `python3 /opt/hermes-ra/nas_indexer.py --force-reindex` 실행.

### 3단계: 환경변수 설정

```bash
# /opt/hermes-ra/.env
nano /opt/hermes-ra/.env
```

필수 키:

```bash
OPENPROJECT_API_KEY=xxxxx
OPENPROJECT_BASE_URL=https://plm.abyz-lab.work
QDRANT_URL=http://localhost:6333
OLLAMA_URL=http://192.168.100.1:11434       # GX10 2.5G 직결 (qwen3-embedding)
NAS_RA_PATH=/mnt/nas-ra/공통자료/RA
API_SERVER_KEY=<secret>
HERMES_BIN=/home/abyz-lab/.local/bin/hermes
HERMES_RA_DIR=/opt/hermes-ra
```

전체 키 목록: `config/dotenv/hermes.env.example`

### 4단계: MCP 지식소스 경로 확인

`~/.hermes/config.yaml`의 MCP filesystem 섹션에 아래 경로가 포함되어야 합니다:

```yaml
mcp_servers:
  filesystem:
    args:
    - -y
    - '@modelcontextprotocol/server-filesystem'
    - /home/abyz-lab/work/workspace-github/hnabyz-bot/hermes-ra
    - /mnt/nas-ra
    - /home/abyz-lab/work/workspace-github/holee9/ra-project
    - /home/abyz-lab/work/workspace-github/holee9/MD-process
    command: npx
```

### 5단계: 서비스 시작

```bash
sudo systemctl enable --now hermes-gateway
sudo systemctl enable --now hermes-api-server

curl http://localhost:8642/health
curl http://localhost:8643/health
```

### 6단계: 동작 검증

```bash
# RA 전문 질의 테스트 (3계층 검색 + 출처 인용 확인)
hermes -z "MFDS 의료기기 소프트웨어 허가 요건을 알려줘"

# RAG 검색 직접 테스트
python3 /opt/hermes-ra/skills/ra-expert/scripts/rag_search.py "DHF 인허가" --top 3
```

---

## 운영 가이드

### 서비스 관리

```bash
# 상태
sudo systemctl status hermes-gateway hermes-api-server

# 재시작
sudo systemctl restart hermes-gateway hermes-api-server

# 로그
sudo journalctl -u hermes-gateway -f
sudo journalctl -u hermes-api-server -f
tail -f ~/.hermes/logs/agent.log
```

### Qdrant 관리

```bash
# 컨테이너 상태
docker ps | grep qdrant
docker logs qdrant --tail 20

# 컬렉션 상태
python3 -c "
import urllib.request, json
resp = json.loads(urllib.request.urlopen('http://localhost:6333/collections').read())
for c in resp['result']['collections']:
    info = json.loads(urllib.request.urlopen(f'http://localhost:6333/collections/{c[\"name\"]}').read())
    print(c['name'], info['result'].get('points_count','?'), 'points')
"

# 컨테이너 재시작 (부팅 후 자동 시작됨 --restart unless-stopped)
docker start qdrant
```

### NAS 인덱싱

```bash
# NAS 마운트 확인
ls /mnt/nas-ra/ 2>/dev/null || echo "NAS 마운트 필요"

# 증분 인덱싱 (cron 02:00 자동 실행)
python3 /opt/hermes-ra/nas_indexer.py

# 강제 전체 재인덱싱 (신규 PC, Qdrant 교체 후)
python3 /opt/hermes-ra/nas_indexer.py --force-reindex

# 인덱싱 로그 실시간 확인
tail -f /var/log/hermes-nas-indexer.log
```

### 지식소스 수동 동기화

```bash
# ra-project 즉시 pull
cd /home/abyz-lab/work/workspace-github/holee9/ra-project && git pull --ff-only

# MD-process 즉시 pull
cd /home/abyz-lab/work/workspace-github/holee9/MD-process && git pull --ff-only

# hermes-ra 즉시 pull + /opt/ 동기화
cd /home/abyz-lab/work/workspace-github/hnabyz-bot/hermes-ra && git pull --ff-only
cp skills/ra-expert/SKILL.md /opt/hermes-ra/skills/ra-expert/SKILL.md
cp skills/ra-expert/scripts/rag_search.py /opt/hermes-ra/skills/ra-expert/scripts/rag_search.py

# 동기화 로그 확인
tail -20 /var/log/hermes-ra-sync.log
```

### GX10 연결 확인

```bash
# 2.5G 직결 (최우선)
ssh gx10                              # → 192.168.100.1

# GPU 상태 확인
ssh gx10 "nvidia-smi --query-gpu=name,utilization.gpu --format=csv,noheader"

# Ollama 모델 목록 확인
curl -s http://192.168.100.1:11434/api/tags | python3 -c "import sys,json; [print(m['name']) for m in json.load(sys.stdin)['models']]"

# 로드된 모델 및 VRAM 점유 확인
curl -s http://192.168.100.1:11434/api/ps | python3 -c "
import sys,json; d=json.load(sys.stdin)
for m in d.get('models',[]): print(m['name'], m['size_vram']//1024//1024,'MB VRAM')
"

# qwen3-embedding 동작 확인
curl -s -X POST http://192.168.100.1:11434/api/embed \
  -d '{"model":"qwen3-embedding:latest","input":"test"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('dim:', len(d['embeddings'][0]))"
```

---

## 인프라 구성 (T3610 ↔ GX10)

### 노드 역할

| 노드 | 역할 | OS |
|------|------|----|
| **T3610** | Hermes RA 메인 서버 / Claude Code | Ubuntu 26.04 LTS |
| **GX10** | AI 컴퓨팅 노드 — NVIDIA GB10 GPU (Ollama, Portainer) | Ubuntu 24.04.4 LTS, kernel 6.17.0-1018-nvidia |
| **rpi5p** | n8n, OpenProject 운영 | — |

### 네트워크

| 노드 | 2.5G 직결 | LAN | Tailscale |
|------|-----------|-----|-----------|
| T3610 | 192.168.100.200 | 10.20.6.140 | 100.119.79.28 |
| GX10 | 192.168.100.1 | 10.20.6.141 | 100.78.1.7 |

**GX10 통신 우선순위**: 2.5G 직결 > Tailscale > LAN

### 서비스 포트

| 서비스 | 포트 | 노드 |
|--------|------|------|
| hermes-gateway | 8642 | T3610 |
| hermes-api-server | 8643 | T3610 |
| Qdrant (Docker) | 6333 | T3610 |
| Ollama | 11434 | GX10 |
| n8n | 5678 | rpi5p |
| Portainer | 9000 | GX10 |
| OpenProject | 443 | plm.abyz-lab.work |

### 링크 성능 (2026-05-21 실측)

| 항목 | 결과 |
|------|------|
| TCP 송신 (T3610→GX10) | 2.36 Gbps |
| TCP 수신 (GX10→T3610) | 2.35 Gbps |
| 평균 지연 | 0.89 ms |

---

## 저장소 구조

```
hermes-ra/
├── skills/ra-expert/                ← RA Expert Skill (에이전트 인텔리전스)
│   ├── SKILL.md                     ← MFDS/CE MDR/FDA 전문 지식 + 3계층 검색 지침
│   ├── scripts/
│   │   └── rag_search.py            ← Qdrant 검색 (qwen3-embedding:latest)
│   └── references/
│       ├── MFDS_summary.md
│       ├── CE_MDR_summary.md
│       └── FDA_summary.md
├── scripts/                          ← /opt/hermes-ra/ 배포 대상
│   ├── hermes-api-server.py         ← OpenAI-compat HTTP 브리지 (:8643)
│   ├── nas_indexer.py               ← NAS 증분 인덱서 (qwen3-embedding, 4096dim)
│   ├── nas_indexer_v2.py
│   ├── meta_extractor.py
│   ├── index_ra_knowledge.py
│   ├── extract_mail_qa.py
│   └── index_github_repos.py
├── config/
│   ├── systemd/                      ← systemd 서비스 템플릿
│   ├── dotenv/
│   │   └── hermes.env.example
│   └── nas/
│       └── nas-ra.creds.example
├── workflows/
│   └── ra-request-to-op_v5.json     ← n8n 활성 워크플로우 (rpi5p 실행)
├── ops/scripts/
│   ├── setup_new_pc.sh
│   ├── qdrant_backup.sh
│   └── qdrant_restore.sh
├── docs/migration/MIGRATION_GUIDE.md
├── CLAUDE.md                         ← Claude Code 작업 지침
├── PROJECT_GUIDE.md                  ← 진행 기준 요약
└── HERMES_RA_PHILOSOPHY.md           ← 운영 철학
```

### LEGACY 파일 (rpi5p 아카이브, 2026-05-26 정리)

| 경로 | 이유 |
|------|------|
| `scripts/nas_scanner.py` | rpi5p PostgreSQL 전용 |
| `scripts/ra_analyze.py` | `hermes -z`로 대체됨 |
| `scripts/ra_api_server.py` | rpi5p 3-model cascade, T3610에서 미사용 (삭제: 2026-05-26) |
| `hermes-oauth-gateway/` | rpi5p 3-model gateway |
| `hermes-ra-api/` | rpi5p v5.2 Triple Model |
| `ra_api_server.py` (루트) | rpi5p Python API 서버 (삭제: 2026-05-26) |
| `ops/scripts/ra_api_server.py` | 이전 운영 스크립트 (삭제: 2026-05-26) |

---

## 신규 PC 이전

### 방법 A: Qdrant 스냅샷 이전 (권장)

```bash
# 소스 PC에서 백업
bash ops/scripts/qdrant_backup.sh ~/.hermes/snapshots/backup_$(date +%Y%m%d)
rsync -av ~/.hermes/snapshots/backup_YYYYMMDD/ NEW_PC:~/.hermes/snapshots/restore/

# 신규 PC에서 복원
git clone https://github.com/hnabyz-bot/hermes-ra.git
cd hermes-ra
sudo bash ops/scripts/setup_new_pc.sh --restore-snapshot ~/.hermes/snapshots/restore/
```

### 방법 B: NAS 재인덱싱 (스냅샷 없을 때)

```bash
# Qdrant Docker 시작 후 전체 재인덱싱
docker run -d --name qdrant --restart unless-stopped \
  -p 6333:6333 -v /opt/hermes-ra/qdrant_storage:/qdrant/storage qdrant/qdrant:latest
python3 /opt/hermes-ra/nas_indexer.py --force-reindex
```

상세: **[MIGRATION_GUIDE.md](docs/migration/MIGRATION_GUIDE.md)**

---

## 문제 해결

### Hermes TUI 응답 없음 (config 오류)

config.yaml의 model 설정이 잘못된 경우 `TypeError: 'NoneType' object is not iterable` 오류가 발생합니다.

```bash
# 현재 model 설정 확인
grep -A4 '^model:' ~/.hermes/config.yaml
```

정상 설정값 (T3610 기준):

```yaml
model:
  default: qwen3:30b
  provider: custom
  base_url: http://192.168.100.1:11434/v1
  ollama_num_ctx: 65536
```

> 이력: 2026-05-27 `gpt-5.3-codex` → ChatGPT 비공식 API 설정으로 TUI 완전 불통 → GX10 재부팅 + 설정 복구.  
> 상세: [docs/ops/2026-05-27-gx10-gpu-recovery.md](docs/ops/2026-05-27-gx10-gpu-recovery.md)

### Qdrant 컨테이너가 없을 때

```bash
docker ps -a | grep qdrant
# 중지된 경우:
docker start qdrant
# 아예 없는 경우:
docker run -d --name qdrant --restart unless-stopped \
  -p 6333:6333 -v /opt/hermes-ra/qdrant_storage:/qdrant/storage qdrant/qdrant:latest
```

### NAS 마운트 확인

```bash
mount | grep nas-ra
sudo mount /mnt/nas-ra   # 재마운트 (fstab에 등록된 경우)
```

### GX10 Ollama 연결 문제

```bash
ping -c 3 192.168.100.1
curl http://192.168.100.1:11434/api/tags
```

### 인덱서 임베딩 오류

임베딩 오류 발생 시 GX10의 `qwen3-embedding:latest` 모델 존재 여부 확인:

```bash
curl -s http://192.168.100.1:11434/api/tags | python3 -c \
  "import sys,json; models=[m['name'] for m in json.load(sys.stdin)['models']]; print('qwen3-embedding' in str(models))"
```

---

## 문서

- **[CLAUDE.md](CLAUDE.md)** — Claude Code 작업 지침 및 동작 검증
- **[PROJECT_GUIDE.md](PROJECT_GUIDE.md)** — 진행 기준 요약
- **[HERMES_RA_PHILOSOPHY.md](HERMES_RA_PHILOSOPHY.md)** — 운영 철학
- **[MIGRATION_GUIDE.md](docs/migration/MIGRATION_GUIDE.md)** — 신규 PC 이전 가이드

---

## [LEGACY] rpi5p 모델 평가 기록 (Cycle 1-3)

| 모델 | Cycle 3 점수 | 역할 |
|------|------------|------|
| Copilot (Claude Sonnet 4.5) | 43/45 | NAS 참조 실행 지침 |
| Codex (GPT-4o) | 43/45 | 규제 의무사항 법적 검토 |
| GLM (glm-4.5-air) | 45/45 | 고부하 비용 효율 |

상세: `docs/evaluation/HERMES_v5.2_EVALUATION_FINAL.md`

---

**Last Updated**: 2026-05-27  
**T3610 AI 엔진**: Nous Research Hermes Agent v0.14.0  
**LLM**: qwen3:30b (GX10 NVIDIA GB10 GPU, 65K ctx, ~24 tokens/sec)  
**지식소스**: NAS Qdrant (Docker) + ra-project + MD-process (3계층)  
**임베딩**: qwen3-embedding:latest (GX10 Ollama, 4096dim)
