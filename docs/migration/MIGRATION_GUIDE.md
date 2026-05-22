# Hermes RA — 신규 PC 이전 가이드

---

## T3610 신규 PC 이전 가이드 (Nous Research Hermes Agent v0.13.0)

**최종 업데이트**: 2026-05-22

### 전제 조건

1. **Nous Research Hermes Agent v0.13.0** 설치 (`~/.local/bin/hermes`)
2. **hermes-ra 저장소** 클론: `git clone https://github.com/hnabyz-bot/hermes-ra.git`
3. **root 또는 sudo 권한** (systemd 서비스 등록용)

### 방법 A: Qdrant 스냅샷 이전 (권장 — 수 시간 절감)

**Step 1 — 기존 PC(T3610/rpi5p)에서 백업**

```bash
# hermes-ra 레포 최신 상태 확인
cd ~/workspace/hermes-ra
git pull

# Qdrant 스냅샷 생성 (nas_ra_docs + hermes-ra-knowledge 컬렉션)
bash ops/scripts/qdrant_backup.sh ~/.hermes/snapshots/backup_$(date +%Y%m%d)
# → ~/.hermes/snapshots/backup_YYYYMMDD/ 생성
```

**Step 2 — 신규 PC로 스냅샷 복사**

```bash
# 기존 PC에서:
rsync -avz ~/.hermes/snapshots/backup_YYYYMMDD/ NEW_PC_IP:~/.hermes/snapshots/restore/

# 또는 외부 스토리지 경유:
cp -r ~/.hermes/snapshots/backup_YYYYMMDD/ /external/drive/
```

**Step 3 — 신규 PC에서 설정**

```bash
# 신규 PC에서 레포 클론
git clone https://github.com/hnabyz-bot/hermes-ra.git ~/workspace/hermes-ra
cd ~/workspace/hermes-ra

# 자동 셋업 (스냅샷 복원 포함)
sudo bash ops/scripts/setup_new_pc.sh --restore-snapshot ~/.hermes/snapshots/restore/
```

**Step 4 — 환경변수 및 서비스 시작**

```bash
# 환경 변수 파일 작성
nano /opt/hermes-ra/.env

# 필수 키:
# GLM_API_KEY=sk_xxxxx              # z.ai API 키
# OPENPROJECT_API_KEY=xxxxx
# OPENPROJECT_BASE_URL=https://plm.abyz-lab.work
# QDRANT_URL=http://localhost:6333
# OLLAMA_URL=http://192.168.100.1:11434  # GX10 2.5G 직결
# API_SERVER_KEY=<secret>
# HERMES_BIN=~/.local/bin/hermes
# HERMES_RA_DIR=/opt/hermes-ra
# NAS_RA_PATH=/mnt/nas-ra/공통자료/RA

# NAS 자격증명 설정
sudo nano /etc/samba/nas-ra.creds
# username=drake.lee
# password=YOUR_PASSWORD

# NAS 마운트 확인 및 마운트
ls /mnt/nas-ra/ 2>/dev/null || sudo mount /mnt/nas-ra/

# 서비스 시작
sudo systemctl enable --now hermes-gateway hermes-api-server

# 헬스체크
curl http://localhost:8642/health
curl http://localhost:8643/health
```

**Step 5 — 동작 검증**

```bash
# Qdrant 컬렉션 상태 확인
python3 -c "
import urllib.request, json
resp = json.loads(urllib.request.urlopen('http://localhost:6333/collections').read())
for c in resp['result']['collections']:
    info = json.loads(urllib.request.urlopen(f'http://localhost:6333/collections/{c[\"name\"]}').read())
    print(c['name'], info['result'].get('points_count','?'), 'points')
"
# 기대값: nas_ra_docs: 84,592+ points

# RA Expert Skill 동작 테스트
hermes -z "MFDS 의료기기 소프트웨어 허가 요건"
# → 전문가 수준 답변 + 출처 문서 확인
```

---

### 방법 B: NAS 재인덱싱 (스냅샷 없을 때)

스냅샷이 없는 경우, NAS에서 처음부터 재인덱싱합니다. **수 시간 소요**.

```bash
# 신규 PC에서
cd ~/workspace/hermes-ra
sudo bash ops/scripts/setup_new_pc.sh --reindex

# 진행 상황 확인
tail -f ~/.hermes/logs/agent.log
```

