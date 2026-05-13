#!/usr/bin/env python3
"""
GitHub MD Indexing Script
Indexes all .md files from configured GitHub repos into a Qdrant collection.
"""

import argparse
import base64
import hashlib
import json
import os
import sys
import time
import warnings
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Optional

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPOS = ["holee9/MD-process", "holee9/ra-project"]
GITHUB_TOKEN: Optional[str] = os.environ.get("GITHUB_TOKEN")
QDRANT_URL = "http://localhost:6333"
OLLAMA_URL = "http://localhost:11434"
COLLECTION = "hermes-ra-knowledge"
EMBED_MODEL = "nomic-embed-text"
STATE_FILE = "/tmp/github_index_state.json"
SERVER_PORT = 7791

GITHUB_API = "https://api.github.com"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def github_headers() -> dict:
    h = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


def github_get(url: str, params: dict = None) -> requests.Response:
    """GET with one retry and rate-limit handling."""
    for attempt in range(2):
        try:
            resp = requests.get(url, headers=github_headers(), params=params, timeout=30)
            if resp.status_code in (403, 429):
                print(f"  [warn] Rate limited on {url}, sleeping 2s …", flush=True)
                time.sleep(2)
                continue
            return resp
        except requests.RequestException as exc:
            if attempt == 0:
                print(f"  [warn] Network error ({exc}), retrying …", flush=True)
                time.sleep(1)
            else:
                print(f"  [warn] Network error ({exc}), skipping.", flush=True)
                return None
    return None


def embed_text(text: str) -> Optional[list]:
    """Embed text via Ollama. Returns embedding vector or None on error."""
    payload = {"model": EMBED_MODEL, "prompt": text[:2000]}
    for attempt in range(2):
        try:
            resp = requests.post(
                f"{OLLAMA_URL}/api/embeddings", json=payload, timeout=60
            )
            if resp.status_code == 200:
                return resp.json().get("embedding")
            print(
                f"  [warn] Embed HTTP {resp.status_code}: {resp.text[:200]}", flush=True
            )
        except requests.RequestException as exc:
            if attempt == 0:
                print(f"  [warn] Embed error ({exc}), retrying …", flush=True)
                time.sleep(1)
            else:
                print(f"  [warn] Embed error ({exc}), skipping chunk.", flush=True)
    return None


def make_id(text: str) -> int:
    return int(hashlib.md5(text.encode()).hexdigest()[:15], 16)


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------

def load_state() -> dict:
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ---------------------------------------------------------------------------
# GitHub helpers
# ---------------------------------------------------------------------------

def get_head_sha(repo: str) -> Optional[str]:
    url = f"{GITHUB_API}/repos/{repo}/commits/HEAD"
    resp = github_get(url)
    if resp and resp.status_code == 200:
        return resp.json().get("sha")
    return None


def list_md_files(repo: str) -> list[dict]:
    """Return list of {path, sha, url} for all .md blobs in repo tree."""
    url = f"{GITHUB_API}/repos/{repo}/git/trees/HEAD"
    resp = github_get(url, params={"recursive": "1"})
    if not resp or resp.status_code != 200:
        print(f"  [warn] Could not fetch tree for {repo}: status={getattr(resp, 'status_code', 'N/A')}", flush=True)
        return []
    tree = resp.json().get("tree", [])
    return [
        item for item in tree
        if item.get("type") == "blob" and item.get("path", "").lower().endswith(".md")
    ]


