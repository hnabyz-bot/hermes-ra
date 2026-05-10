# Hermes v5 — RA 도메인 지식 에이전트 설계 spec

**날짜**: 2026-05-07  
**관련 이슈**: GitHub #11 (ra-request-to-op)  
**현재 버전**: hermes-ra-api v4 (gemma3:4b, 단순 이메일 분석)  
**목표 버전**: v5 (Qdrant RAG + NAS 지속 학습 + 첨부파일 분석 + 3단계 모델 캐스케이드)

---

## 1. 배경 및 목적

RA(인허가) 담당자는 수신 이메일의 요청을 처리하기 위해 NAS에 축적된 수만 건의 인허가 문서를 수동으로 검색해야 한다. 사람의 파일 검색 속도와 기억력은 에이전트에 비해 느리다.

**Hermes는 RA 도메인 지식을 사전에 학습하고, 요청이 오면 즉시 관련 문서와 업무 체크리스트를 제공하는 RA 전담 에이전트다.**

목표: RA 담당자가 WP를 열면 코멘트에 이미 "무엇을 해야 하는지 + 어떤 파일을 참고해야 하는지"가 정리되어 있는 상태.

---

## 2. 현재 상태 (v4) 진단

| 항목 | 현재 상태 | 문제 |
|---|---|---|
| 첨부파일 처리 | 파일명 목록만 수집 | PDF/DOCX 내용 미분석 |
| NAS 연동 | 없음 | 관련 문서 검색 불가 |
| 분석 모델 | gemma3:4b, 이메일 본문 5000자만 | 컨텍스트 부족 |
| 지식 베이스 | 없음 (stateless) | 매 요청마다 zero-shot |

---

## 3. 전체 아키텍처

```
┌─────────────────────────────────────────────────────┐
│                  Hermes v5 구조                      │
│                                                     │
│  [지속 학습 레이어]          [요청 처리 레이어]         │
│  NAS 감시 (cron)             이메일 + 첨부파일         │
│       ↓                           ↓                 │
│  텍스트 추출                  텍스트 추출              │
│  (pdf/docx/hwp/pptx)         (pdf/docx/hwp)         │
│       ↓                           ↓                 │
│  nomic-embed-text            Qdrant 검색             │
│  임베딩 생성                  (시맨틱 top-K)           │
│       ↓                           ↓                 │
│  Qdrant upsert               gemma3:4b              │
│  (nas_ra_docs)               3단계 모델 캐스케이드      │
│                              (품질 자동 판단)          │
│                                   ↓                 │
│                              /analyze 응답           │
│                         (wp_comment 필드 추가)        │
└─────────────────────────────────────────────────────┘
         ↕ Docker network
┌─────────────────────────────────────────────────────┐
│  n8n 워크플로우 (ra-request-to-op v3 → v4)           │
│  첨부파일 다운로드 노드 추가                           │
│  hermes 호출 시 attachment_texts 전달                 │
│  WP 생성 후 → OP 코멘트 추가 노드                     │
└─────────────────────────────────────────────────────┘
```

---

## 4. 모델 캐스케이드 (자율 품질 최적화)

Hermes가 요청 복잡도와 출력 품질을 스스로 평가하여 모델을 선택한다.

### 3단계 캐스케이드

```
[1단계] gemma3:4b — 로컬 Ollama, 무료
    ↓ 품질 점수 계산
    score 8-10 → 완료 ($0)
    score 5-7  → glm-4.5-air 재실행
    score 0-4  → glm-5.1 재실행

[2단계] glm-4.5-air — z.ai API, $0.20/$1.10 per 1M
    ↓ 품질 점수 계산
    score 7-10 → 완료
    score 0-6  → glm-5.1 재실행

[3단계] glm-5.1 — z.ai API, $2/$8 per 1M (reasoning 모델)
    → 최종 출력 (max_tokens=3000 이상)
```

### 품질 점수 계산 기준

| 지표 | 0점 | 1점 | 2점 |
|---|---|---|---|
| `action` 길이 | < 30자 | 30-80자 | > 80자 |
| 체크리스트 항목 수 | 0-1개 | 2개 | 3개+ |
| NAS 참조 수 | 0건 | 1건 | 2건+ |
| JSON 필드 완성도 | 1개+ 누락 | - | 전 필드 완성 |

**합산 0-8점 → score로 환산 (×1.25 → 0-10)**

### 예상 비용 분포

| 케이스 | 종료 단계 | 예상 비용/건 |
|---|---|---|
| 단순 공지 메일 | gemma3:4b | $0 |
| 일반 심사 요청 | glm-4.5-air | < $0.001 |
| 복잡한 공문 + 첨부파일 | glm-5.1 | ~$0.02 |

### z.ai API 설정

