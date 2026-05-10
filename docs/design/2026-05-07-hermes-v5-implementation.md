# Hermes v5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade Hermes RA agent to v5: NAS document RAG via Qdrant, attachment text extraction, 3-stage model cascade, and n8n workflow v4 with OP comment posting.

**Architecture:** nas_indexer.py crawls NAS nightly → embeds with nomic-embed-text → stores in Qdrant `nas_ra_docs`. On email arrival, /analyze extracts attachment text, searches Qdrant, generates wp_comment via gemma3:4b → GLM cascade. n8n v4 downloads attachments, calls hermes, posts wp_comment to OP.

**Tech Stack:** Python 3, Qdrant (Docker), Ollama (nomic-embed-text + gemma3:4b), z.ai GLM API (glm-4.5-air + glm-5.1), python-docx, pdftotext, openpyxl, python-pptx, SQLite3, n8n, OpenProject API

---

## Current State (pre-implementation)

| Component | Status |
|---|---|
| Qdrant container | Running at `172.18.0.6:6333` (no host port binding) |
| nomic-embed-text | Installed in Ollama ✓ |
| pdftotext | Installed ✓ |
| python-docx | NOT installed ✗ |
| qdrant-client | NOT installed ✗ |
| GLM_API_KEY .env | Does not exist ✗ |
| nas_ra_docs collection | Does not exist ✗ |
| nas_indexer.py | Does not exist ✗ |
| ra_api_server.py | v5 deployed at /opt/hermes/ (has /qa RAG but /analyze lacks attachment+cascade) |
| n8n workflow | v3 at workflows/ra-request-to-op_v3.json (has WP comment but not from hermes wp_comment) |

## File Map

| File | Action | Responsibility |
|---|---|---|
| `/home/raspi5p/workspace/n8n-stack/docker-compose.yml` | Modify | Add Qdrant port binding |
| `/home/raspi5p/workspace/n8n-stack/hermes-ra/nas_indexer.py` | Create | NAS doc crawl → embed → Qdrant upsert |
| `/opt/hermes/nas_indexer.py` | Deploy | Production copy |
| `/home/raspi5p/workspace/n8n-stack/hermes-ra/ra_api_server.py` | Modify | v5.1: /analyze with attachment + cascade |
| `/opt/hermes/ra_api_server.py` | Deploy | Production copy |
| `/opt/hermes/.env` | Create | GLM_API_KEY storage |
| `/etc/systemd/system/hermes-ra-api.service` | Modify | Add EnvironmentFile directive |
| `/home/raspi5p/workspace/n8n-stack/workflows/ra-request-to-op_v4.json` | Create | n8n workflow with attachment download |

---

## Task 1: Add Qdrant Host Port Binding

**Files:**
- Modify: `/home/raspi5p/workspace/n8n-stack/docker-compose.yml` (lines 87-94)

- [ ] **Step 1: Edit docker-compose.yml — add ports and container_name to qdrant service**

Current qdrant block:
```yaml
  qdrant:
    image: qdrant/qdrant
    restart: unless-stopped
    environment:
      - LD_PRELOAD=
    volumes:
      - qdrant_data:/qdrant/storage
```

Replace with:
```yaml
  qdrant:
    image: qdrant/qdrant
    container_name: n8n-stack-qdrant-1
    restart: unless-stopped
    ports:
      - "127.0.0.1:6333:6333"
    environment:
      - LD_PRELOAD=
    volumes:
      - qdrant_data:/qdrant/storage
```

- [ ] **Step 2: Recreate qdrant container with new port binding**

```bash
cd /home/raspi5p/workspace/n8n-stack
docker compose up -d --no-deps --force-recreate qdrant
```

Expected: `n8n-stack-qdrant-1 Created` + `Started`

- [ ] **Step 3: Verify Qdrant accessible on localhost**

```bash
curl -s http://localhost:6333/collections | python3 -c "import json,sys; d=json.load(sys.stdin); print('OK:', d)"
```

Expected: `OK: {'result': {'collections': [...]}, 'status': 'ok', ...}`

- [ ] **Step 4: Update hardcoded Qdrant IPs in /opt/hermes/ra_api_server.py**

Current lines 101-103 use `http://172.18.0.6:6333`. These still work but are fragile.
Note: we will update these when deploying the new ra_api_server.py in Task 7.

- [ ] **Step 5: Commit**

```bash
cd /home/raspi5p/workspace/n8n-stack
git add docker-compose.yml
git commit -m "feat: expose Qdrant port 6333 on localhost"
```

---

## Task 2: Install Python Prerequisites

- [ ] **Step 1: Install python-docx and qdrant-client**

```bash
sudo pip3 install python-docx qdrant-client --break-system-packages
```

Expected: Successfully installed packages

- [ ] **Step 2: Verify installations**

```bash
python3 -c "import docx; print('python-docx OK')"
python3 -c "from qdrant_client import QdrantClient; print('qdrant-client OK')"
```

Expected: both print OK

---

## Task 3: Create nas_ra_docs Qdrant Collection

- [ ] **Step 1: Create collection**