def fetch_file_content(repo: str, path: str) -> Optional[str]:
    """Fetch and decode a file from GitHub Contents API."""
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    resp = github_get(url)
    if not resp or resp.status_code != 200:
        print(f"  [warn] Could not fetch {repo}/{path}: status={getattr(resp, 'status_code', 'N/A')}", flush=True)
        return None
    data = resp.json()
    encoded = data.get("content", "")
    try:
        return base64.b64decode(encoded).decode("utf-8", errors="replace")
    except Exception as exc:
        print(f"  [warn] Base64 decode error for {path}: {exc}", flush=True)
        return None


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def split_by_paragraphs(text: str, max_size: int = 800) -> list[str]:
    """Split text at paragraph boundaries to fit within max_size."""
    paragraphs = text.split("\n\n")
    chunks = []
    current = ""
    for para in paragraphs:
        candidate = (current + "\n\n" + para).strip() if current else para.strip()
        if len(candidate) <= max_size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            # If a single paragraph exceeds max_size, hard-split it
            if len(para) > max_size:
                for i in range(0, len(para), max_size):
                    chunk = para[i : i + max_size].strip()
                    if chunk:
                        chunks.append(chunk)
                current = ""
            else:
                current = para.strip()
    if current:
        chunks.append(current)
    return chunks


def chunk_markdown(text: str, max_chunk: int = 800, min_chunk: int = 50) -> list[str]:
    """
    Split markdown at ## / ### boundaries.
    Each chunk = heading + content until next heading.
    Chunks > max_chunk are further split at paragraph boundaries.
    Chunks < min_chunk are skipped.
    """
    import re

    # Split on ## or ### headings (keep the delimiter)
    parts = re.split(r"(?=^#{2,3} )", text, flags=re.MULTILINE)

    raw_chunks = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len(part) <= max_chunk:
            raw_chunks.append(part)
        else:
            raw_chunks.extend(split_by_paragraphs(part, max_chunk))

    return [c for c in raw_chunks if len(c) >= min_chunk]


# ---------------------------------------------------------------------------
# Qdrant helpers
# ---------------------------------------------------------------------------

def qdrant_delete_by_source(source_path: str):
    """Delete all points matching source_path payload field."""
    url = f"{QDRANT_URL}/collections/{COLLECTION}/points/delete"
    payload = {
        "filter": {
            "must": [
                {
                    "key": "source_path",
                    "match": {"value": source_path},
                }
            ]
        }
    }
    try:
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code not in (200, 202):
            print(f"  [warn] Qdrant delete failed for {source_path}: {resp.text[:200]}", flush=True)
    except requests.RequestException as exc:
        print(f"  [warn] Qdrant delete error: {exc}", flush=True)


def qdrant_upsert(points: list[dict]):
    """Upsert a batch of points into the collection."""
    url = f"{QDRANT_URL}/collections/{COLLECTION}/points"
    payload = {"points": points}
    try:
        resp = requests.put(url, json=payload, timeout=60)
        if resp.status_code not in (200, 202):
            print(f"  [warn] Qdrant upsert failed: {resp.text[:200]}", flush=True)
    except requests.RequestException as exc:
        print(f"  [warn] Qdrant upsert error: {exc}", flush=True)


def qdrant_count() -> int:
    """Return total point count in the collection."""
    url = f"{QDRANT_URL}/collections/{COLLECTION}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("result", {}).get("points_count", 0)
    except requests.RequestException:
        pass
    return -1


# ---------------------------------------------------------------------------
# Per-file indexing
# ---------------------------------------------------------------------------

def index_file(repo: str, path: str) -> int:
    """Fetch, chunk, embed, and upsert one .md file. Returns chunks added."""
    source_path = f"github:{repo}/{path}"
    repo_short = repo.split("/")[-1]

    content = fetch_file_content(repo, path)
    if content is None:
        return 0

    chunks = chunk_markdown(content)
    if not chunks:
        return 0

    # Delete stale points for this file before re-indexing
    qdrant_delete_by_source(source_path)

    indexed_at = datetime.now(timezone.utc).isoformat()
    points = []
    for chunk in chunks:
        vector = embed_text(chunk)
        if vector is None:
            print(f"    [warn] Skipping chunk (embed failed): {chunk[:60]!r}", flush=True)
            continue
        point_id = make_id(source_path + chunk)
        points.append(
            {
                "id": point_id,
                "vector": vector,
                "payload": {
                    "text": chunk,
                    "source_path": source_path,
                    "sheet": repo_short,
                    "doc_type": "regulatory_knowledge",
                    "repo": repo,
                    "file_path": path,
                    "indexed_at": indexed_at,
                },
            }
        )

    if points:
        qdrant_upsert(points)

    return len(points)