완료 후:
```bash
# NAS 컬렉션 포인트 수 확인
python3 -c "
import urllib.request, json
resp = json.loads(urllib.request.urlopen('http://localhost:6333/collections/nas_ra_docs').read())
print('nas_ra_docs:', resp['result'].get('points_count','?'), 'points')
"
```

---

## [LEGACY — rpi5p 아카이브]

아래는 rpi5p 기반 Hermes 자체 개발 파이프라인(ra_api_server.py + Qdrant + Ollama)의 PC 이전 절차입니다.  
T3610 서버에서는 **Nous Research Hermes Agent v0.13.0**을 사용하며, 이 이전 가이드는 더 이상 활성 운영 대상이 아닙니다. 레퍼런스 목적으로만 보존합니다.

### 버전 정보

**버전**: v5.2  
**최종 업데이트**: 2026-05-10

---

## 이전해야 할 구성 요소

| 구성 요소 | 위치 | 이전 방법 |
|----------|------|---------|
| 소스 코드 (8개 스크립트) | git (hermes-ra + n8n-stack) | `git clone` |
| systemd 서비스 | `config/systemd/` | git → `/etc/systemd/system/` |
| 환경 변수 | `/opt/hermes/.env` | 수동 (민감 정보) |
| **Qdrant 벡터 DB** (544MB) | `/qdrant/storage/` (런타임) | **스냅샷 백업** 또는 재인덱싱 |
| indexer_state.db (2,973 파일) | n8n-stack git | `git pull` |
| NAS CIFS 마운트 | `/etc/fstab` + `/etc/samba/nas-ra.creds` | 수동 설정 |
| Ollama 모델 | 로컬 (nomic-embed-text) | `ollama pull nomic-embed-text` |

> **Qdrant 벡터 데이터가 핵심**: `nas_ra_docs` 컬렉션 84,592 포인트가 NAS RAG의 "성장 결과물"입니다.  
> 스냅샷 없이 신규 PC에서 재인덱싱하면 수 시간이 소요됩니다.

---

## 방법 A: Qdrant 스냅샷으로 빠른 이전 (권장)

### Step 1 — 소스 PC에서 백업

```bash
# 1a. Hermes RA 레포 클론
git clone https://github.com/hnabyz-bot/hermes-ra.git ~/workspace/hermes-ra
cd ~/workspace/hermes-ra

# 1b. Qdrant 스냅샷 생성 (nas_ra_docs + hermes-ra-knowledge)
bash ops/scripts/qdrant_backup.sh ~/.hermes/snapshots/backup_$(date +%Y%m%d)
# → ~/.hermes/snapshots/backup_YYYYMMDD/ 에 저장
```

### Step 2 — 신규 PC로 복사

```bash
# 신규 PC IP 또는 호스트명으로 rsync
rsync -avz ~/.hermes/snapshots/backup_YYYYMMDD/ NEW_PC:~/.hermes/snapshots/restore/
```

### Step 3 — 신규 PC에서 셋업

```bash
# 신규 PC에서 레포 클론
git clone https://github.com/hnabyz-bot/hermes-ra.git ~/workspace/hermes-ra
git clone https://github.com/hnabyz-bot/abyz-lab-n8n.git ~/workspace/n8n-stack

# 자동 셋업 (Qdrant 스냅샷 복원 포함)
cd ~/workspace/hermes-ra
sudo bash ops/scripts/setup_new_pc.sh --restore-snapshot ~/.hermes/snapshots/restore/
```

### Step 4 — 수동 설정 완료

```bash
# 1. 환경 변수 설정
nano /opt/hermes/.env
# GLM_API_KEY, OPENPROJECT_API_KEY, OPENPROJECT_BASE_URL 입력

# 2. NAS 자격증명 설정
sudo nano /etc/samba/nas-ra.creds
# username=drake.lee
# password=YOUR_PASSWORD

# 3. NAS 마운트
sudo mount /mnt/nas-ra
ls /mnt/nas-ra/공통자료/  # 확인

# 4. 서비스 시작
sudo systemctl start hermes-ra-api hermes-oauth-gateway
curl http://localhost:7788/health  # → {"status": "ok"}
```

---

## 방법 B: NAS에서 재인덱싱 (스냅샷 없을 때)

> ⚠️ 수 시간 소요. NAS 접근 가능해야 함.

```bash
# 신규 PC에서
sudo bash ops/scripts/setup_new_pc.sh --reindex
# → indexer_state.db 초기화 → nas_indexer.py 전체 재실행
```

