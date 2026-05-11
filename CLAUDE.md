# CLAUDE.md — Hermes RA Agent 개발 지침

> **[2026-05-11 AI 엔진 전환 선언]**
> 이 서버(T3610)에서의 Hermes RA Agent AI 엔진은
> **Nous Research Hermes Agent v0.13.0** 으로 전환되었다.
> 기존 자체 개발 파이프라인(`ra_api_server.py` + `gemma3:4b → GLM cascade` + `hermes-oauth-gateway`)은
> rpi5p 서버 운영 아카이브로 보존되며, **이 서버(T3610)에서는 사용하지 않는다.**

---

## 프로젝트 개요

Hermes RA Agent는 의료기기 규제 인허가(RA) 업무를 RA 전문가 수준 이상으로 처리하는 AI 에이전트다.
보조 도구가 아닌 **전문 에이전트**로서 동작한다.

---

## AI 엔진 — Nous Research Hermes Agent

| 항목 | 내용 |
|------|------|
| 프레임워크 | Nous Research Hermes Agent v0.13.0 |
| 설치 경로 | `/home/abyz-lab/.hermes/hermes-agent/` |
| 바이너리 | `/home/abyz-lab/.local/bin/hermes` |
| 설정 파일 | `/home/abyz-lab/.hermes/config.yaml` |
| 현재 기본 모델 | gpt-5.5 (openai-codex) |
| RA 스킬 경로 | `~/.hermes/skills/ra-expert/` (신규 구성 예정) |

---

## 핵심 파일

- `~/.hermes/config.yaml` — Hermes Agent 설정 (모델, 퍼스널리티, 크론 등)
- `~/.hermes/skills/ra-expert/` — RA 전문 스킬 (신규 제작 예정)
- `~/.hermes/hermes-agent/skills/` — 빌트인 스킬 라이브러리
- `systemctl status hermes` — 서비스 상태 (설정 완료 후)

---

## Definition of Done (DoD) — 모든 이슈에 적용

이슈를 완료로 처리하려면 아래 **전부** 충족해야 한다:

1. **스킬/설정 변경**: `~/.hermes/skills/ra-expert/` 또는 `~/.hermes/config.yaml`에 변경 반영
2. **동작 검증**: `hermes` CLI로 RA 질의 테스트 후 전문가 수준 응답 확인
3. **E2E 검증**: 실제 RA 케이스(실제 규제 질의)로 전체 파이프라인 동작 확인

### DoD 위반 사례 (완료 아님)
- `/tmp` 스크립트로만 테스트 → **완료 아님**
- rpi5p 레거시 코드만 수정 → **완료 아님** (이 서버와 무관)
- 설정 변경 후 `hermes` CLI 검증 없이 완료 처리 → **완료 아님**
- E2E 없이 단위 테스트만 → **완료 아님**

---

## 서비스 구조 (T3610 목표)

```
[RA 메일 / 사내 규제 질의]
         ↓
[Hermes Agent v0.13.0 (Nous Research)]
    ├── RA Expert Skills (MFDS · FDA · MDR · ISO 표준)
    ├── NAS Qdrant MCP 연동 (nas_ra_docs, 84,592 points)
    ├── ra-project 지식베이스 (매일 07:00 자동 pull)
    └── MD-process SOP (매일 07:00 자동 pull)
         ↓
[전문가급 RA 답변 + 근거 문서 출처 명시]
```

---

## 개발 원칙

- 상세 철학: `HERMES_RA_PHILOSOPHY.md`
- Hermes Agent 스킬 제작 가이드: `~/.hermes/hermes-agent/skills/software-development/hermes-agent-skill-authoring/SKILL.md`
- 프로덕션 검증 없이는 이슈 close 금지
- 실제 RA 케이스 처리 확인 후 완료 처리

---

## rpi5p 레거시 컴포넌트 (이 서버에서 사용 안 함)

아래는 rpi5p에서 운영하던 자체 개발 파이프라인이다. 레퍼런스로만 보존.

| 경로 | 내용 | 상태 |
|------|------|------|
| `ops/scripts/ra_api_server.py` | Python HTTP API 서버 (포트 7788) | rpi5p 아카이브 |
| `hermes-oauth-gateway/` | OAuth 기반 3-Model 게이트웨이 (포트 5055) | rpi5p 아카이브 |
| `hermes-ra-api/` | v5.2 Triple Model 파이프라인 | rpi5p 아카이브 |
| `config/systemd/` | rpi5p systemd 서비스 파일 | rpi5p 아카이브 |
| `ops/scripts/nas_indexer.py` | NAS 인덱서 (rpi5p Qdrant용) | rpi5p 아카이브 |