# ---------------------------------------------------------------------------
# Full sync
# ---------------------------------------------------------------------------

def sync_repos(repos: list[str] = REPOS) -> dict:
    state = load_state()
    total_files = 0
    total_chunks = 0
    repos_processed = []

    for repo in repos:
        print(f"\n[{repo}] Checking HEAD commit …", flush=True)
        t0 = time.time()

        head_sha = get_head_sha(repo)
        if head_sha and state.get(repo) == head_sha:
            print(f"[{repo}] No changes since last run (sha={head_sha[:8]}), skipping.", flush=True)
            continue

        print(f"[{repo}] Listing .md files …", flush=True)
        md_files = list_md_files(repo)
        print(f"[{repo}] Found {len(md_files)} .md file(s).", flush=True)

        repo_files = 0
        repo_chunks = 0
        for item in md_files:
            path = item["path"]
            print(f"  Indexing: {path}", flush=True)
            added = index_file(repo, path)
            print(f"    → {added} chunk(s) added.", flush=True)
            repo_files += 1
            repo_chunks += added

        elapsed = time.time() - t0
        print(
            f"[{repo}] Done. files={repo_files}, chunks={repo_chunks}, time={elapsed:.1f}s",
            flush=True,
        )

        total_files += repo_files
        total_chunks += repo_chunks
        repos_processed.append(repo)

        # Update state only if we obtained a sha
        if head_sha:
            state[repo] = head_sha
            save_state(state)

    return {
        "repos_processed": repos_processed,
        "total_files": total_files,
        "chunks_added": total_chunks,
    }


# ---------------------------------------------------------------------------
# HTTP server mode
# ---------------------------------------------------------------------------

class SyncHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress default access log
        pass

    def send_json(self, code: int, data: dict):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            kb_points = qdrant_count()
            self.send_json(200, {"status": "ok", "kb_points": kb_points})
        else:
            self.send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/sync":
            print("[server] /sync triggered", flush=True)

            def run():
                result = sync_repos()
                kb = qdrant_count()
                print(f"[server] Sync complete: {result}, kb_points={kb}", flush=True)

            t = Thread(target=run, daemon=True)
            t.start()
            # Return immediately; sync runs in background
            result_preview = sync_repos.__doc__ or "sync started"
            self.send_json(202, {"status": "sync started"})
        else:
            self.send_json(404, {"error": "not found"})


def run_server():
    server = HTTPServer(("0.0.0.0", SERVER_PORT), SyncHandler)
    print(f"[server] Listening on port {SERVER_PORT} …", flush=True)
    print(f"  GET  /health  → {{status, kb_points}}", flush=True)
    print(f"  POST /sync    → trigger full sync", flush=True)
    server.serve_forever()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Index .md files from GitHub repos into Qdrant."
    )
    parser.add_argument(
        "--server",
        action="store_true",
        help=f"Run HTTP server on port {SERVER_PORT} instead of one-shot sync.",
    )
    parser.add_argument(
        "--repos",
        nargs="*",
        default=REPOS,
        metavar="OWNER/REPO",
        help="Override repo list (default: %(default)s).",
    )
    args = parser.parse_args()

    if args.server:
        run_server()
        return

    print("=" * 60, flush=True)
    print("GitHub MD Indexer", flush=True)
    print(f"Repos : {args.repos}", flush=True)
    print(f"Qdrant: {QDRANT_URL}  Collection: {COLLECTION}", flush=True)
    print(f"Embed : {OLLAMA_URL}  Model: {EMBED_MODEL}", flush=True)
    print("=" * 60, flush=True)

    t_start = time.time()
    result = sync_repos(args.repos)
    elapsed = time.time() - t_start

    kb_points = qdrant_count()
    print("\n" + "=" * 60, flush=True)
    print(
        f"Finished. repos_processed={len(result['repos_processed'])}, "
        f"files={result['total_files']}, chunks={result['chunks_added']}, "
        f"time={elapsed:.1f}s",
        flush=True,
    )
    print(f"Total KB points in collection: {kb_points}", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
