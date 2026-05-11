# Hermes RA — Regulatory Affairs AI Agent

[![Latest Release](https://img.shields.io/github/v/release/hnabyz-bot/hermes-ra)](https://github.com/hnabyz-bot/hermes-ra/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> **[2026-05-11 아키텍처 전환]**
> T3610 서버에서의 AI 엔진은 **Nous Research Hermes Agent v0.13.0** 으로 전환되었습니다.
> 기존 `ra_api_server.py` + `3-Model Architecture (gemma3:4b → GLM cascade)` + `hermes-oauth-gateway`는
> **rpi5p 서버 아카이브**입니다. 신규 개발은 Hermes Agent RA 전문 스킬 탑재 방식으로 진행합니다.

**Hermes RA**는 의료기기 규제 대응(Regulatory Affairs)을 AI 전문가 수준으로 수행하는 에이전트입니다.

---

## T3610 현재 시스템 (Nous Research Hermes Agent v0.13.0)

| 항목 | 내용 |
|------|------|
| AI 엔진 | Nous Research Hermes Agent v0.13.0 |
| 바이너리 | `~/.local/bin/hermes` |
| 설정 | `~/.hermes/config.yaml` |
| RA 스킬 경로 | `~/.hermes/skills/ra-expert/` |
| 지식베이스 | ra-project + MD-process (매일 07:00 자동 pull) |
| NAS RAG | nas_ra_docs 컬렉션 (84,592 points) via MCP |
| gx10 연결 | 2.5G 직결 (192.168.100.200 → 192.168.100.1), 실측 2.35Gbps |
| gx10 Ollama | http://gx10:11434 (2.5G 직결) / http://100.78.1.7:11434 (Tailscale 외부) |

```
[RA 메일 / 규제 질의]
         ↓
[Hermes Agent v0.13.0 (Nous Research)]
    ├── RA Expert Skills (MFDS · FDA · MDR · ISO)
    ├── NAS Qdrant MCP (nas_ra_docs, 84,592 points)
    ├── ra-project 지식베이스
    └── MD-process SOP
         ↓
[전문가급 RA 답변 + 출처 문서 명시]
```

상세 개발 지침: **[CLAUDE.md](CLAUDE.md)** | 운영 철학: **[HERMES_RA_PHILOSOPHY.md](HERMES_RA_PHILOSOPHY.md)**

---

## [LEGACY] rpi5p 아카이브

> 아래 내용은 rpi5p 서버에서 운영하던 자체 개발 파이프라인의 기록이다.
> T3610에서는 사용하지 않는다.

## 📦 프로젝트 구조

```
hermes-ra/
├── hermes-oauth-gateway/        # OAuth 기반 다중 LLM 게이트웨이 (포트 5055)
│   ├── gateway.py              # FastAPI 메인 서버
│   ├── codex_driver.py          # GPT-4o (Codex CLI)
│   ├── copilot_driver.py        # Claude Sonnet 4.5 (Copilot CLI)
│   ├── glm_driver.py            # GLM-4.5-air (Zhipu AI)
│   ├── session_store.py         # SQLite 세션 로깅
│   ├── routes.yaml              # 모델 라우팅
│   ├── ARCHITECTURE.md          # 설계 상세
│   └── README.md                # 사용 설명서
│
├── ops/                         # 운영 스크립트
│   └── scripts/
│       ├── ra_api_server.py     # v5.2 분석 엔진 (NAS RAG + 3-Model)
│       ├── nas_indexer.py       # NAS 자동 인덱싱 (cron 02:00, --force-reindex)
│       ├── nas_scanner.py       # NAS 변경 감지 (md5 해시)
│       ├── qdrant_backup.sh     # Qdrant 스냅샷 백업 (이전용)
│       ├── qdrant_restore.sh    # Qdrant 스냅샷 복원 (이전용)
│       ├── setup_new_pc.sh      # 신규 PC 전체 셋업 자동화
│       ├── extract_mail_qa.py   # 메일 QA 추출
│       ├── index_ra_knowledge.py# KB 벡터화
│       ├── index_github_repos.py# GitHub 문서 인덱싱
│       ├── n8n_deploy.py        # n8n 워크플로우 배포
│       └── ra_analyze.py        # 단일 메일 분석
│
├── config/                      # 설정 파일
│   ├── systemd/                 # systemd 서비스 (참고용 — 현재 /etc/systemd/system/ 기준)
│   │   ├── hermes-gateway.service       # NousResearch Hermes-Agent gateway (:8642)
│   │   ├── hermes-api-server.service    # RA 분석 API (:8643)
│   │   ├── raspi-ra-oauth-gateway.service
│   │   ├── raspi-ra-indexer.service
│   │   └── raspi-ra-nas-scanner.service
│   ├── nas/
│   │   ├── fstab.example        # NAS fstab 항목 템플릿
│   │   └── nas-ra.creds.example # CIFS 자격증명 템플릿
│   └── dotenv/
│       ├── hermes.env.example          # 시스템 환경 (필수 키 목록)
│       └── hermes-user.env.example     # 사용자 환경
│
├── workflows/                   # n8n 자동화 워크플로우
│   ├── ra-request-to-op_v5.json # 메일→OP 분석 (활성, FhOhE3GPgepI6KOB)
│   └── hermes-notify.json       # 알림 (참고용)
│
├── docs/                        # 문서
│   ├── migration/
│   │   └── MIGRATION_GUIDE.md   # 신규 PC 이전 가이드 (방법A/B)
│   ├── design/                  # 설계 스펙
│   │   ├── 2026-05-07-hermes-v5-rag-design.md
│   │   └── 2026-05-07-hermes-v5-implementation.md
│   └── evaluation/              # 모델 평가
│       └── HERMES_v5.2_EVALUATION_FINAL.md
│
└── logs/samples/                # 로그 샘플
```

## 🚀 빠른 시작

### 신규 PC 자동 셋업 (권장)

```bash
git clone https://github.com/hnabyz-bot/hermes-ra.git
cd hermes-ra

# 기존 PC에서 Qdrant 스냅샷 백업 후 복사 (상세: docs/migration/MIGRATION_GUIDE.md)
sudo bash ops/scripts/setup_new_pc.sh --restore-snapshot ~/.hermes/snapshots/restore/
```

### 수동 설치

#### 1. raspi-ra-oauth-gateway

```bash
cd hermes-oauth-gateway
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

sudo cp config/systemd/raspi-ra-oauth-gateway.service /etc/systemd/system/
sudo systemctl enable --now raspi-ra-oauth-gateway

curl http://localhost:5055/health
```

#### 2. RA API 서버 (NousResearch Hermes-Agent 기반)

```bash
# hermes-agent 바이너리 설치 후 (v0.13.0+)
sudo cp config/systemd/hermes-gateway.service /etc/systemd/system/
sudo cp config/systemd/hermes-api-server.service /etc/systemd/system/
sudo systemctl enable --now hermes-gateway
sudo systemctl enable --now hermes-api-server

curl http://localhost:8643/health
```

#### 3. NAS 마운트

```bash
# 자격증명 파일 (config/nas/nas-ra.creds.example 참고)
sudo cp config/nas/nas-ra.creds.example /etc/samba/nas-ra.creds
sudo nano /etc/samba/nas-ra.creds   # username/password 입력
sudo chmod 600 /etc/samba/nas-ra.creds

# fstab 항목 추가 (config/nas/fstab.example 참고)
# //100.126.59.10/DR_Dev /mnt/nas-ra cifs credentials=/etc/samba/nas-ra.creds,...
sudo mount /mnt/nas-ra
```

#### 4. 환경변수 설정

```bash
# /opt/hermes/.env
GLM_API_KEY=sk_xxxxx              # z.ai API 키 (필수)
OPENPROJECT_API_KEY=xxxxx         # OpenProject API (필수)
OPENPROJECT_BASE_URL=https://plm.abyz-lab.work
QDRANT_URL=http://localhost:6333  # 기본값
OLLAMA_URL=http://localhost:11434 # 기본값
OAUTH_GATEWAY_URL=http://localhost:5055  # 기본값
NAS_RA_PATH=/mnt/nas-ra/공통자료/RA
```

전체 키 목록: `config/dotenv/hermes.env.example`

#### 5. NAS 인덱싱

```bash
# 최초 인덱싱 (수 시간 소요)
python /opt/hermes/nas_indexer.py

# 신규 PC — Qdrant 비어있는 경우 강제 재인덱싱
python /opt/hermes/nas_indexer.py --force-reindex

# 인덱싱 상태 확인
python3 -c "
import sqlite3
conn = sqlite3.connect('/home/raspi5p/workspace/n8n-stack/hermes-ra/indexer_state.db')
cnt = conn.execute('SELECT COUNT(*) FROM indexed_files').fetchone()[0]
print(f'인덱싱된 파일: {cnt}개')
conn.close()
"
```

## 📊 모델 평가 결과

### 테스트 시나리오 (3가지 규제 상황)

| 상황 | 설명 | Codex | Copilot | GLM |
|------|------|-------|---------|-----|
| **TFDA 긴급** | 태국 FDA, 4일 마감 | ✅ | ✅ | ✅ |
| **EU CE 갱신** | EUDAMED, 3개월 마감 | ✅ | ✅ | ✅ |
| **FDA 510(k)** | FDA, 30일 마감 | ✅ | ✅ | ✅ |
| **응답률** | - | **100%** | **100%** | **100%** |

> Cycle 1 당시 GLM은 wp_comment 0 bytes 문제로 응답 실패. 2026-05-10 프롬프트 최적화(-34.5%) + max_tokens 3000으로 완전 해결. **Cycle 3 재평가: 45/45 만점.**

### 권장 구성 (Cycle 3 기준 — 2026-05-10 확정)

| 역할 | 모델 | Cycle 3 점수 | 응답시간 | 주 용도 |
|------|------|------------|---------|--------|
| **🥇 Primary** | Copilot (Claude Sonnet 4.5) | 43/45 | 45.6초 | NAS 참조 실행 지침 (6/6 경로 인용) |
| **🥈 Secondary** | Codex (GPT-4o) | 43/45 | 52.1초 | 규제 의무사항 법적 검토, 체크리스트 |
| **🥉 Tertiary** | GLM (glm-4.5-air) | **45/45** ✨ | 54.6초 | 고부하 비용 효율, JSON 자동화 |

**🥇 Primary: Copilot (Claude Sonnet 4.5)**
- ✅ NAS 파일 경로 완전 인용 (6/6) — RAG 활용 극대화
- ✅ 실무 실행 지침 (담당자 즉시 사용 가능, 6,571자)
- 응답시간: 45.6초 | 비용: $240/년

**🥈 Secondary: Codex (GPT-4o)**
- ✅ IEC 표준 버전 5/5 완벽 명시
- ✅ 규제 조문 기반 체크리스트, NAS 불일치 경고
- 응답시간: 52.1초 | 비용: $200/년

**🥉 Tertiary: GLM (glm-4.5-air)** ✅ *2026-05-10 이슈 해결*
- ✅ Cycle 3 만점 (45/45) — 3개 모델 최고점
- ✅ JSON 구조 완성도 100% (자동화 파이프라인 안정)
- 응답시간: 54.6초 | 비용: z.ai 토큰 기반 (저비용)

📄 **상세 평가 보고서**: `docs/evaluation/HERMES_v5.2_EVALUATION_FINAL.md`

## 🔧 운영

### 주요 서비스

```bash
# NousResearch Hermes-Agent gateway (:8642)
sudo systemctl status hermes-gateway

# RA 분석 API 서버 (:8643)
sudo systemctl status hermes-api-server

# OAuth 게이트웨이 (:5055) — Codex/Copilot/GLM 3-model
sudo systemctl status raspi-ra-oauth-gateway

# RA 지식베이스 인덱싱
sudo systemctl status raspi-ra-indexer

# NAS 변경 감지
sudo systemctl status raspi-ra-nas-scanner
```

### 로그 확인

```bash
# API 서버 로그
sudo journalctl -u hermes-api-server -f

# OAuth 게이트웨이 로그
sudo journalctl -u raspi-ra-oauth-gateway -f
```

### NAS 인덱싱

```bash
# 수동 인덱싱 (변경 파일만)
python /opt/hermes/nas_indexer.py

# 강제 전체 재인덱싱 (Qdrant 초기화 후 재구축)
python /opt/hermes/nas_indexer.py --force-reindex

# 인덱싱 상태 확인
python3 -c "
import sqlite3
conn = sqlite3.connect('/home/raspi5p/workspace/n8n-stack/hermes-ra/indexer_state.db')
cnt = conn.execute('SELECT COUNT(*) FROM indexed_files').fetchone()[0]
print(f'인덱싱된 파일: {cnt}개')
"

# Qdrant 컬렉션 상태 확인
python3 -c "
import urllib.request, json
resp = json.loads(urllib.request.urlopen('http://localhost:6333/collections').read())
for c in resp['result']['collections']:
    info = json.loads(urllib.request.urlopen(f'http://localhost:6333/collections/{c[\"name\"]}').read())
    print(c['name'], info['result'].get('points_count','?'), 'points')
"
```

## 📈 아키텍처 흐름

```
규제 메일 수신
      ↓
  [n8n WF ra-request-to-op_v5 (FhOhE3GPgepI6KOB)]
      ↓
[hermes-api-server :8643 /analyze]   ← NousResearch Hermes-Agent 기반
  ├─ 메일 파싱 + 첨부파일 추출
  ├─ NAS RAG 검색 (Qdrant :6333, nas_ra_docs)
  │     ↑ /mnt/nas-ra/ (CIFS, 100.126.59.10)
  └─ hermes-gateway :8642 (hermes -z oneshot)
           ↓
      [wp_comment 생성]
           ↓
    [OpenProject 댓글]

[raspi-ra-oauth-gateway :5055]  ← 3-model 평가용 (별도)
  ├─ Codex (GPT-4o via OpenRouter)
  ├─ Copilot (Claude Sonnet 4.5 via CLI OAuth)
  └─ GLM (glm-4.5-air via z.ai)
```

## 🔄 신규 PC 이전

Qdrant 벡터 데이터(544MB, 84,592 포인트)와 인덱싱 상태를 완전하게 이전합니다.

### 방법 A: 스냅샷 이전 (권장, ~분 단위)

```bash
# 1. 소스 PC에서 백업
bash ops/scripts/qdrant_backup.sh ~/.hermes/snapshots/backup_$(date +%Y%m%d)
rsync ~/.hermes/snapshots/backup_YYYYMMDD/ NEW_PC:~/.hermes/snapshots/restore/

# 2. 신규 PC에서 복원
git clone https://github.com/hnabyz-bot/hermes-ra.git
sudo bash ops/scripts/setup_new_pc.sh --restore-snapshot ~/.hermes/snapshots/restore/
```

### 방법 B: NAS 재인덱싱 (스냅샷 없을 때, 수 시간)

```bash
sudo bash ops/scripts/setup_new_pc.sh --reindex
```

> 상세 절차: **[MIGRATION_GUIDE.md](docs/migration/MIGRATION_GUIDE.md)**

## 📚 문서

- **[MIGRATION_GUIDE.md](docs/migration/MIGRATION_GUIDE.md)** — 신규 PC 이전 가이드
- **[ARCHITECTURE.md](hermes-oauth-gateway/ARCHITECTURE.md)** — OAuth Gateway 설계
- **[hermes-v5-rag-design.md](docs/design/2026-05-07-hermes-v5-rag-design.md)** — RAG 파이프라인
- **[EVALUATION_FINAL.md](docs/evaluation/HERMES_v5.2_EVALUATION_FINAL.md)** — 모델 평가 (Cycle 1-3)
- **[hermes-config.yaml](config/hermes-config.yaml.example)** — 설정 참고

## 🔄 개발 사이클

**Cycle 1** ✅ (2026-05-10)
- 3가지 의료기기 RA 규제 시나리오 테스트 완료
- Codex/Copilot 100% 응답
- GLM API 이슈 진단 (wp_comment 0 bytes 근본 원인 확인)

**Cycle 2** ✅ (2026-05-10)
- NAS 온톨로지 기반 정성 평가 완료 (7항목 /35점 척도)
- GLM 문제 해결 (프롬프트 최적화 -34.5% + max_tokens 3000)
- Hermes agent 성장 추적

**Cycle 3** ✅ (2026-05-10)
- NAS 강화 프롬프트 재평가 (5항목 /45점 척도)
- 최종 모델 역할 확정 (Primary/Secondary/Tertiary)
- GLM Cycle 3 만점 달성 (45/45)

**Cycle 4+** (예정)
- 의료기기 RA 케이스 확대 (CDSCO 인도, BPOM 인도네시아, NMPA 중국 등)
- 실제 운영 케이스 10-15개 축적
- v5.3 성장 메커니즘 연동 (Issue #9)

## 🛠️ 문제 해결

### GLM wp_comment 0 bytes
```
원인: z.ai API max_tokens 부족 (wp_comment 프롬프트 길이 초과)
해결: 프롬프트 길이 -34.5% (1097→719 chars) + max_tokens 1500→3000
결과: GLM 응답 정상화 (1325자), Cycle 3 재평가 45/45 만점
상태: 해결 완료 (2026-05-10)
```

### NAS 인덱싱 지연
```
원인: md5 해시 비교로 변경 파일 감지 (inotify 불가)
해결: nas_indexer.py cron 02:00에 실행
상태: 정상 운영
```

### 신규 PC 재인덱싱 필요 (Qdrant 비어있는 경우)
```
증상: nas_indexer.py 실행 시 "⚠️ Qdrant가 비어있습니다" 경고
원인: indexer_state.db 기록은 있으나 Qdrant 데이터 없음
해결: python /opt/hermes/nas_indexer.py --force-reindex
     또는: qdrant_restore.sh 로 스냅샷 복원
```

## 📞 연락처

- **Repository**: https://github.com/hnabyz-bot/hermes-ra
- **Issues**: https://github.com/hnabyz-bot/hermes-ra/issues
- **Contact**: hnabyz2023@gmail.com

---

**Last Updated**: 2026-05-21  
**T3610 AI 엔진**: Nous Research Hermes Agent v0.13.0  
**Status**: Active Development (RA Expert Skill 탑재 진행 중)
