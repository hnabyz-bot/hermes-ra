> ⚠️ **[LEGACY — rpi5p 아카이브]**
> 이 문서는 rpi5p 기반 Hermes 운영 시절의 모니터링 이메일 설계 기록이다.
> T3610 서버에서는 **Nous Research Hermes Agent v0.13.0**을 사용하며,
> 이 설계는 더 이상 활성 개발 대상이 아니다. 레퍼런스 목적으로만 보존.

# Hermes 모니터링 이메일 개선 + README 전면 재작성

**날짜**: 2026-05-07  
**상태**: 승인됨

---

## 배경

Hermes RA Agent가 Phase 1~3 구현 완료 후 10개 크론 잡, 12개 n8n 워크플로우, 4개 백그라운드 서비스가 운영 중이나 이를 한눈에 확인할 방법이 없었음. 사용자가 "AI가 뭘 처리했는지 어디서 확인하나"라는 질문 이후, 이메일 기반 모니터링으로 방향 확정.

---

## 목표

1. 기존 일일 이메일(op-daily-briefing)에 AI 처리 현황 섹션 추가
2. 주간 이메일(ra-weekly-ops-report)을 항상 발송 + AI 주간 요약 포함으로 개선
3. README.md를 현재 실제 상태 기준으로 전면 재작성

---

## 설계

### 1. 일일 이메일 확장 (`op-daily-briefing` 프롬프트 수정)

**파일**: `~/.hermes/cron/jobs.json` — `op-daily-briefing` 항목의 `prompt` 필드

**추가 내용**: 기존 WP 현황 이메일 본문 마지막에 아래 섹션 append

```
🤖 오늘 AI 처리 현황
─────────────────────
트리아지 댓글: N건   ← OP API: 오늘 날짜 댓글 중 "[Hermes 트리아지]" 포함
공문 처리:     N건   ← n8n API: ra-mail-to-op 오늘 실행 횟수
NAS 변경 감지: N건   ← nas_scanner POST /scan 결과
RA 알림 발송:  N건   ← n8n API: ra-annual-alerts + ra-deadline-alert 오늘 실행 횟수
```

데이터 조회 방법:
- OP API (`http://localhost:8086/api/v3/activities?...`): 오늘 날짜 필터 + text contains "[Hermes 트리아지]"
- n8n API (`http://localhost:5678/api/v1/executions?...`): workflowId별 오늘 실행 집계
- nas_scanner (`http://localhost:7789/scan`): POST 호출, 변경 감지 건수

**방법**: Hermes가 cron 프롬프트 지시에 따라 실행 시점에 직접 조회하므로 코드 변경 없이 프롬프트 수정만으로 구현 가능.

---

### 2. 주간 이메일 개선 (`ra-weekly-ops-report` 프롬프트 수정)

**파일**: `~/.hermes/cron/jobs.json` — `ra-weekly-ops-report` 항목의 `prompt` 필드

**변경사항**:
- 기존: `ISSUE_COUNT > 0`일 때만 발송
- 변경: **항상 발송** (정상이면 "이번 주 정상 운영" 한 줄 + AI 요약, 이상이면 기존처럼 오류 상세)

**추가 섹션**: 이메일 상단에 "이번 주 AI 처리 현황" 테이블

```
📋 이번 주 AI 처리 현황 (YYYY-MM-DD ~ YYYY-MM-DD)
──────────────────────────────────────────────────
트리아지 댓글:   N건
공문 처리:       N건
NAS 변경 감지:   N건
RA 알림 발송:    N건
크론 실행:       N회 성공 / N회 실패
```

조회: n8n API executions 주간 집계, OP API 주간 댓글 집계

---

### 3. README 전면 재작성

**파일**: `/home/raspi5p/workspace/work-github/abyz-lab-pm/README.md`

**구조**:

```
# abyz-lab-pm

## 개요
## 서비스 구성          ← 실제 컨테이너/포트 기준
## 트래픽 흐름
## Hermes AI 자동화
  ### 크론 스케줄 (10개)
  ### RA Agent 구성
  ### n8n 워크플로우 (12개)
## 모니터링             ← 신규: 일일/주간 이메일
## 운영 명령어
## 저장소 구조
## 배포
## Changelog
```

**핵심 수정 항목**:
| 항목 | 기존 (잘못됨) | 수정 |
|---|---|---|
| 크론 이름 | triage-summary, morning-briefing | issue-triage-batch, op-daily-briefing |
| gateway 실행 | systemd hermes-gateway.service | 프로세스 직접 실행 |
| OP_BASE_URL | localhost:8085 | localhost:8086 (nginx 경유) |
| RA Agent | 없음 | Phase 1~3 완료, 백그라운드 4개 서비스, KB 2801pts |
| n8n WF | 없음 | 12개 목록 |
| 모니터링 | 없음 | 일일/주간 이메일 섹션 |

---

## 구현 범위

- `~/.hermes/cron/jobs.json` 프롬프트 2개 수정 (op-daily-briefing, ra-weekly-ops-report)
- Hermes gateway 재시작 (설정 반영)
- `work-github/abyz-lab-pm/README.md` 전면 재작성
- git commit + push

## 범위 외

- weekly_ops_scan.py 코드 변경 없음 (프롬프트 레벨에서 처리)
- n8n 워크플로우 변경 없음
- OP 설정 변경 없음
