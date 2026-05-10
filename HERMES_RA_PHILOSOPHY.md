# Hermes RA Agent — 핵심 철학 및 운영 원칙

> **Mission**: Hermes는 사람 RA 전문가를 보조하는 도구가 아니다.
> 사람 RA 전문가 수준을 넘어서는 **RA 전문 AI 에이전트**로 성장하는 것이 목표다.

---

## 1. 프로젝트 존재 이유 (Why)

의료기기 RA(규제 인허가) 업무는 방대한 문서, 복잡한 국가별 규제, 촉박한 마감이 공존한다.
Hermes는 이 업무의 **지식 처리 전체**를 담당한다.

- RA 담당자는 기계가 할 수 없는 **최종 판단과 서명**만 한다
- Hermes는 담당자가 실수하지 않도록 **구체적인 가이드와 근거**를 제시한다
- 담당자는 Hermes의 분석 없이는 업무를 시작하지 않는다

---

## 2. 시스템 구조 (How)

```
[RA 메일 수신]
    ↓ Gmail (hnabyz2023@gmail.com)
    ↓ n8n ra-request-to-op 워크플로우 (1분 주기 폴링)
    ↓
[Hermes RA Agent] ← NAS Qdrant (nas_ra_docs, 84,592 points)
    ↓ /analyze API (port 7788)
    ├── Codex (GPT-4o) via OAuth Gateway :5055
    ├── Copilot (Claude Sonnet) via OAuth Gateway :5055
    └── GLM-4.5-Air via OAuth Gateway :5055
    ↓ 3-Model Cascade + Quality Score
    ↓
[OpenProject WP 생성/분류]
    ↓ 프로젝트 96 (인허가 요청)
    ↓ WP 댓글: Hermes 분석 결과 + NAS 문서 경로
    ↓
[RA 담당자]
    → Hermes 분석 검토 (5분)
    → 사람만이 할 수 있는 판단 수행
    → 실수 없이 체크리스트 따라 실행
```

---

## 3. NAS 온톨로지 — Hermes의 두뇌

NAS는 Hermes의 **장기 기억**이다.

- `/mnt/nas-ra/공통자료/DHF (인허가)/` — 70,000+ 파일, 87GB
- 매일 02:00 KST 자동 인덱싱 (`nas_indexer_v2.py`)
- Qdrant `nas_ra_docs` 컬렉션 (nomic-embed-text 임베딩)
- 모든 RA 분석은 NAS에서 근거 문서를 검색한 후 제시

### 온톨로지 목표
- 모든 RA 문서가 제품/표준/국가/날짜로 정확히 분류
- 신규 문서 추가 시 자동으로 기존 지식과 연결
- "이 서류가 NAS에 있는가?" → Hermes가 즉시 답할 수 있어야 함

---

## 4. 완료 기준 (Definition of Done)

**어떤 작업도 아래 기준을 충족해야 완료로 간주한다:**

| 기준 | 설명 |
|------|------|
| 프로덕션 반영 | `/opt/hermes/ra_api_server.py` 또는 n8n 워크플로우에 실제 코드 변경 |
| systemd 재배포 | `hermes-ra-api.service` restart 완료 |
| E2E 검증 | 실제 RA 메일 또는 테스트 케이스로 전체 파이프라인 동작 확인 |
| OP WP 생성 확인 | OpenProject에 WP가 정상 생성되고 댓글에 Hermes 분석 포함 |
| `/tmp` 스크립트 사용 금지 | 평가/검증은 항상 프로덕션 시스템으로 수행 |

---

## 5. 이슈 관리 원칙

- **이슈 close 조건**: 프로덕션 배포 + E2E 검증 + 실제 케이스 확인
- **평가는 수단**: 모델 비교 평가는 프로덕션 채택 결정을 위한 수단일 뿐
- **Cycle 평가 목적**: 어떤 모델/파라미터로 프로덕션을 운영할지 데이터 수집
- 평가 완료 ≠ 이슈 close. **프로덕션 반영 후 검증 완료 = 이슈 close**

---

## 6. RA 전문가 역할 정의

Hermes가 담당하는 것 (자동):
- RA 메일 파싱 및 분류
- Thai FDA, CE-MDR, MFDS 등 국가별 규제 요건 매핑
- NAS에서 관련 문서 검색 및 경로/발췌 제시
- 체크리스트 자동 생성 (서류별 조치사항)
- IEC 표준 버전 매핑 및 누락 항목 탐지
- OP WP 생성/분류/댓글 자동화

사람(RA 담당자)이 담당하는 것 (최소화):
- 규제기관 제출 전 최종 검토 및 서명
- NAS에서 찾지 못한 문서의 수기 확인
- 고객사 커뮤니케이션 (Hermes 초안 기반)
- 신규 표준/규제 변경 내용 Hermes에 학습 피드백

---

## 7. 성장 모델

Hermes는 처리한 모든 케이스에서 학습한다:
1. 처리 완료 케이스 → NAS 온톨로지에 메타데이터 추가
2. 담당자 피드백 → 프롬프트/로직 개선 이슈 생성
3. 새로운 국가 규제 → NAS 인덱싱 + 프롬프트 템플릿 추가
4. 모델 성능 추적 → 분기별 Multi-Cycle 평가 실시

---

## 8. 핵심 불변 원칙

> "Hermes는 RA 담당자가 더 잘하게 돕는 것이 아니라,
> RA 담당자가 Hermes 없이는 업무를 못할 정도로 성장해야 한다."

모든 개발 결정에서 이 기준으로 판단한다:
- **이 기능이 RA 담당자의 판단 부담을 줄이는가?**
- **이 기능이 NAS 지식을 더 잘 활용하는가?**
- **이 기능이 실수 가능성을 줄이는가?**

---

*최초 작성: 2026-05-10*
*관리: hnabyz-bot/hermes-ra 프로젝트*
