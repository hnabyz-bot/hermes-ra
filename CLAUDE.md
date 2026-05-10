# CLAUDE.md — Hermes RA Agent 개발 지침

## 프로젝트 개요

Hermes RA Agent는 의료기기 규제 인허가(RA) 업무를 RA 전문가 수준 이상으로 처리하는 AI 에이전트다.
보조 도구가 아닌 **전문 에이전트**로서 동작한다.

## 핵심 파일

- `/opt/hermes/ra_api_server.py` — 프로덕션 API 서버 (포트 7788)
- `/opt/hermes/.env` — GLM API 키 등 환경변수
- `systemctl status hermes-ra-api` — 서비스 상태 확인

## Definition of Done (DoD) — 모든 이슈에 적용

이슈를 완료로 처리하려면 아래 **전부** 충족해야 한다:

1. **실제 코드 변경**: `/opt/hermes/ra_api_server.py` 또는 n8n 워크플로우에 변경 반영
2. **서비스 재시작**: `systemctl restart hermes-ra-api` 완료
3. **E2E 검증**: 메일 → Hermes → OpenProject WP + 댓글 전체 파이프라인 동작 확인

### DoD 위반 사례 (완료 아님)
- `/tmp` 스크립트로만 테스트 → **완료 아님**
- 이슈 점수 향상만 확인 → **완료 아님**
- 코드 변경 없이 설정만 수정 → **완료 아님**
- E2E 없이 API 단위 테스트만 → **완료 아님**

## 서비스 구조

```
[RA 메일] → Gmail → n8n (ra-request-to-op) → /analyze :7788
                                                    ↓
                              NAS Qdrant (nas_ra_docs) ← 84,592 points
                                                    ↓
                              OAuth Gateway :5055
                              ├── Codex (GPT-4o)
                              ├── Copilot (Claude Sonnet)
                              └── GLM-4.5-Air
                                                    ↓
                              OpenProject WP + 댓글 자동 등록
```

## 모델 혼동 금지

| 역할 | 모델 | 포트 |
|------|------|------|
| 내부 캐스케이드 | gemma3:4b → glm-4.5-air → glm-5.1 | 자동 |
| 외부 평가 | Codex(gpt-4o) / Copilot(claude-sonnet) / GLM(glm-4.5-air) | :5055 |

## 개발 원칙

- 상세 철학: `HERMES_RA_PHILOSOPHY.md`
- 프로덕션 배포 + E2E 검증 없이는 이슈 close 금지
- 실제 케이스(실제 RA 메일) 처리 확인 후 완료 처리
