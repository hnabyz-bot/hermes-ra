# Hermes RA — Regulatory Affairs AI Agent

[![Latest Release](https://img.shields.io/github/v/release/hnabyz-bot/hermes-ra)](https://github.com/hnabyz-bot/hermes-ra/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Hermes RA**는 의료기기 규제 대응(Regulatory Affairs)을 자동화하는 AI 에이전트입니다.

- 📧 **이메일 기반 분석**: 규제 메일 → 자동 분석 → OpenProject 댓글 등록
- 🧠 **3-Model 아키텍처**: Codex (GPT-4) + Copilot (Claude) + GLM (Zhipu AI)
- 🔍 **NAS RAG 통합**: 회사 내 규제 자료 기반 맞춤형 대응 제시
- ⚡ **n8n 오케스트레이션**: 워크플로우 기반 자동화

## 📦 프로젝트 구조

```
hermes-ra/
├── hermes-oauth-gateway/        # OAuth 기반 다중 LLM 게이트웨이 (포트 5055)
│   ├── gateway.py              # FastAPI 메인 서버
│   ├── codex_driver.py          # GPT-4 (Codex CLI)
│   ├── copilot_driver.py        # Claude (GitHub Copilot CLI)
│   ├── glm_driver.py            # GLM-4.5 (Zhipu AI)
│   ├── session_store.py         # SQLite 세션 로깅
│   ├── routes.yaml              # 모델 라우팅
│   ├── ARCHITECTURE.md          # 설계 상세
│   └── README.md                # 사용 설명서
│
├── hermes-ra-api/               # RA 분석 API 서버 (포트 7788)
│   ├── hermes_v5.2_triple_model.py  # 3-model 병렬 호출
│   └── hermes-ra-api.service    # systemd 서비스
│
├── ops/                         # 운영 스크립트
│   └── scripts/
│       ├── ra_api_server.py     # v5.2 분석 엔진 (Qdrant RAG)
│       ├── nas_indexer.py       # NAS 자동 인덱싱 (cron 02:00)
│       ├── nas_scanner.py       # NAS 변경 감지 (md5 해시)
│       ├── extract_mail_qa.py   # 메일 QA 추출
│       ├── index_ra_knowledge.py# KB 벡터화
│       ├── index_github_repos.py# GitHub 문서 인덱싱
│       ├── n8n_deploy.py        # n8n 워크플로우 배포
│       └── ra_analyze.py        # 단일 메일 분석
│
├── config/                      # 설정 파일
│   ├── systemd/                 # systemd 서비스
│   │   ├── hermes-api-server.service
│   │   ├── hermes-gateway.service
│   │   ├── hermes-indexer.service
│   │   ├── hermes-nas-scanner.service
│   │   ├── hermes-ra-api.service
│   │   └── hermes-oauth-gateway.service
│   ├── hermes-config.yaml.example      # 설정 템플릿
│   └── dotenv/
│       ├── hermes.env.example          # 시스템 환경
│       └── hermes-user.env.example     # 사용자 환경
│
├── workflows/                   # n8n 자동화 워크플로우
│   ├── ra-request-to-op_v5.json # 메일→OP 분석 (활성)
│   └── hermes-notify.json       # 알림 (참고용)
│
├── scripts/                     # 배포/운영 도우미
│   ├── hermes-api-server.service
│   └── hermes-api-server.py
│
├── docs/                        # 문서
│   ├── architecture/            # 아키텍처
│   ├── design/                  # 설계 스펙
│   │   ├── 2026-05-07-hermes-v5-rag-design.md
│   │   ├── 2026-05-07-hermes-v5-implementation.md
│   │   └── 2026-05-07-hermes-monitoring-email-readme-design.md
│   └── evaluation/              # 모델 평가
│       └── HERMES_v5.2_EVALUATION_FINAL.md
│
└── logs/samples/                # 로그 샘플

```

## 🚀 빠른 시작

### 1. hermes-oauth-gateway 설치

```bash
cd hermes-oauth-gateway
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# systemd에 등록
sudo cp config/systemd/hermes-oauth-gateway.service /etc/systemd/system/
sudo systemctl enable hermes-oauth-gateway
sudo systemctl start hermes-oauth-gateway

# 상태 확인
curl http://localhost:5055/health
```

### 2. RA API 서버 설치

```bash
# /opt/hermes에 스크립트 복사
sudo cp ops/scripts/ra_api_server.py /opt/hermes/
sudo cp ops/scripts/nas_indexer.py /opt/hermes/

# systemd 서비스 등록
sudo cp config/systemd/hermes-ra-api.service /etc/systemd/system/
sudo systemctl enable hermes-ra-api
sudo systemctl start hermes-ra-api

# 포트 7788에서 실행 중인지 확인
curl http://localhost:7788/health
```

### 3. 환경변수 설정

```bash
# ~/.hermes/.env 또는 /opt/hermes/.env
export GLM_API_KEY=sk_xxxxx                  # z.ai API 키
export QDRANT_URL=http://localhost:6333      # Qdrant 벡터 DB
export OPENPROJECT_API_KEY=xxxxx             # OpenProject API
export OPENPROJECT_BASE_URL=https://plm.abyz-lab.work
```

## 📊 모델 평가 결과

### 테스트 시나리오 (3가지 규제 상황)

| 상황 | 설명 | Codex | Copilot | GLM |
|------|------|-------|---------|-----|
| **TFDA 긴급** | 태국 FDA, 4일 마감 | ✅ | ✅ | ❌ |
| **EU CE 갱신** | EUDAMED, 3개월 마감 | ✅ | ✅ | ❌ |
| **FDA 510(k)** | FDA, 30일 마감 | ✅ | ✅ | ❌ |
| **응답률** | - | **100%** | **100%** | **0%** |

### 권장 구성

**🥇 Primary: Copilot (Claude Sonnet)**
- ✅ 구체적 액션 플랜 + 타임라인
- ✅ RA 전문 용어 정확
- 응답시간: 37-40초
- 비용: $240/년

**🥈 Secondary: Codex (GPT-4)**
- ✅ 규제 의무사항 체크리스트
- ✅ 법적 안전성 우선
- 응답시간: 18-20초
- 비용: $200/년

**⏳ Tertiary: GLM (보류)**
- wp_comment API 0 bytes 문제
- z.ai 이슈 해결 후 재평가

📄 **상세 평가 보고서**: `docs/evaluation/HERMES_v5.2_EVALUATION_FINAL.md`

## 🔧 운영

### 주요 서비스

```bash
# API 서버 (포트 7788)
sudo systemctl status hermes-ra-api

# OAuth 게이트웨이 (포트 5055)
sudo systemctl status hermes-oauth-gateway

# NAS 인덱싱 (매일 02:00)
sudo systemctl status hermes-indexer

# NAS 변경 감지 (백그라운드)
sudo systemctl status hermes-nas-scanner
```

### 로그 확인

```bash
# API 로그
tail -f /home/raspi5p/.hermes/logs/agent.log

# systemd 로그
sudo journalctl -u hermes-ra-api -f
sudo journalctl -u hermes-oauth-gateway -f
```

### NAS 인덱싱

```bash
# 수동 인덱싱
python ops/scripts/nas_indexer.py

# 상태 확인
python -c "import json; print(json.load(open('/home/raspi5p/workspace/n8n-stack/hermes-ra/indexer_state.db')))"
```

## 📈 아키텍처 흐름

```
규제 메일 수신
      ↓
  [n8n WF]
      ↓
[Hermes RA API :7788]
  ├─ 메일 파싱
  ├─ 첨부파일 추출
  ├─ NAS RAG 검색 (Qdrant)
  └─ 3-Model 병렬 호출
       ├─ [OAuth Gateway :5055]
       │   ├─ Codex (GPT-4)
       │   ├─ Copilot (Claude)
       │   └─ GLM (Zhipu AI)
       └─ 결과 통합
           ↓
      [wp_comment 생성]
           ↓
    [OpenProject 댓글]
```

## 📚 문서

- **[ARCHITECTURE.md](hermes-oauth-gateway/ARCHITECTURE.md)** — OAuth Gateway 설계
- **[hermes-v5-rag-design.md](docs/design/2026-05-07-hermes-v5-rag-design.md)** — RAG 파이프라인
- **[EVALUATION_FINAL.md](docs/evaluation/HERMES_v5.2_EVALUATION_FINAL.md)** — 모델 평가
- **[hermes-config.yaml](config/hermes-config.yaml.example)** — 설정 참고

## 🔄 개발 사이클

**Cycle 1** ✅ (2026-05-10)
- 3가지 규제 시나리오 테스트 완료
- Codex/Copilot 100% 응답
- GLM API 이슈 진단

**Cycle 2** (진행 중)
- 다른 도메인 이메일 (금융, 화학, IT 등)
- Hermes agent 성장 추적
- GLM 문제 해결

**Cycle 3+**
- 사용자 실제 메일 재전송
- 최종 모델 확정
- 성과 측정

## 🛠️ 문제 해결

### GLM wp_comment 0 bytes
```
원인: z.ai API가 특정 프롬프트에 빈 응답 반환
해결: 프롬프트 최적화 + API 로그 확인 필요
상태: 추적 중
```

### NAS 인덱싱 지연
```
원인: md5 해시 비교로 변경 파일 감지 (inotify 불가)
해결: nas_indexer.py cron 02:00에 실행
상태: 정상 운영
```

## 📞 연락처

- **Repository**: https://github.com/hnabyz-bot/hermes-ra
- **Issues**: https://github.com/hnabyz-bot/hermes-ra/issues
- **Contact**: hnabyz2023@gmail.com

---

**Last Updated**: 2026-05-10  
**Version**: v5.2  
**Status**: Production
