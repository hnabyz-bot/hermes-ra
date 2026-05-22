# Hermes RA Agent — 핵심 철학 및 운영 원칙

> **Mission**: Hermes는 사람 RA 전문가를 보조하는 도구가 아니다.
> 사람 RA 전문가 수준을 넘어서는 **RA 전문 AI 에이전트**로 성장하는 것이 목표다.

> **[2026-05-11 AI 엔진 전환]**
> T3610 서버의 Hermes RA Agent AI 엔진은 **Nous Research Hermes Agent v0.13.0** 으로 전환되었다.
> 아래 Section 2의 시스템 구조 중 `/analyze API`, `OAuth Gateway`, `GLM cascade` 부분은
> **rpi5p 아카이브**이며, T3610에서는 Hermes Agent 스킬 시스템으로 대체된다.

---

## 1. 프로젝트 존재 이유 (Why)

의료기기 RA(규제 인허가) 업무는 방대한 문서, 복잡한 국가별 규제, 촉박한 마감이 공존한다.
Hermes는 이 업무의 **지식 처리 전체**를 담당한다.

- RA 담당자는 기계가 할 수 없는 **최종 판단과 서명**만 한다
- Hermes는 담당자가 실수하지 않도록 **구체적인 가이드와 근거**를 제시한다
- 담당자는 Hermes의 분석 없이는 업무를 시작하지 않는다

---

## 2. 시스템 구조 (How)

### T3610 현재 구조 (Nous Research Hermes Agent v0.13.0 기반)

**핵심 변화:** rpi5p의 자체 개발 파이프라인(ra_api_server.py 3-모델 캐스케이드)에서  
**Nous Research Hermes Agent v0.13.0** 스킬 시스템으로 마이그레이션 완료 (2026-05-11)

```
[Gmail 수신]
    → n8n ra-request-to-op_v5 (rpi5p:5678, 1분 주기 폴링)
    → hermes-api-server :8643 (/opt/hermes-ra/hermes-api-server.py)
         메일 메타데이터 파싱 (제목, 발신자, 첨부파일)
         리치 컨텍스트 빌드
         ↓
    → Nous Research Hermes Agent v0.13.0 (hermes -z)
         ~/.hermes/skills/ra-expert/ (이 저장소의 skills/ra-expert/ → symlink)
         ├── SKILL.md  (MFDS · CE MDR · FDA 510(k) · IEC 표준)
         ├── scripts/rag_search.py
         └── references/ (3개 시장 규정 요약)
         ↓
         [Layer 1] NAS Qdrant :6333 RAG 검색 (Docker, --restart unless-stopped)
         ├── nas_ra_docs 컬렉션
         ├── 임베딩: qwen3-embedding:latest (GX10 Ollama :11434, 4096dim, /api/embed)
         └── 데이터 소스: /mnt/nas-ra/ (CIFS, 매일 02:00 자동 인덱싱)
         ↓
         [Layer 2] ra-project 규제 지식베이스 (holee9/ra-project, 매일 07:00 pull)
         [Layer 3] MD-process QMS/SOP 절차서 (holee9/MD-process, 매일 07:05 pull)
         ↓
         wp_comment JSON 응답 생성
         ├── 분석 결과 (근거 문서 출처 명시)
         ├── 체크리스트 (조치사항)
         └── 규제 요건 매핑
         ↓
    → hermes-gateway :8642 (응답 중계)
    → n8n (응답 수신)
    → OpenProject 프로젝트 96 WP 댓글 자동 등록
         ↓
    [RA 담당자]
         → Hermes 분석 검토 (5분)
         → 최종 판단 + 서명
         → 체크리스트 기반 조치
```

**인프라 분리 원칙:**

| 계층 | 경로 | 역할 |
|------|------|------|
| **인텔리전스** | `~/.hermes/skills/ra-expert/` | **WHO**: RA 전문가 역할 정의, 지식, 판단 기준 (MFDS/CE/FDA/ISO) |
| **데이터 플로우** | `/opt/hermes-ra/` | **HOW**: NAS 인덱싱, HTTP 브리지, 임베딩 파이프라인 |

- 스킬 수정 후 Hermes 재시작 불필요 (파일 기반 로드)
- `/opt/hermes-ra/` 는 인프라 전용 (이 저장소는 지식만 관리)
- `~/.hermes/skills/ra-expert/` ← `hermes-ra/skills/ra-expert/` 심링크 (setup_new_pc.sh 생성)

### rpi5p 레거시 구조 (아카이브 — 더 이상 T3610에서 사용 안 함)

```
[RA 메일 수신]
    ↓ Gmail (hnabyz2023@gmail.com)
    ↓ n8n ra-request-to-op 워크플로우 (1분 주기 폴링)
    ↓
[Hermes RA API :7788 — ra_api_server.py] ← NAS Qdrant (nas_ra_docs, 84,592 points)
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

- `/mnt/nas-ra/` (CIFS, NAS IP: 100.126.59.10) — RA 관련 선별 경로만 인덱싱
- 매일 02:00 KST 자동 인덱싱 (`nas_indexer.py --force-reindex` or 증분)
- Qdrant `nas_ra_docs` 컬렉션 (Docker, `qwen3-embedding:latest` 4096dim)
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
| 스킬/설정 변경 | `~/.hermes/skills/ra-expert/` 또는 `~/.hermes/config.yaml`에 실제 반영 |
| 동작 검증 | `hermes` CLI로 RA 질의 테스트 후 전문가 수준 응답 확인 |
| E2E 검증 | 실제 RA 케이스로 전체 파이프라인 동작 확인 |
| 출처 명시 | 답변에 NAS 문서 경로 또는 지식베이스 출처 포함 |

---

## 5. 이슈 관리 원칙

- **이슈 close 조건**: 스킬/설정 변경 + 동작 검증 + 실제 케이스 확인
- **평가는 수단**: 모델 비교 평가는 최적 설정 결정을 위한 수단일 뿐
- 평가 완료 ≠ 이슈 close. **실제 RA 케이스 검증 완료 = 이슈 close**

---

## 6. RA 전문가 역할 정의

Hermes가 담당하는 것 (자동):
- RA 메일 파싱 및 분류
- Thai FDA, CE-MDR, MFDS 등 국가별 규제 요건 매핑
- NAS에서 관련 문서 검색 및 경로/발췌 제시
- 체크리스트 자동 생성 (서류별 조치사항)
- IEC 표준 버전 매핑 및 누락 항목 탐지
- OP WP 생성/분류/댓글 자동화 (연동 구성 후)

사람(RA 담당자)이 담당하는 것 (최소화):
- 규제기관 제출 전 최종 검토 및 서명
- NAS에서 찾지 못한 문서의 수기 확인
- 고객사 커뮤니케이션 (Hermes 초안 기반)
- 신규 표준/규제 변경 내용 Hermes 스킬에 반영

---

## 7. 성장 모델

Hermes는 처리한 모든 케이스에서 학습한다:
1. 처리 완료 케이스 → NAS 온톨로지에 메타데이터 추가
2. 담당자 피드백 → RA 스킬 개선 이슈 생성
3. 새로운 국가 규제 → NAS 인덱싱 + RA 스킬 업데이트
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
*AI 엔진 전환 업데이트: 2026-05-11 (rpi5p 자체 파이프라인 → Nous Research Hermes Agent v0.13.0)*
*3계층 지식소스 통합: 2026-05-22 (NAS Qdrant + ra-project + MD-process)*
*관리: hnabyz-bot/hermes-ra 프로젝트*
