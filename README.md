# Hermes RA — Regulatory Affairs AI Agent

[![Latest Release](https://img.shields.io/github/v/release/hnabyz-bot/hermes-ra)](https://github.com/hnabyz-bot/hermes-ra/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> **[2026-05-22 T3610 운영 체제]**
> AI 엔진: **Nous Research Hermes Agent v0.13.0**
> T3610 서버에서 RA Expert Skill을 탑재하여 의료기기 규제 대응을 전문가 수준으로 수행합니다.
> 기존 rpi5p 기반 3-Model Architecture는 아카이브입니다.

**Hermes RA**는 의료기기 규제 대응(Regulatory Affairs)을 AI 전문가 수준으로 수행하는 에이전트입니다. T3610 Nous Hermes Agent v0.13.0 바탕으로 MFDS·CE MDR·FDA 3개 시장의 규제 지식을 정리한 RA Expert Skill로 구동됩니다.

---

## T3610 현재 시스템 (Nous Research Hermes Agent v0.13.0)

| 항목 | 내용 |
|------|------|
| AI 엔진 | Nous Research Hermes Agent v0.13.0 |
| 바이너리 | `~/.local/bin/hermes` |
| 설정 파일 | `~/.hermes/config.yaml` |
| RA 스킬 경로 | `~/.hermes/skills/ra-expert/` |
| 지식베이스 | ra-project + MD-process (매일 07:00 자동 pull) |
| NAS RAG | nas_ra_docs 컬렉션 (84,592 points via Qdrant) |
| GX10 연결 | 2.5G 직결 (192.168.100.200 → 192.168.100.1), 실측 2.35Gbps |
| GX10 Ollama | http://192.168.100.1:11434 (2.5G 직결) / http://100.78.1.7:11434 (Tailscale) |

### 시스템 흐름도

```
[규제 메일 / RA 질의]
         ↓
[n8n WF: ra-request-to-op_v5 (rpi5p:5678)]
         ↓
[hermes-api-server.py :8643 (T3610)]
    ├─ 메일 메타데이터 파싱 (subject, sender, attachments)
    ├─ 리치 컨텍스트 빌드 → hermes -z "<context>"
    └─ wp_comment JSON 구조 응답 구성
         ↓
[Nous Hermes Agent v0.13.0 (T3610)]
    ├── RA Expert Skill (~/.hermes/skills/ra-expert/)
    │   ├─ SKILL.md (MFDS + CE MDR 2017/745 + FDA 510(k))
    │   ├─ scripts/rag_search.py (Qdrant NAS 검색 헬퍼)
    │   └─ references/ (규정 요약 마크다운)
    ├── NAS Qdrant RAG (:6333)
    │     ↑ /mnt/nas-ra/ (CIFS, IP: 100.126.59.10)
    └── GX10 Ollama (:11434, 2.5G 직결 또는 Tailscale)
         ↓
[wp_comment JSON] → n8n (rpi5p) → OpenProject WP 댓글 등록
```

---

## 빠른 시작

### 1단계: 신규 PC 자동 셋업 (권장)

```bash
git clone https://github.com/hnabyz-bot/hermes-ra.git
cd hermes-ra

# Qdrant 스냅샷 복원 (기존 PC에서 사전 백업 필요)
# 상세: docs/migration/MIGRATION_GUIDE.md
sudo bash ops/scripts/setup_new_pc.sh --restore-snapshot ~/.hermes/snapshots/restore/
```

### 2단계: 환경변수 설정

```bash
# /opt/hermes-ra/.env (setup_new_pc.sh 실행 후 생성됨)
nano /opt/hermes-ra/.env
```

필수 키:

```bash
GLM_API_KEY=sk_xxxxx                        # z.ai API 키 (GLM-4.5-air)
OPENPROJECT_API_KEY=xxxxx
OPENPROJECT_BASE_URL=https://plm.abyz-lab.work
QDRANT_URL=http://localhost:6333
OLLAMA_URL=http://192.168.100.1:11434      # GX10 2.5G 직결
NAS_RA_PATH=/mnt/nas-ra/공통자료/RA
API_SERVER_KEY=<secret>                     # hermes-api-server.py Bearer 인증
HERMES_BIN=/home/abyz-lab/.local/bin/hermes
HERMES_RA_DIR=/opt/hermes-ra
```

전체 키 목록: `config/dotenv/hermes.env.example`

### 3단계: 서비스 시작

```bash
# Hermes Agent gateway 및 API 서버 활성화
sudo systemctl enable --now hermes-gateway
sudo systemctl enable --now hermes-api-server

# 서비스 상태 확인
sudo systemctl status hermes-gateway
sudo systemctl status hermes-api-server
curl http://localhost:8642/health
curl http://localhost:8643/health
```

### 4단계: 동작 검증

```bash
# hermes -z로 RA 질의 테스트
hermes -z "MFDS 의료기기 소프트웨어 허가 요건을 알려줘"

# 전체 파이프라인 E2E 테스트 (실제 RA 케이스)
# n8n에서 테스트 메일 발송 후 OpenProject WP 댓글 생성 확인
```

---

## 운영 가이드

### 서비스 관리

```bash
# 서비스 상태 확인
sudo systemctl status hermes-gateway
sudo systemctl status hermes-api-server

# 재시작
sudo systemctl restart hermes-gateway hermes-api-server

# 로그 실시간 확인
sudo journalctl -u hermes-gateway -f
sudo journalctl -u hermes-api-server -f

# Hermes Agent 로그
tail -f ~/.hermes/logs/agent.log
```

### RA Skill 검증

```bash
# Skill 파일 위치 확인
ls -la ~/.hermes/skills/ra-expert/

# Skill 테스트 (단일 질의)
hermes -z "MFDS 의료기기 검사 신청 절차는 어떻게 되나?"

# RAG 검색 헬퍼 테스트
python ~/.hermes/skills/ra-expert/scripts/rag_search.py \
  --query "FDA 510(k) 클리어런스" \
  --top-k 5
```

### NAS 인덱싱

> **전제조건**: NAS가 `/mnt/nas-ra/`에 마운트되어 있어야 합니다.

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

### GX10 연결 확인

```bash
# SSH 접속 — 2.5G 직결 (최우선)
ssh gx10                              # → 192.168.100.1 (2.5G)

# GX10 Ollama 접근
curl http://192.168.100.1:11434/api/tags

# 신규 PC 전체 셋업
sudo bash ops/scripts/setup_new_pc.sh --restore-snapshot ~/.hermes/snapshots/restore/
```

---

## T3610 ↔ GX10 인프라 (2026-05-21 구성 완료)

### 노드 구성

| 노드 | 호스트명 | 역할 | OS |
|------|----------|------|-----|
| **T3610** | abyz-lab-Precision-T3610 | Hermes RA 메인 서버 / Claude Code | Ubuntu 26.04 LTS |
| **GX10** | gx10-d74b | AI 컴퓨팅 노드 (Ollama, Portainer) | Ubuntu 24.04.4 LTS (nvidia) |

### 네트워크 토폴로지

```
[T3610]                                    [스위치]                   [GX10]
enp6s0 (2.5G)                                                   enx00e04c4728ca (2.5G)
192.168.100.200/24 ──────── 2500 Mbps Full Duplex ──────────── 192.168.100.1/24

enp0s25 (1G)                                                    enP7s7 (1G)
10.20.6.140/24 ───────────────── LAN ──────────────────────── 10.20.6.141/24

tailscale0                                                       tailscale0
100.119.79.28 ───────────── Tailscale VPN ─────────────────── 100.78.1.7
```

#### 인터페이스 상세

**T3610**

| 인터페이스 | 속도 | IP | 용도 |
|-----------|------|-----|------|
| `enp6s0` | 2.5G | 192.168.100.200/24 (고정) | GX10 전용 직결 |
| `enp0s25` | 1G | 10.20.6.140/20 (DHCP) | 인터넷/사내 LAN (기본 게이트웨이) |
| `tailscale0` | — | 100.119.79.28 | 원격 접속 VPN |

**GX10**

| 인터페이스 | 속도 | IP | 용도 |
|-----------|------|-----|------|
| `enx00e04c4728ca` | 2.5G | 192.168.100.1/24 (고정) | T3610 전용 직결 |
| `enP7s7` | 1G | 10.20.6.141/20 (DHCP) | 인터넷/사내 LAN (기본 게이트웨이) |
| `tailscale0` | — | 100.78.1.7 | 원격 접속 VPN |

#### 2.5G 링크 우선순위 정책

GX10과의 모든 통신은 **2.5G 직결(192.168.100.x)이 최우선**입니다.

- Tailscale(100.78.1.7) 및 사내 LAN(10.20.6.141)보다 항상 우선
- 상호 tailscale IP도 2.5G 경유 static route 설정:
  - T3610 → GX10 tailscale: `100.78.1.7/32 via 192.168.100.1 dev enp6s0`
  - GX10 → T3610 tailscale: `100.119.79.28/32 via 192.168.100.200 dev enx00e04c4728ca`

#### 성능 측정 결과 (2026-05-21)

| 항목 | 수치 |
|------|------|
| TCP 송신 (T3610 → GX10) | **2.36 Gbps** (패킷 손실 0%) |
| TCP 수신 (GX10 → T3610) | **2.35 Gbps** (패킷 손실 0%) |
| UDP | 1.68 Gbps (손실 0.21%) |
| 평균 지연 | **0.89 ms** |
| 링크 활용률 | 94% (2.5G 대비) |

### GX10 서비스 목록

| 포트 | 서비스 | 용도 |
|------|--------|------|
| 22 | SSH | 원격 관리 |
| 11434 | **Ollama** | 로컬 LLM 임베딩 (nomic-embed-text) |
| 9000 | Portainer | 컨테이너 관리 |

### SSH 접속

```bash
# GX10 접속 — 2.5G 직결 (최우선, ~/.ssh/config 자동 적용)
ssh gx10                     # → 192.168.100.1 via 192.168.100.200 (2.5G)

# GX10 접속 — Tailscale fallback (2.5G 링크 불가 시)
ssh gx10-tail                # → gx10-d74b (tailscale)

# T3610에서 GX10 Ollama 접근
curl http://192.168.100.1:11434/api/tags    # 2.5G 직결 경유
```

`~/.ssh/config` 핵심 설정:

```
Host gx10
    HostName 192.168.100.1
    User holee
    BindAddress 192.168.100.200      # 반드시 2.5G 인터페이스 사용
    IdentityFile ~/.ssh/id_ed25519

Host 10.20.6.141                     # LAN IP 입력 시 자동 2.5G 리다이렉트
    HostName 192.168.100.1
    User holee
    BindAddress 192.168.100.200
    IdentityFile ~/.ssh/id_ed25519
```

### NetworkManager 설정 (재부팅 영속)

netplan YAML 위치: `/etc/netplan/90-NM-d511308b-06c2-3cc4-b7da-8fb9d11b069b.yaml`

```yaml
network:
  version: 2
  ethernets:
    NM-d511308b-06c2-3cc4-b7da-8fb9d11b069b:
      renderer: NetworkManager
      match:
        name: "enp6s0"
        macaddress: "88:c9:b3:be:56:a5"
      addresses:
      - "192.168.100.200/24"
      routes:
      - to: "100.78.1.7/32"        # GX10 tailscale IP도 2.5G 경유
        via: "192.168.100.1"
      networkmanager:
        name: "gx10-2.5G"
        passthrough:
          connection.autoconnect-priority: "100"
          ipv4.never-default: "true"   # 인터넷 기본 게이트웨이로 사용 안 함
          ipv6.method: "disabled"
```

### 보안 설정

| 항목 | T3610 | GX10 |
|------|-------|------|
| UFW | 활성 (22, 3389, enp6s0 전체, tailscale0 전체) | 활성 (22, 11434, 8080, 9000, 5201) |
| PermitRootLogin | no (`/etc/ssh/sshd_config.d/99-security.conf`) | no (sshd_config 직접) |
| `/etc/hosts` | `192.168.100.1 gx10` | `192.168.100.200 t3610` |

---

## 저장소 구조

```
hermes-ra/
├── skills/ra-expert/                ← RA Expert Skill (에이전트 인텔리전스)
│   ├── SKILL.md                     ← MFDS / CE MDR / FDA 전문 지식
│   ├── scripts/
│   │   └── rag_search.py            ← Qdrant NAS 검색 헬퍼
│   └── references/
│       ├── MFDS_summary.md
│       ├── CE_MDR_summary.md
│       └── FDA_summary.md
├── scripts/                          ← /opt/hermes-ra/ 배포 대상
│   ├── hermes-api-server.py         ← OpenAI-compat HTTP 브리지 (:8643)
│   ├── nas_indexer.py               ← NAS 증분 인덱서
│   ├── nas_indexer_v2.py
│   ├── meta_extractor.py
│   ├── index_ra_knowledge.py
│   └── index_github_repos.py
├── config/
│   ├── systemd/                      ← systemd 서비스 템플릿
│   │   ├── hermes-gateway.service
│   │   └── hermes-api-server.service
│   ├── dotenv/
│   │   ├── hermes.env.example       ← 환경변수 키 목록
│   │   └── hermes-user.env.example
│   └── nas/
│       ├── fstab.example
│       └── nas-ra.creds.example
├── workflows/
│   └── ra-request-to-op_v5.json     ← n8n 활성 워크플로우 (rpi5p에서 실행)
├── ops/scripts/
│   ├── setup_new_pc.sh              ← 신규 PC 자동 셋업
│   ├── qdrant_backup.sh
│   └── qdrant_restore.sh
├── docs/
│   ├── migration/
│   │   └── MIGRATION_GUIDE.md
│   ├── design/
│   └── evaluation/
├── CLAUDE.md                         ← 개발 작업 지침
├── PROJECT_GUIDE.md                  ← 진행 기준 요약
└── HERMES_RA_PHILOSOPHY.md           ← 운영 철학
```

### LEGACY 파일 (rpi5p 아카이브)

다음 파일들은 기존 rpi5p 기반 시스템의 기록이며 T3610에서는 사용하지 않습니다:

- `scripts/nas_scanner.py` — rpi5p n8n PostgreSQL 연동 전용
- `scripts/ra_analyze.py` — Ollama 직접 호출 (hermes -z로 대체됨)
- `hermes-oauth-gateway/` — rpi5p 3-model 게이트웨이 (Codex/Copilot/GLM)
- `hermes-ra-api/` — rpi5p v5.2 Triple Model
- `ra_api_server.py` (루트) — rpi5p Python API 서버

---

## 신규 PC 이전

Qdrant 벡터 데이터(544MB, 84,592 포인트)와 인덱싱 상태를 완전하게 이전합니다.

### 방법 A: 스냅샷 이전 (권장, ~분 단위)

```bash
# 1. 소스 PC에서 백업
bash ops/scripts/qdrant_backup.sh ~/.hermes/snapshots/backup_$(date +%Y%m%d)
rsync -av ~/.hermes/snapshots/backup_YYYYMMDD/ NEW_PC:~/.hermes/snapshots/restore/

# 2. 신규 PC에서 복원
git clone https://github.com/hnabyz-bot/hermes-ra.git
cd hermes-ra
sudo bash ops/scripts/setup_new_pc.sh --restore-snapshot ~/.hermes/snapshots/restore/
```

### 방법 B: NAS 재인덱싱 (스냅샷 없을 때, 수 시간)

```bash
sudo bash ops/scripts/setup_new_pc.sh --reindex
```

상세 절차: **[MIGRATION_GUIDE.md](docs/migration/MIGRATION_GUIDE.md)**

---

## [LEGACY] rpi5p 아카이브

아래 내용은 rpi5p 서버에서 운영하던 자체 개발 파이프라인의 기록입니다. T3610에서는 사용하지 않습니다.

### 모델 평가 결과 (Cycle 1-3)

#### 테스트 시나리오 (3가지 규제 상황)

| 상황 | 설명 | Codex | Copilot | GLM |
|------|------|-------|---------|-----|
| **TFDA 긴급** | 태국 FDA, 4일 마감 | ✅ | ✅ | ✅ |
| **EU CE 갱신** | EUDAMED, 3개월 마감 | ✅ | ✅ | ✅ |
| **FDA 510(k)** | FDA, 30일 마감 | ✅ | ✅ | ✅ |
| **응답률** | - | **100%** | **100%** | **100%** |

Cycle 3 재평가: GLM 45/45 만점 (2026-05-10 프롬프트 최적화 -34.5% + max_tokens 3000 적용 후)

#### 권장 구성 (Cycle 3 기준)

| 역할 | 모델 | Cycle 3 점수 | 응답시간 | 주 용도 |
|------|------|------------|---------|--------|
| **🥇 Primary** | Copilot (Claude Sonnet 4.5) | 43/45 | 45.6초 | NAS 참조 실행 지침 |
| **🥈 Secondary** | Codex (GPT-4o) | 43/45 | 52.1초 | 규제 의무사항 법적 검토 |
| **🥉 Tertiary** | GLM (glm-4.5-air) | **45/45** | 54.6초 | 고부하 비용 효율 |

상세 평가 보고서: `docs/evaluation/HERMES_v5.2_EVALUATION_FINAL.md`

---

## 문서

- **[CLAUDE.md](CLAUDE.md)** — 개발 작업 지침 및 동작 검증
- **[PROJECT_GUIDE.md](PROJECT_GUIDE.md)** — 진행 기준 요약
- **[HERMES_RA_PHILOSOPHY.md](HERMES_RA_PHILOSOPHY.md)** — 운영 철학 및 RA 전문가 기준
- **[MIGRATION_GUIDE.md](docs/migration/MIGRATION_GUIDE.md)** — 신규 PC 이전 가이드
- **[hermes-v5-rag-design.md](docs/design/2026-05-07-hermes-v5-rag-design.md)** — RAG 파이프라인 설계
- **[EVALUATION_FINAL.md](docs/evaluation/HERMES_v5.2_EVALUATION_FINAL.md)** — 모델 평가 보고서 (Cycle 1-3)

---

## 문제 해결

### NAS 마운트 확인

```bash
# NAS 마운트 상태 확인
mount | grep nas-ra

# 마운트 안 됨: 재마운트
sudo mount /mnt/nas-ra
```

### Qdrant 컬렉션 상태

```bash
# 컬렉션 목록 및 포인트 수
python3 -c "
import urllib.request, json
resp = json.loads(urllib.request.urlopen('http://localhost:6333/collections').read())
print('Collections:', len(resp['result']['collections']))
for c in resp['result']['collections']:
    info = json.loads(urllib.request.urlopen(f'http://localhost:6333/collections/{c[\"name\"]}').read())
    print(f'{c[\"name\"]}: {info[\"result\"].get(\"points_count\",\"?\")} points')
"
```

### GX10 연결 문제

```bash
# 2.5G 직결 우선 확인
ping -c 3 192.168.100.1

# Ollama 접근 확인
curl http://192.168.100.1:11434/api/tags

# Tailscale fallback
curl http://100.78.1.7:11434/api/tags
```

---

## 연락처 및 링크

- **Repository**: https://github.com/hnabyz-bot/hermes-ra
- **Issues**: https://github.com/hnabyz-bot/hermes-ra/issues
- **Email**: hnabyz2023@gmail.com

---

**Last Updated**: 2026-05-22
**T3610 AI 엔진**: Nous Research Hermes Agent v0.13.0
**Status**: Active Operation (RA Expert Skill 탑재 완료)
**인프라**: T3610 ↔ GX10 2.5G 직결 구성 완료