```bash
python3 - <<'EOF'
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

client = QdrantClient("localhost", port=6333)
client.create_collection(
    collection_name="nas_ra_docs",
    vectors_config=VectorParams(size=768, distance=Distance.COSINE)
)
print("Collection created:", client.get_collection("nas_ra_docs"))
EOF
```

Expected: `Collection created: ...` with `status=green` or `status=yellow` (empty)

- [ ] **Step 2: Verify collection exists**

```bash
curl -s http://localhost:6333/collections/nas_ra_docs | python3 -c "import json,sys; d=json.load(sys.stdin); print('vectors_count:', d['result']['vectors_count'])"
```

Expected: `vectors_count: 0`

---

## Task 4: Write nas_indexer.py

**Files:**
- Create: `/home/raspi5p/workspace/n8n-stack/hermes-ra/nas_indexer.py`

- [ ] **Step 1: Write the file**

```python
#!/usr/bin/env python3
"""Hermes NAS Indexer v1 — crawl NAS docs, embed, upsert to Qdrant nas_ra_docs"""
import os, sqlite3, json, subprocess, hashlib, urllib.request, sys, time
from pathlib import Path
from datetime import datetime

QDRANT_URL = "http://localhost:6333"
OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
COLLECTION = "nas_ra_docs"
STATE_DB = "/home/raspi5p/workspace/n8n-stack/hermes-ra/indexer_state.db"
CHUNK_CHARS = 800    # ~500 tokens
OVERLAP_CHARS = 160  # ~100 tokens
BATCH_SIZE = 50      # points per Qdrant upsert call

SCAN_PATHS = [
    "/mnt/nas-ra/공통자료/DHF (인허가)/",
    "/mnt/nas-ra/변경점문서/",
    "/mnt/nas-ra/회의자료/Project회의/CYAN/인허가문서/",
    "/mnt/nas-ra/회의자료/Project회의/Retrofit/",
    "/mnt/nas-ra/회의자료/Project회의/포터블 CE MDR/",
    "/mnt/nas-ra/회의자료/Project회의/주요 Project 인허가 이슈사항/",
    "/mnt/nas-ra/회의자료/Project회의/미국 방사선등록 EPRC/",
    "/mnt/nas-ra/공통자료/Standard(국제)/",
]

SUPPORTED_EXTS = {".pdf", ".docx", ".doc", ".pptx", ".xlsx"}
SKIP_PREFIXES = ("~$", ".")


def init_db():
    conn = sqlite3.connect(STATE_DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS indexed_files (
        path TEXT PRIMARY KEY,
        mtime REAL,
        size INTEGER,
        qdrant_ids TEXT,
        indexed_at TEXT
    )""")
    conn.commit()
    return conn


def get_file_state(conn, path):
    row = conn.execute("SELECT mtime, size, qdrant_ids FROM indexed_files WHERE path=?", (path,)).fetchone()
    return row  # (mtime, size, qdrant_ids_json) or None


def save_file_state(conn, path, mtime, size, qdrant_ids):
    conn.execute(
        "INSERT OR REPLACE INTO indexed_files (path,mtime,size,qdrant_ids,indexed_at) VALUES(?,?,?,?,?)",
        (path, mtime, size, json.dumps(qdrant_ids), datetime.now().isoformat())
    )
    conn.commit()


def extract_text(filepath):
    ext = Path(filepath).suffix.lower()
    try:
        if ext == ".pdf":
            r = subprocess.run(["pdftotext", "-q", filepath, "-"],
                               capture_output=True, text=True, timeout=60)
            return r.stdout
        elif ext == ".docx":
            import docx
            doc = docx.Document(filepath)
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        elif ext == ".pptx":
            from pptx import Presentation
            prs = Presentation(filepath)
            parts = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        parts.append(shape.text)
            return "\n".join(parts)
        elif ext == ".xlsx":
            import openpyxl
            wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
            parts = []
            for sn in wb.sheetnames:
                ws = wb[sn]
                parts.append(f"[{sn}]")
                for row in ws.iter_rows(values_only=True):
                    cells = [str(c) for c in row if c is not None and str(c).strip()]
                    if cells:
                        parts.append(" | ".join(cells))
            wb.close()
            return "\n".join(parts)
        elif ext in (".doc",):
            r = subprocess.run(
                ["libreoffice", "--headless", "--convert-to", "txt", "--outdir", "/tmp", filepath],
                capture_output=True, timeout=120
            )
            txt = f"/tmp/{Path(filepath).stem}.txt"
            if os.path.exists(txt):
                with open(txt) as f:
                    return f.read()
    except Exception as e:
        print(f"  [extract error] {Path(filepath).name}: {e}", file=sys.stderr)
    return ""


def chunk_text(text):
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_CHARS, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = end - OVERLAP_CHARS
    return chunks


def embed(text):
    data = json.dumps({"model": "nomic-embed-text", "prompt": text}).encode()
    req = urllib.request.Request(OLLAMA_EMBED_URL, data=data,
                                  headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())["embedding"]


def qdrant_upsert(points):
    data = json.dumps({"points": points}).encode()
    req = urllib.request.Request(
        f"{QDRANT_URL}/collections/{COLLECTION}/points?wait=true",
        data=data, headers={"Content-Type": "application/json"}, method="PUT"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def qdrant_delete(ids):
    if not ids:
        return
    data = json.dumps({"points": ids}).encode()
    req = urllib.request.Request(
        f"{QDRANT_URL}/collections/{COLLECTION}/points/delete",
        data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def make_id(path, chunk_index):
    h = hashlib.md5(f"{path}:{chunk_index}".encode()).hexdigest()
    return int(h[:15], 16)  # 60-bit int, safe for Qdrant


def folder_category(path):
    for p in SCAN_PATHS:
        if path.startswith(p):
            return Path(p).name
    return "other"


def index_file(conn, filepath):
    try:
        stat = os.stat(filepath)
    except OSError:
        return "error"
    mtime, size = stat.st_mtime, stat.st_size

    prev = get_file_state(conn, filepath)
    if prev and abs(prev[0] - mtime) < 1 and prev[1] == size:
        return "skip"

    text = extract_text(filepath)
    if not text.strip():
        return "empty"

    chunks = chunk_text(text)
    if not chunks:
        return "empty"

    # Delete old vectors
    if prev and prev[2]:
        old_ids = json.loads(prev[2])
        qdrant_delete(old_ids)

    fname = Path(filepath).name
    category = folder_category(filepath)
    new_ids = []
    batch = []

    for i, chunk in enumerate(chunks):
        try:
            vector = embed(chunk)
        except Exception as e:
            print(f"  [embed error] chunk {i}: {e}", file=sys.stderr)
            continue
        pid = make_id(filepath, i)
        new_ids.append(pid)
        batch.append({
            "id": pid,
            "vector": vector,
            "payload": {
                "file_path": filepath,
                "filename": fname,
                "folder_category": category,
                "modified_at": mtime,
                "chunk_index": i,
                "text": chunk[:500]
            }
        })
        if len(batch) >= BATCH_SIZE:
            qdrant_upsert(batch)
            batch = []

    if batch:
        qdrant_upsert(batch)

    if new_ids:
        save_file_state(conn, filepath, mtime, size, new_ids)

    return f"ok({len(new_ids)}chunks)"


def run():
    conn = init_db()
    stats = {"indexed": 0, "skipped": 0, "empty": 0, "error": 0}
    t0 = time.time()

    for base in SCAN_PATHS:
        if not os.path.exists(base):
            print(f"[skip] not mounted: {base}")
            continue
        print(f"\n[scan] {base}")
        for root, dirs, files in os.walk(base):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            for fname in files:
                if any(fname.startswith(p) for p in SKIP_PREFIXES):
                    continue
                ext = Path(fname).suffix.lower()
                if ext not in SUPPORTED_EXTS:
                    continue
                fpath = os.path.join(root, fname)
                result = index_file(conn, fpath)
                key = "indexed" if result.startswith("ok") else result
                stats[key] = stats.get(key, 0) + 1
                if result.startswith("ok"):
                    print(f"  + {fname} [{result}]")

    conn.close()
    elapsed = int(time.time() - t0)
    print(f"\n=== Done in {elapsed}s ===")
    print(f"  indexed: {stats.get('indexed',0)}, skipped: {stats.get('skip',0)}, "
          f"empty: {stats.get('empty',0)}, error: {stats.get('error',0)}")


if __name__ == "__main__":
    run()
```

