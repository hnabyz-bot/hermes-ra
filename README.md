# Hermes RA — Regulatory Affairs AI Agent

**Hermes RA**는 의료기기 규제 대응(Regulatory Affairs)을 자동화하는 AI 에이전트입니다. 이메일 기반 규제 요청을 분석하고, NAS RAG(검색 증강 생성)를 통해 회사 내 규제 자료를 참고한 대응 방안을 제시합니다.

## 📦 프로젝트 구조

```
hermes-ra/
├── hermes-oauth-gateway/        # OAuth 기반 다중 LLM 게이트웨이
│   ├── gateway.py              # FastAPI 게이트웨이 (포트 5055)
│   ├── codex_driver.py          # GPT-4 (Codex CLI) 래퍼
│   ├── copilot_driver.py        # Claude (GitHub Copilot CLI) 래퍼
│   ├── glm_driver.py            # GLM-4.5 (Zhipu AI) 래퍼
│   ├── session_store.py         # SQLite 세션 로깅
│   ├── routes.yaml              # 모델 라우팅 규칙
│   ├── ARCHITECTURE.md          # 설계 상세
│   └── README.md                # 사용자 가이드
│
├── hermes-ra-api/               # RA 분석 API 서버
│   ├── hermes-ra-api.service    # systemd 서비스
│   └── hermes_v5.2_triple_model.py  # 3 모델 병렬 호출
│
├── docs/
│   ├── architecture/            # 아키텍처 문서
│   ├── design/                  # 설계 스펙
│   └── evaluation/              # 모델 평가 보고서
│
├── scripts/                     # 운영 스크립트
│   └── hermes-api-server.{py,service}
│
└── workflows/                   # n8n 워크플로우
    └── hermes-notify.json
```

## 🚀 주요 기능

### 1. 다중 LLM 게이트웨이 (OAuth)
- **Track A**: Codex (GPT-4)
- **Track B**: Copilot (Claude)
- **Track C**: GLM (Zhipu AI)

### 2. NAS RAG 기반 분석
- **벡터 DB**: Qdrant (포트 6333)
- **온톨로지**: nas_ra_docs 컬렉션
- **자동 인덱싱**: NAS 변경 감지

### 3. n8n 통합
- 이메일 → 분석 → OpenProject WP 댓글 자동 등록

## 📊 모델 평가 결과 (2026-05-10)

### 테스트 결과 (3가지 규제 시나리오)

| 시나리오 | Codex | Copilot | GLM |
|---------|-------|---------|-----|
| TFDA 긴급 (4일) | ✅ | ✅ | ❌ |
| EU CE 갱신 (3개월) | ✅ | ✅ | ❌ |
| FDA 510(k) (30일) | ✅ | ✅ | ❌ |
| **응답률** | **100%** | **100%** | **0%** |

### 권장 구성

**Primary**: Copilot (Claude Sonnet)
- 구체적 액션 플랜, 문서명+타임라인 명시
- $240/년

**Secondary**: Codex (GPT-4)
- 규제 의무사항 기반 체크리스트, 법적 안전성 우선
- $200/년

⏳ **보류**: GLM (z.ai API 이슈 해결 후 재평가)

📄 **상세 평가**: `docs/evaluation/HERMES_v5.2_EVALUATION_FINAL.md`

## 🔧 빠른 시작

### hermes-oauth-gateway 시작
```bash
cd hermes-oauth-gateway
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python gateway.py
```

### 환경변수
```bash
# ~/.hermes/.env
GLM_API_KEY=sk_xxxxx
```

## 📈 개발 로드맵

**Cycle 1** ✅ (2026-05-10): 3가지 규제 시나리오 테스트 완료  
**Cycle 2** (진행 중): 다른 도메인 이메일 테스트  
**Cycle 3+**: 최종 모델 확정 & Issue Close

---

**Contact**: hnabyz2023@gmail.com  
**Last Updated**: 2026-05-10