또는 수동으로:
```bash
# indexer_state.db 초기화 (중요: Qdrant 비어있는 경우 필수)
python3 -c "
import sqlite3
conn = sqlite3.connect('~/workspace/n8n-stack/hermes-ra/indexer_state.db')
conn.execute('DELETE FROM indexed_files')
conn.commit()
"
# NAS RAG 재인덱싱
python3 /opt/hermes/nas_indexer.py
```

> **주의**: `indexer_state.db`가 있어도 Qdrant가 비어있으면 반드시 DB 초기화 후 재인덱싱해야 합니다.  
> DB를 초기화하지 않으면 인덱서가 "이미 인덱싱됨"으로 판단하고 건너뜁니다.

---

## 사전 요구사항

### 필수 소프트웨어

```bash
# Qdrant (벡터 DB)
# https://qdrant.tech/documentation/guides/installation/
curl -L https://github.com/qdrant/qdrant/releases/latest/download/qdrant-aarch64-unknown-linux-gnu.tar.gz | tar xz
sudo mv qdrant /usr/local/bin/

# Ollama (임베딩 모델)
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull nomic-embed-text

# Python 패키지
pip3 install fastapi uvicorn requests python-docx python-pptx openpyxl
apt-get install -y poppler-utils cifs-utils
```

### 네트워크 전제 조건

| 항목 | 요구사항 |
|------|---------|
| NAS (Tailscale) | `100.126.59.10` 접근 가능 (Tailscale 설치 필요) |
| Qdrant | `localhost:6333` |
| Ollama | `localhost:11434` |
| OAuth Gateway | `localhost:5055` |
| RA API | `localhost:7788` |

---

## 검증 체크리스트

```bash
# 1. Qdrant 컬렉션 확인
python3 -c "
import urllib.request, json
resp = json.loads(urllib.request.urlopen('http://localhost:6333/collections').read())
for c in resp['result']['collections']:
    info = json.loads(urllib.request.urlopen(f'http://localhost:6333/collections/{c[\"name\"]}').read())
    pts = info['result'].get('points_count', '?')
    print(f'  {c[\"name\"]}: {pts} points')
"
# 기대값: nas_ra_docs: 84592+ points, hermes-ra-knowledge: N+ points

# 2. NAS 마운트 확인
ls /mnt/nas-ra/공통자료/RA/

# 3. RA API 헬스체크
curl http://localhost:7788/health

# 4. 임베딩 테스트
python3 -c "
import urllib.request, json
data = json.dumps({'model': 'nomic-embed-text', 'prompt': 'test'}).encode()
resp = urllib.request.urlopen(urllib.request.Request('http://localhost:11434/api/embeddings', data=data))
emb = json.loads(resp.read())
print('임베딩 차원:', len(emb['embedding']))
"
# 기대값: 768

# 5. NAS RAG 검색 테스트
curl -s -X POST http://localhost:7788/analyze \
  -H 'Content-Type: application/json' \
  -d '{"mail_body": "IEC 60601-1 테스트", "project_id": "test"}' | python3 -m json.tool
```

---

## 설정 파일 위치 요약

| 파일 | 위치 | 용도 |
|------|------|------|
| 스크립트 | `/opt/hermes/*.py` | 런타임 (git에서 복사) |
| 환경 변수 | `/opt/hermes/.env` | API 키 (수동 작성) |
| NAS 자격증명 | `/etc/samba/nas-ra.creds` | CIFS 인증 (수동 작성) |
| NAS fstab | `/etc/fstab` (일부) | NAS 자동 마운트 |
| indexer DB | `n8n-stack git: hermes-ra/indexer_state.db` | 인덱싱 상태 |
| systemd | `/etc/systemd/system/hermes-*.service` | 서비스 관리 |

---

## 데이터 흐름 (이전 후 동일하게 동작)

```
[Gmail 수신] → n8n (ra-request-to-op_v5)
                    ↓
            [RA API :7788]
              ├─ NAS RAG 검색 (Qdrant nas_ra_docs)
              │     ↑ /mnt/nas-ra/ (CIFS)
              ├─ Codex/Copilot/GLM (OAuth Gateway :5055)
              └─ OpenProject 댓글 자동 등록
```

---

*마지막 인덱싱: 2026-05-10 (2,973 파일, 84,592+ 포인트)*