- **엔드포인트**: `https://api.z.ai/api/paas/v4/` (일반 API, Coding Plan과 별개)
- **API Key**: `/home/raspi5p/workspace/n8n-stack/hermes-ra/.env` (`GLM_API_KEY=...`)
- **주의**: 모든 GLM 모델이 reasoning 모델 → `max_tokens` 최소 2000 필요
- **GLM Coding Plan** (`api/coding/paas/v4`): Claude Code 전용, hermes에서 사용 불가

---

## 6. 컴포넌트 상세 설계

### 6-1. NAS 인덱서 (`nas_indexer.py`)

**역할**: NAS 문서를 청크 단위로 임베딩하여 Qdrant에 저장. LLM 호출 없음.

**인덱싱 대상 폴더 (우선순위 순)**:
```
Priority 1 (즉시):
  /mnt/nas-ra/공통자료/DHF (인허가)/          # 4,341 files
  /mnt/nas-ra/변경점문서/                     # 2,082 files
  /mnt/nas-ra/회의자료/Project회의/CYAN/인허가문서/
  /mnt/nas-ra/회의자료/Project회의/Retrofit/
  /mnt/nas-ra/회의자료/Project회의/포터블 CE MDR/
  /mnt/nas-ra/회의자료/Project회의/주요 Project 인허가 이슈사항/
  /mnt/nas-ra/회의자료/Project회의/미국 방사선등록 EPRC/
  /mnt/nas-ra/공통자료/Standard(국제)/         # 114 files

Priority 2 (다음 단계):
  /mnt/nas-ra/공통자료/RA/★Label/             # 라벨 규격서
  /mnt/nas-ra/공통자료/RA/★User Manual/       # 사용자 매뉴얼
```

**대상 파일 타입**: `pdf`, `PDF`, `docx`, `doc`, `hwp`, `pptx`, `xlsx`  
**제외**: raw, dcm, bimg, dwg, dll, h, stp, dxf (바이너리/CAD)

**텍스트 추출 방법**:
| 형식 | 도구 |
|---|---|
| pdf / PDF | `pdftotext` (poppler-utils) |
| docx | `python-docx` |
| doc | `libreoffice --headless --convert-to txt` |
| hwp | `libreoffice --headless --convert-to txt` |
| pptx | `python-pptx` |
| xlsx | `openpyxl` (시트명 + 셀 텍스트) |

**청킹 전략**:
- 청크 크기: 500 토큰 (약 800자)
- 오버랩: 100 토큰
- 메타데이터 보존: `file_path`, `filename`, `folder_category`, `modified_at`, `chunk_index`

**변경 감지**:
- SQLite DB (`/home/raspi5p/workspace/n8n-stack/hermes-ra/indexer_state.db`)
- 테이블: `indexed_files(path, mtime, size, qdrant_ids, indexed_at)`
- mtime + size 변경 시만 재인덱싱

**임베딩 모델**: `nomic-embed-text` via Ollama  
- URL: `http://localhost:11434/api/embeddings`
- 차원: 768

**스케줄**: cron `0 2 * * *` (매일 새벽 2시, 기존 reconcile.sh와 분리)

---

### 6-2. Qdrant Docker

**n8n-stack/docker-compose.yml에 추가**:
```yaml
qdrant:
  image: qdrant/qdrant:latest
  container_name: n8n-stack-qdrant-1
  ports:
    - "127.0.0.1:6333:6333"   # 로컬호스트 전용
  volumes:
    - qdrant_storage:/qdrant/storage
  restart: unless-stopped
```

**Collection**: `nas_ra_docs`  
**벡터 설정**: size=768, distance=Cosine

---

### 6-3. hermes-ra-api v5 (`ra_api_server.py` 교체)

**신규 `/analyze` 입력 스키마**:
```json
{
  "from": "string",
  "subject": "string",
  "body": "string",
  "attachments": "string (파일명 목록, 하위호환)",
  "attachment_files": [
    {
      "filename": "string",
      "content_type": "string",
      "data": "base64 encoded binary"
    }
  ]
}
```

**처리 파이프라인**:
1. `attachment_files` 있으면 텍스트 추출 (pdftotext/python-docx/etc.)
2. 쿼리 구성: `subject + body[:1000] + attachment_text[:2000]`
3. Qdrant 시맨틱 검색: top-5 문서 청크 검색
4. 1차 프롬프트: gemma3:4b → 요청 분석 (기존 필드: summary, org, region, task_type, deadline, action, priority)
5. 2차 프롬프트: gemma3:4b → NAS 검색 결과 + 1차 분석 → wp_comment 생성

**신규 출력 필드**:
```json
{
  "...기존 필드들...",
  "wp_comment": "## 🤖 Hermes RA 가이드\n\n### 요청 분석\n...\n\n### 업무 체크리스트\n1. ...\n2. ...\n\n### 관련 NAS 문서\n- `파일경로` — 발췌: ...",
  "nas_refs": [
    {
      "path": "/mnt/nas-ra/...",
      "filename": "string",
      "score": 0.85,
      "excerpt": "string"
    }
  ]
}
```