- [ ] **Step 2: Copy to /opt/hermes/**

```bash
sudo cp /home/raspi5p/workspace/n8n-stack/hermes-ra/nas_indexer.py /opt/hermes/nas_indexer.py
sudo chmod +x /opt/hermes/nas_indexer.py
```

- [ ] **Step 3: Smoke test (NAS mount check only — don't run full index yet)**

```bash
python3 /opt/hermes/nas_indexer.py 2>&1 | head -20
```

Expected: lines like `[skip] not mounted: /mnt/nas-ra/...` (if NAS not mounted) or `[scan] /mnt/nas-ra/...` if mounted. No Python errors.

- [ ] **Step 4: Commit**

```bash
cd /home/raspi5p/workspace/n8n-stack
git add hermes-ra/nas_indexer.py
git commit -m "feat: add nas_indexer.py for Qdrant NAS document indexing"
```

---

## Task 5: Register nas_indexer Cron

- [ ] **Step 1: Add cron entry**

```bash
(crontab -l 2>/dev/null; echo "0 2 * * * /usr/bin/python3 /opt/hermes/nas_indexer.py >> /var/log/nas_indexer.log 2>&1") | crontab -
```

- [ ] **Step 2: Verify cron entry**

```bash
crontab -l | grep nas_indexer
```

Expected: `0 2 * * * /usr/bin/python3 /opt/hermes/nas_indexer.py >> /var/log/nas_indexer.log 2>&1`

---

## Task 6: GLM API Key Setup

- [ ] **Step 1: Create /opt/hermes/.env** (fill in actual GLM_API_KEY value from z.ai dashboard)

```bash
sudo tee /opt/hermes/.env > /dev/null <<'EOF'
GLM_API_KEY=<paste-actual-key-here>
EOF
sudo chmod 600 /opt/hermes/.env
```

- [ ] **Step 2: Update systemd service to load env file**

Edit `/etc/systemd/system/hermes-ra-api.service`:

Current:
```ini
[Service]
Type=simple
User=raspi5p
ExecStart=/usr/bin/python3 /opt/hermes/ra_api_server.py
Restart=on-failure
RestartSec=5
```

Replace with:
```ini
[Service]
Type=simple
User=raspi5p
EnvironmentFile=/opt/hermes/.env
ExecStart=/usr/bin/python3 /opt/hermes/ra_api_server.py
Restart=on-failure
RestartSec=5
```

```bash
sudo systemctl daemon-reload
```

---

## Task 7: Update ra_api_server.py — /analyze with Attachment + NAS RAG + Cascade

**Files:**
- Modify: `/home/raspi5p/workspace/n8n-stack/hermes-ra/ra_api_server.py`

This updates the v4 `/analyze` endpoint with:
1. Attachment text extraction
2. Qdrant `nas_ra_docs` search
3. wp_comment generation (2nd gemma3:4b prompt)
4. 3-stage model cascade

- [ ] **Step 1: Add imports and constants at the top of ra_api_server.py**

After line 8 (`import json, re, urllib.request, urllib.error`):

```python
import json, re, urllib.request, urllib.error, os, base64, subprocess, tempfile
from pathlib import Path

GLM_API_KEY = os.environ.get("GLM_API_KEY", "")
GLM_BASE_URL = "https://api.z.ai/api/paas/v4/chat/completions"
NAS_QDRANT_SEARCH = "http://localhost:6333/collections/nas_ra_docs/points/search"
NAS_QDRANT_EMBED = "http://localhost:11434/api/embeddings"
```

- [ ] **Step 2: Add attachment text extraction function**

Add after the `clean_body()` function:

```python
def extract_attachment_text(attachment_files):
    """Extract text from attachment_files list [{filename, content_type, data}]. Returns combined string."""
    texts = []
    for att in attachment_files:
        fname = att.get("filename", "")
        data_b64 = att.get("data", "")
        if not data_b64:
            continue
        ext = Path(fname).suffix.lower()
        try:
            raw = base64.b64decode(data_b64)
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(raw)
                tmp_path = tmp.name
            text = ""
            if ext == ".pdf":
                r = subprocess.run(["pdftotext", "-q", tmp_path, "-"],
                                   capture_output=True, text=True, timeout=60)
                text = r.stdout
            elif ext == ".docx":
                import docx
                doc = docx.Document(tmp_path)
                text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            elif ext == ".pptx":
                from pptx import Presentation
                prs = Presentation(tmp_path)
                parts = [shape.text for slide in prs.slides for shape in slide.shapes
                         if hasattr(shape, "text") and shape.text.strip()]
                text = "\n".join(parts)
            elif ext == ".xlsx":
                import openpyxl
                wb = openpyxl.load_workbook(tmp_path, read_only=True, data_only=True)
                rows = []
                for sn in wb.sheetnames:
                    ws = wb[sn]
                    rows.append(f"[{sn}]")
                    for row in ws.iter_rows(values_only=True):
                        cells = [str(c) for c in row if c is not None and str(c).strip()]
                        if cells:
                            rows.append(" | ".join(cells))
                wb.close()
                text = "\n".join(rows)
            os.unlink(tmp_path)
            if text.strip():
                texts.append(f"[{fname}]\n{text[:3000]}")
        except Exception as e:
            texts.append(f"[{fname}] (추출 실패: {e})")
    return "\n\n".join(texts)[:5000]
```

- [ ] **Step 3: Add NAS Qdrant search function**

```python
def search_nas_qdrant(query_text, top_k=5):
    """Embed query and search nas_ra_docs. Returns list of {path, filename, score, excerpt}."""
    try:
        embed_data = json.dumps({"model": "nomic-embed-text", "prompt": query_text}).encode()
        req = urllib.request.Request(NAS_QDRANT_EMBED, data=embed_data,
                                      headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=60) as resp:
            vector = json.loads(resp.read())["embedding"]

        search_data = json.dumps({
            "vector": vector,
            "limit": top_k,
            "with_payload": True,
            "score_threshold": 0.5
        }).encode()
        req2 = urllib.request.Request(NAS_QDRANT_SEARCH, data=search_data,
                                       headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req2, timeout=30) as resp2:
            results = json.loads(resp2.read()).get("result", [])

        return [{
            "path": h["payload"]["file_path"],
            "filename": h["payload"]["filename"],
            "score": round(h["score"], 3),
            "excerpt": h["payload"].get("text", "")[:300]
        } for h in results]
    except Exception:
        return []
```

- [ ] **Step 4: Add quality score calculator**

```python
def calc_quality_score(analysis_dict):
    """Score 0-10 based on action length, checklist items, NAS refs, JSON completeness."""
    score = 0
    # action length
    action = analysis_dict.get("action", "")
    if len(action) > 80:
        score += 2
    elif len(action) >= 30:
        score += 1

    # wp_comment checklist items (count lines starting with digit+dot or -)
    wp = analysis_dict.get("wp_comment", "")
    items = len([l for l in wp.split("\n") if re.match(r"^\s*(\d+\.|[-*])\s", l)])
    if items >= 3:
        score += 2
    elif items >= 2:
        score += 1

    # nas_refs count
    refs = len(analysis_dict.get("nas_refs", []))
    if refs >= 2:
        score += 2
    elif refs >= 1:
        score += 1

    # JSON completeness
    required = ["summary", "org", "region", "task_type", "deadline", "action", "priority"]
    missing = sum(1 for f in required if not analysis_dict.get(f))
    if missing == 0:
        score += 2

    return min(int(score * 1.25), 10)
```

- [ ] **Step 5: Add GLM API caller**

```python
def call_glm(model, prompt, max_tokens=3000):
    """Call z.ai GLM API (OpenAI-compatible). Returns response text or None."""
    if not GLM_API_KEY:
        return None
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.1
    }).encode()
    req = urllib.request.Request(
        GLM_BASE_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GLM_API_KEY}"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]
    except Exception:
        return None
```

- [ ] **Step 6: Add JSON parse helper (used across cascade steps)**

```python
def parse_json_response(raw):
    """Strip markdown/think tags and parse JSON. Returns dict or None."""
    raw = re.sub(r'```json\s*', '', raw)
    raw = re.sub(r'```\s*', '', raw)
    raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL)
    raw = raw.strip()
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
    return None
```

- [ ] **Step 7: Add analyze_mail_v5() — the full pipeline**

```python
ANALYSIS_PROMPT_TEMPLATE = (
    "당신은 의료기기 규제/인허가(RA) 전문가입니다. "
    "아래 공문을 분석하여 JSON만 출력하세요. 다른 텍스트, 설명, 마크다운 없이 순수 JSON만.\n\n"
    "[발신자] {from_addr}\n"
    "[제목] {subject}\n"
    "[본문]\n{body}\n"
    "{attach_section}"
    "\n출력 형식 (모든 필드 필수):\n"
    '{{\n'
    '  "summary": "핵심 내용 3-5줄 요약",\n'
    '  "org": "발신기관명",\n'
    '  "region": "EU/FDA/KR/글로벌/기타",\n'
    '  "task_type": "지원사업/규제변경/인증갱신/심사/공고/기타",\n'
    '  "deadline": "마감기한 또는 null",\n'
    '  "action": "RA담당자가 즉시 취해야 할 구체적 조치 (80자 이상 상세히)",\n'
    '  "priority": "high/medium/low",\n'
    '  "attachments_note": "첨부파일 주요사항 또는 null"\n'
    '}}'
)

WP_COMMENT_PROMPT_TEMPLATE = (
    "당신은 의료기기 RA 전담 에이전트입니다.\n"
    "아래 정보를 바탕으로 RA 담당자가 즉시 업무를 시작할 수 있도록 "
    "마크다운 형식의 체크리스트와 관련 문서 가이드를 작성하세요.\n\n"
    "[요청 분석 결과]\n{analysis}\n\n"
    "[관련 NAS 문서]\n{nas_refs}\n\n"
    "[첨부파일 내용]\n{attachment_text}\n\n"
    "출력 형식 (마크다운):\n"
    "## 🤖 Hermes RA 가이드\n\n"
    "### 요청 분석\n(3줄 요약)\n\n"
    "### 업무 체크리스트\n1. ...\n2. ...\n3. ...\n\n"
    "### 관련 NAS 문서\n- `파일경로` — 발췌: ..."
)

def run_analysis_prompt(from_addr, subject, body, attachments, attachment_text):
    """Run the 1st stage prompt via Ollama gemma3:4b. Returns raw JSON string."""
    attach_section = ""
    if attachments:
        attach_section += f"\n[첨부파일 목록]\n{attachments}"
    if attachment_text:
        attach_section += f"\n[첨부파일 내용 요약]\n{attachment_text[:2000]}"

    prompt = ANALYSIS_PROMPT_TEMPLATE.format(
        from_addr=from_addr,
        subject=subject,
        body=clean_body(body),
        attach_section=attach_section
    )

    req_data = json.dumps({
        'model': 'gemma3:4b',
        'prompt': prompt,
        'stream': False,
        'options': {'temperature': 0.1, 'num_predict': 800}
    }).encode()
    req = urllib.request.Request(
        'http://localhost:11434/api/generate',
        data=req_data,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read()).get('response', '')


def run_wp_comment_prompt(analysis_dict, nas_refs, attachment_text):
    """Run 2nd stage prompt to generate wp_comment. Returns markdown string."""
    nas_text = "\n".join(
        f"- `{r['path']}` (score: {r['score']})\n  발췌: {r['excerpt']}"
        for r in nas_refs
    ) if nas_refs else "관련 NAS 문서 없음"

    analysis_text = json.dumps(analysis_dict, ensure_ascii=False, indent=2)

    prompt = WP_COMMENT_PROMPT_TEMPLATE.format(
        analysis=analysis_text,
        nas_refs=nas_text,
        attachment_text=(attachment_text or "없음")[:1500]
    )

    req_data = json.dumps({
        'model': 'gemma3:4b',
        'prompt': prompt,
        'stream': False,
        'options': {'temperature': 0.2, 'num_predict': 600}
    }).encode()
    req = urllib.request.Request(
        'http://localhost:11434/api/generate',
        data=req_data,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        raw = json.loads(resp.read()).get('response', '')
        raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL)
        return raw.strip()


def _build_glm_analysis_prompt(from_addr, subject, body, attachments, attachment_text):
    """Same as run_analysis_prompt but returns prompt string for GLM (not Ollama)."""
    attach_section = ""
    if attachments:
        attach_section += f"\n[첨부파일 목록]\n{attachments}"
    if attachment_text:
        attach_section += f"\n[첨부파일 내용 요약]\n{attachment_text[:2000]}"
    return ANALYSIS_PROMPT_TEMPLATE.format(
        from_addr=from_addr,
        subject=subject,
        body=clean_body(body),
        attach_section=attach_section
    )


def analyze_mail_v5(from_addr, subject, body, attachments='', attachment_files=None):
    """
    Full v5 pipeline:
    1. Extract attachment text
    2. Qdrant NAS search
    3. gemma3:4b analysis → quality cascade
    4. wp_comment generation
    """
    attachment_text = ""
    if attachment_files:
        attachment_text = extract_attachment_text(attachment_files)

    # NAS semantic search
    query = f"{subject} {body[:500]} {attachment_text[:500]}"
    nas_refs = search_nas_qdrant(query, top_k=5)

    # Stage 1: gemma3:4b analysis
    error_result = {
        'summary': '', 'org': '', 'region': '', 'task_type': '',
        'deadline': None, 'action': '', 'priority': 'medium',
        'attachments_note': None, 'wp_comment': '', 'nas_refs': nas_refs
    }
    try:
        raw1 = run_analysis_prompt(from_addr, subject, body, attachments, attachment_text)
        result = parse_json_response(raw1)
    except Exception as e:
        error_result['summary'] = f'분석오류: {e}'
        return error_result

    if not result:
        error_result['summary'] = 'JSON파싱실패'
        return error_result

    result['nas_refs'] = nas_refs

    # Quality gate → cascade
    score = calc_quality_score(result)
    if score < 8 and GLM_API_KEY:
        glm_prompt = _build_glm_analysis_prompt(from_addr, subject, body, attachments, attachment_text)
        if score < 5:
            glm_raw = call_glm("glm-5.1", glm_prompt, max_tokens=3000)
        else:
            glm_raw = call_glm("glm-4.5-air", glm_prompt, max_tokens=2000)
            if glm_raw:
                glm_result = parse_json_response(glm_raw)
                if glm_result:
                    glm_result['nas_refs'] = nas_refs
                    score2 = calc_quality_score(glm_result)
                    if score2 < 7:
                        glm_raw = call_glm("glm-5.1", glm_prompt, max_tokens=3000)
                    else:
                        result = glm_result
                        glm_raw = None
        if glm_raw:
            glm_result = parse_json_response(glm_raw)
            if glm_result:
                glm_result['nas_refs'] = nas_refs
                result = glm_result

    # Stage 2: wp_comment generation
    try:
        wp_comment = run_wp_comment_prompt(result, nas_refs, attachment_text)
    except Exception:
        wp_comment = ""
    result['wp_comment'] = wp_comment

    # Ensure nas_refs is in result
    if 'nas_refs' not in result:
        result['nas_refs'] = nas_refs

    return result
```

- [ ] **Step 8: Update the /analyze HTTP handler to call analyze_mail_v5**

In the `do_POST` method, find the `/analyze` block:
```python
        if self.path == '/analyze':
            # v4 endpoint — unchanged behaviour
            try:
                data = json.loads(self.rfile.read(length).decode('utf-8'))
                result = analyze_mail(
                    data.get('from', ''),
                    data.get('subject', ''),
                    data.get('body', ''),
                    data.get('attachments', '')
                )
                self._send_json(200, result)
```

Replace with:
```python
        if self.path == '/analyze':
            try:
                data = json.loads(self.rfile.read(length).decode('utf-8'))
                result = analyze_mail_v5(
                    data.get('from', ''),
                    data.get('subject', ''),
                    data.get('body', ''),
                    data.get('attachments', ''),
                    data.get('attachment_files', None)
                )
                self._send_json(200, result)
```

- [ ] **Step 9: Update version string**

Change:
```python
    print('Hermes RA API server v5 running on port 7788')
```
To:
```python
    print('Hermes RA API server v5.1 running on port 7788')
```

Also update Qdrant URLs from hardcoded `172.18.0.6:6333` to `localhost:6333`:
```python
QDRANT_SEARCH_URL = 'http://localhost:6333/collections/hermes-ra-knowledge/points/search'
QDRANT_COLLECTION_URL = 'http://localhost:6333/collections/hermes-ra-knowledge'
QDRANT_SCROLL_URL = 'http://localhost:6333/collections/hermes-ra-knowledge/points/scroll'
```

- [ ] **Step 10: Copy to /opt/hermes/ and restart service**

```bash
sudo cp /home/raspi5p/workspace/n8n-stack/hermes-ra/ra_api_server.py /opt/hermes/ra_api_server.py
sudo systemctl restart hermes-ra-api
sleep 3
systemctl status hermes-ra-api | grep -E "Active|running"
```

Expected: `Active: active (running)`

- [ ] **Step 11: Smoke test /analyze**

```bash
curl -s -X POST http://localhost:7788/analyze \
  -H "Content-Type: application/json" \
  -d '{"from":"test@test.com","subject":"CE 인증 갱신 문의","body":"안녕하세요. CYAN 모델의 CE MDR 인증 갱신 일정을 문의드립니다.","attachments":"","attachment_files":[]}' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('summary:', d.get('summary','')[:80]); print('wp_comment:', bool(d.get('wp_comment'))); print('nas_refs:', len(d.get('nas_refs',[])))"
```

Expected: `summary: ...`, `wp_comment: True`, `nas_refs: 0` (collection empty until first NAS index run)

- [ ] **Step 12: Commit**

```bash
cd /home/raspi5p/workspace/n8n-stack
git add hermes-ra/ra_api_server.py
git commit -m "feat: hermes v5.1 — /analyze with attachment extraction, NAS RAG, 3-stage cascade"
```

---

## Task 8: n8n Workflow v4

**Files:**
- Create: `/home/raspi5p/workspace/n8n-stack/workflows/ra-request-to-op_v4.json`

The v3 workflow already has 17 nodes. v4 adds:
1. Gmail attachment download (before hermes call)
2. Updated hermes call body with `attachment_files`
3. OP comment now uses `hermes.wp_comment` field

**Changes from v3:**
- After `메일 파싱` node: add `첨부파일 다운로드` Code node
- `hermes 분석 API` HTTP Request: add `attachment_files` to body
- `WP 댓글 생성` Code node: use `{{ $('hermes 분석 API').item.json.wp_comment }}` as comment body

- [ ] **Step 1: Export v3 workflow from n8n UI**

Navigate to: `https://n8n.abyz-lab.work` → Workflows → `ra-request-to-op_v3` → `...` menu → Export

Save as: `/home/raspi5p/workspace/n8n-stack/workflows/ra-request-to-op_v3_export.json`

- [ ] **Step 2: Create attachment download Code node**

In the exported JSON, add this node after `메일 파싱`:

```json
{
  "name": "첨부파일 다운로드",
  "type": "n8n-nodes-base.code",
  "parameters": {
    "language": "javaScript",
    "jsCode": "// Download Gmail attachments via Gmail API\nconst items = $input.all();\nconst results = [];\n\nfor (const item of items) {\n  const parsed = item.json;\n  const attachments = parsed.attachments || [];\n  const messageId = parsed.messageId;\n  const attachment_files = [];\n\n  for (const att of attachments) {\n    if (!att.attachmentId) continue;\n    try {\n      const response = await $helpers.httpRequest({\n        method: 'GET',\n        url: `https://gmail.googleapis.com/gmail/v1/users/me/messages/${messageId}/attachments/${att.attachmentId}`,\n        authentication: 'predefinedCredentialType',\n        nodeCredentialType: 'gmailOAuth2Api',\n      });\n      attachment_files.push({\n        filename: att.filename,\n        content_type: att.mimeType || 'application/octet-stream',\n        data: response.data  // base64url from Gmail API\n      });\n    } catch (e) {\n      // Skip failed attachment\n    }\n  }\n\n  results.push({\n    json: { ...parsed, attachment_files }\n  });\n}\n\nreturn results;"
  },
  "position": [<after 메일 파싱 position>],
  "id": "attachment-download-v4"
}
```

- [ ] **Step 3: Update hermes 분석 API node body**

Find the `hermes 분석 API` HTTP Request node. Update the body:

```json
{
  "from": "={{ $json.from }}",
  "subject": "={{ $json.subject }}",
  "body": "={{ $json.body }}",
  "attachments": "={{ $json.attachments_str }}",
  "attachment_files": "={{ $json.attachment_files || [] }}"
}
```

- [ ] **Step 4: Update WP 댓글 생성 code node to use hermes wp_comment**

```javascript
// Use hermes wp_comment if available, else build basic comment
const hermes = $('hermes 분석 API').item.json;
const wp_comment = hermes.wp_comment || '';
const nas_refs = hermes.nas_refs || [];

let comment = wp_comment;

if (!comment) {
  // Fallback: build basic comment from hermes fields
  comment = `## Hermes RA 분석\n\n**요약**: ${hermes.summary || ''}\n\n**조치**: ${hermes.action || ''}\n\n**우선순위**: ${hermes.priority || 'medium'}`;
}

return [{ json: { comment_body: comment } }];
```

- [ ] **Step 5: Verify WP 댓글 POST node**

The `WP 댓글 POST` node should POST to:
```
POST https://plm.abyz-lab.work/api/v3/work_packages/{{ $('결과 통합').item.json.wp_id }}/activities
Body: { "comment": { "raw": "{{ $json.comment_body }}" } }
onError: continueRegularOutput
```

Confirm this is already configured in v3 or adjust if needed.

- [ ] **Step 6: Save as v4 and import to n8n**

Save the modified JSON as `ra-request-to-op_v4.json`.

Import via n8n UI: Settings → Import workflow → select file.

Activate workflow (deactivate v3 first).

- [ ] **Step 7: Manual test in n8n**

Trigger the workflow manually with a test email. Verify:
- `첨부파일 다운로드` node runs without error
- `hermes 분석 API` returns `wp_comment` field
- `WP 댓글 POST` returns 201 Created

---

## Task 9: E2E Verification

- [ ] **Step 1: Verify Qdrant collection status**

```bash
curl -s http://localhost:6333/collections/nas_ra_docs | python3 -c "
import json,sys
d=json.load(sys.stdin)
r=d['result']
print('status:', r['status'])
print('vectors_count:', r['vectors_count'])
"
```

Expected: `status: green`, `vectors_count: 0` (until first NAS index run)

- [ ] **Step 2: Run a small manual index test (if NAS is mounted)**

```bash
# Only index 1 file as smoke test
python3 - <<'EOF'
import sys
sys.argv = ['nas_indexer']
import importlib.util, os
spec = importlib.util.spec_from_file_location("nas_indexer", "/opt/hermes/nas_indexer.py")
mod = importlib.util.load_from_spec(spec)
# Just test extract on one known file
from pathlib import Path
test_files = []
for base in ["/mnt/nas-ra/공통자료/DHF (인허가)/"]:
    if not os.path.exists(base):
        print(f"[skip] {base}")
        continue
    for f in Path(base).iterdir():
        if f.suffix.lower() in {".pdf", ".docx"}:
            test_files.append(str(f))
            break
if test_files:
    from nas_indexer import extract_text
    t = extract_text(test_files[0])
    print(f"Extracted {len(t)} chars from {test_files[0]}")
else:
    print("No test file found (NAS not mounted?)")
EOF
```

- [ ] **Step 3: Test /analyze with attachment payload**

```bash
# Create a minimal test PDF (or use base64 of known file)
PAYLOAD='{"from":"test@institution.kr","subject":"MDR 인증 갱신 심사 일정 통보","body":"안녕하세요. 귀사의 CYAN 모델 MDR 인증 갱신 심사 일정이 2026-06-15로 확정되었습니다. 아래 서류를 준비해 주시기 바랍니다.","attachments":"심사일정표.pdf","attachment_files":[]}'
curl -s -X POST http://localhost:7788/analyze \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print('org:', d.get('org'))
print('task_type:', d.get('task_type'))
print('priority:', d.get('priority'))
print('wp_comment chars:', len(d.get('wp_comment','')))
print('nas_refs:', len(d.get('nas_refs',[])))
"
```

Expected: all fields populated, `wp_comment chars > 0`

- [ ] **Step 4: Check hermes service health**

```bash
curl -s http://localhost:7788/health | python3 -c "
import json,sys
d=json.load(sys.stdin)
print('status:', d['status'])
print('ollama:', d['ollama'])
print('qdrant:', d['qdrant'])
"
```

Expected: `status: ok`, both `True`

- [ ] **Step 5: Push to GitHub**

```bash
cd /home/raspi5p/workspace/n8n-stack
git push origin main
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| Qdrant Docker 포트 바인딩 | Task 1 |
| nas_ra_docs collection 생성 | Task 3 |
| nas_indexer.py (NAS crawl + embed + upsert) | Task 4 |
| cron 매일 02:00 | Task 5 |
| GLM API key 설정 | Task 6 |
| attachment_files 텍스트 추출 | Task 7 Steps 2-3 |
| Qdrant 검색 top-5 | Task 7 Step 3 |
| gemma3:4b 1차 분석 | Task 7 Step 7 |
| gemma3:4b 2차 wp_comment | Task 7 Step 7 |
| 3단계 캐스케이드 (score 기반) | Task 7 Steps 4-7 |
| wp_comment + nas_refs 출력 필드 | Task 7 Step 7 |
| n8n 첨부파일 다운로드 노드 | Task 8 Step 2 |
| hermes 호출 시 attachment_files 전달 | Task 8 Step 3 |
| OP 코멘트 wp_comment 사용 | Task 8 Steps 4-5 |
| nomic-embed-text 설치 | Already done ✓ |
| pdftotext 설치 | Already done ✓ |

**All spec requirements covered.** python-docx and qdrant-client installation covered in Task 2.

**Type consistency verified:** `analyze_mail_v5()` returns dict with `nas_refs` (list of dicts with path/filename/score/excerpt) — matches `search_nas_qdrant()` output. `wp_comment` is string in both generator and HTTP response.