**wp_comment 프롬프트 설계**:
```
당신은 의료기기 RA 전담 에이전트입니다.
아래 정보를 바탕으로 RA 담당자가 즉시 업무를 시작할 수 있도록
체크리스트와 관련 문서 가이드를 작성하세요.

[요청 분석 결과]
{hermes 1차 분석}

[관련 NAS 문서 발췌]
{qdrant top-K 결과}

[첨부파일 내용]
{attachment_text}

출력: 마크다운 형식, 체크리스트 + 파일 경로 포함
```

---

### 6-4. n8n 워크플로우 변경 (v3 → v4)

**추가/변경 노드**:

| 노드 | 변경 내용 |
|---|---|
| `첨부파일 다운로드` (신규) | `attachments[]` 있으면 Gmail `getMessage` + attachment download API 호출 |
| `hermes 호출` (수정) | `attachment_files` 배열 추가 전달 |
| `OP 코멘트 추가` (신규) | WP 생성 후 `POST /api/v3/work_packages/{id}/activities` — `wp_comment` 본문 |

**OP 코멘트 API**:
```
POST https://plm.abyz-lab.work/api/v3/work_packages/{id}/activities
Authorization: Basic {admin_token}
Content-Type: application/json

{
  "comment": {
    "raw": "{wp_comment}"
  }
}
```

**에러 처리**: 코멘트 추가 실패해도 WP 등록은 유지 (`onError: continueRegularOutput`)

---

## 7. 데이터 흐름 요약

```
[이메일 수신]
  → Gmail fetch (미확인 메일)
  → RA 요청 필터 (3smd)
  → 메일 파싱 + 첨부파일 다운로드
  → Ollama 유사도 분석 (기존 WP 매칭)
  → hermes v5 /analyze 호출
      ├─ 첨부파일 텍스트 추출
      ├─ Qdrant 검색 (관련 NAS 문서)
      ├─ gemma3:4b 1차: 요청 분석
      └─ gemma3:4b 2차: wp_comment 생성
  → WP 생성 (기존)
  → OP 코멘트 추가 (신규)
  → 메일 읽음 처리
```

---

## 8. 구현 범위 및 제외

**포함**:
- Qdrant Docker 컨테이너 추가
- `nas_indexer.py` 신규 작성
- `ra_api_server.py` v4 → v5 교체
- n8n 워크플로우 노드 추가 (첨부파일 다운로드, 코멘트 추가)
- cron 등록 (야간 인덱싱)
- nomic-embed-text 모델 설치

**제외 (추후)**:
- 웹훅 기반 즉시 재인덱싱 트리거
- 공통자료/RA 전체 인덱싱 (Priority 2)
- HWP 파일 처리 (libreoffice 설치 후 추가)
- 인덱싱 진행률 대시보드

---

## 9. 기술 스택 추가

| 항목 | 기술 | 비고 |
|---|---|---|
| 벡터 DB | Qdrant (Docker) | 포트 6333, 로컬호스트 전용 |
| 임베딩 | nomic-embed-text (Ollama) | 기존 Ollama 인프라 활용 |
| PDF 추출 | pdftotext (poppler-utils) | apt 설치 |
| DOCX 추출 | python-docx | pip 설치 |
| PPTX 추출 | python-pptx | pip 설치 |
| XLSX 추출 | openpyxl | pip 설치 |
| 상태 관리 | SQLite3 | Python 내장 |

---

## 10. 성능 예측 (RPi5 기준)

| 작업 | 예상 시간 |
|---|---|
| nomic-embed-text 청크 1개 임베딩 | ~1-2초 |
| Priority 1 초기 인덱싱 (약 7천 파일) | 수 시간 (일회성, 야간) |
| Qdrant 검색 top-5 | <100ms |
| gemma3:4b 2차 wp_comment 생성 | 3-5분 (비동기) |
| 전체 이메일 → WP 등록 | ~30초 (코멘트는 별도 비동기) |

---

## 11. 관련 파일 경로

| 파일 | 경로 |
|---|---|
| hermes API 서버 | `/home/raspi5p/workspace/n8n-stack/hermes-ra/ra_api_server.py` |
| NAS 인덱서 (신규) | `/home/raspi5p/workspace/n8n-stack/hermes-ra/nas_indexer.py` |
| 인덱서 상태 DB (신규) | `/home/raspi5p/workspace/n8n-stack/hermes-ra/indexer_state.db` |
| n8n-stack compose | `/home/raspi5p/workspace/n8n-stack/docker-compose.yml` |
| n8n 워크플로우 | `/home/raspi5p/workspace/n8n-stack/workflows/ra-request-to-op_v3.json` |
| 완성 후 워크플로우 | `/home/raspi5p/workspace/n8n-stack/workflows/ra-request-to-op_v4.json` |
