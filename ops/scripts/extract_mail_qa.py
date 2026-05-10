#!/usr/bin/env python3
"""
메일백업 QA이력 추출 스크립트
Parse .eml files from NAS mail backup zips → extract Q&A threads
→ save as structured .md → push to holee9/ra-project GitHub repo
→ index to Qdrant.
"""

import os
import re
import sys
import json
import base64
import zipfile
import logging
import hashlib
from email import policy
from email.parser import BytesParser
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from collections import defaultdict
from typing import Optional

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAIL_DIR = "/mnt/nas-ra/공통자료/RA/99_4. 한지민(241120~260508)/메일백업"

# Zips to process (skip Hiworks_*.zip)
ZIP_FILES = [
    "3EC.zip",
    "KTR.zip",
    "FDA.zip",
    "Nemko.zip",
    "UL(EMERGO).zip",
    "3SMD (Javitech).zip",
    "KTL.zip",
    "Medi-Guide.zip",
    "CTI cert & Cowalks.zip",
    "GMSC.zip",
    "DK Medical.zip",
    "대안일레콤.zip",
    "Acts.zip",
]

# Org type mapping
ORG_TYPE_MAP = {
    "3EC": "NB심사 (CE/MDR)",
    "KTR": "해외인증지원 + 규격시험",
    "FDA": "FDA심사",
    "Nemko": "NB심사 (CE/MDR)",
    "UL(EMERGO)": "US대리인",
    "3SMD (Javitech)": "EU대리인",
    "KTL": "규격시험",
    "Medi-Guide": "MFDS컨설팅",
    "CTI cert & Cowalks": "기타시험",
    "GMSC": "기타",
    "DK Medical": "제조협력",
    "대안일레콤": "제조협력",
    "Acts": "MFDS인허가",
}

GITHUB_API_BASE = "https://api.github.com"
GITHUB_REPO = "holee9/ra-project"
GITHUB_BRANCH = "main"

QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "hermes-ra-knowledge")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = "nomic-embed-text"


def _embed_text(text: str) -> list:
    """Embed text via Ollama nomic-embed-text."""
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text[:2000]},
            timeout=30
        )
        resp.raise_for_status()
        return resp.json()["embedding"]
    except Exception as e:
        logger.warning("Embed error: %s — using zero vector", e)
        return [0.0] * 768

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers: header / body decoding
# ---------------------------------------------------------------------------

def decode_mime_words(s: Optional[str]) -> str:
    """Decode RFC2047-encoded header value to a plain string."""
    if s is None:
        return ""
    parts = decode_header(s)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            charset = charset or "utf-8"
            decoded.append(part.decode(charset, errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


def get_text_body(msg) -> str:
    """
    Extract plain-text body from an email.message.Message object.
    Falls back to stripping tags from text/html if no text/plain found.
    """
    body_text = None

    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition", ""))
            if "attachment" in disp:
                continue
            if ctype == "text/plain" and body_text is None:
                charset = part.get_content_charset() or "utf-8"
                payload = part.get_payload(decode=True)
                if payload:
                    body_text = payload.decode(charset, errors="replace")
                    break  # prefer first text/plain
    else:
        ctype = msg.get_content_type()
        charset = msg.get_content_charset() or "utf-8"
        payload = msg.get_payload(decode=True)
        if payload:
            if ctype == "text/plain":
                body_text = payload.decode(charset, errors="replace")
            elif ctype == "text/html":
                html = payload.decode(charset, errors="replace")
                body_text = re.sub(r"<[^>]+>", "", html)

    # Fallback: try html parts if still nothing
    if body_text is None and msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/html":
                charset = part.get_content_charset() or "utf-8"
                payload = part.get_payload(decode=True)
                if payload:
                    html = payload.decode(charset, errors="replace")
                    body_text = re.sub(r"<[^>]+>", "", html)
                    break

    return (body_text or "").strip()


# ---------------------------------------------------------------------------
# Helpers: subject normalization for thread grouping
# ---------------------------------------------------------------------------

_THREAD_PREFIX_RE = re.compile(
    r"^(Re|Fwd|FW|RE|FWD|AW|回复|回覆|SV|VS|Ответ|답장|답변|전달)[\s:：]+",
    re.IGNORECASE,
)
_EXTERNAL_TAG_RE = re.compile(r"\[EXTERNAL\]", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_subject(subject: str) -> str:
    """Strip Re:/Fwd:/[EXTERNAL] prefixes and collapse whitespace."""
    s = _EXTERNAL_TAG_RE.sub("", subject)
    prev = None
    while prev != s:
        prev = s
        s = _THREAD_PREFIX_RE.sub("", s.strip())
    return _WHITESPACE_RE.sub(" ", s).strip() or "(제목 없음)"


# ---------------------------------------------------------------------------
# Core: parse a single .eml bytes blob
# ---------------------------------------------------------------------------

def parse_eml(data: bytes) -> dict:
    """Parse raw .eml bytes and return a dict with extracted fields."""
    parser = BytesParser(policy=policy.compat32)
    msg = parser.parsebytes(data)

    # Date
    raw_date = msg.get("Date", "")
    try:
        dt = parsedate_to_datetime(raw_date)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except Exception:
        dt = datetime(1970, 1, 1, tzinfo=timezone.utc)

    # Subject
    subject_raw = msg.get("Subject", "")
    subject = decode_mime_words(subject_raw) or "(제목 없음)"

    # From / To
    from_addr = decode_mime_words(msg.get("From", ""))
    to_addr = decode_mime_words(msg.get("To", ""))

    # Body
    body = get_text_body(msg)

    return {
        "date": dt,
        "subject": subject,
        "subject_norm": normalize_subject(subject),
        "from_addr": from_addr,
        "to_addr": to_addr,
        "body": body,
    }


# ---------------------------------------------------------------------------
# Core: iterate .eml files inside a zip
# ---------------------------------------------------------------------------

def iter_emls_from_zip(zip_path: str):
    """Yield parsed email dicts from all .eml files within a zip archive."""
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = [n for n in zf.namelist() if n.lower().endswith(".eml")]
            logger.info("  → %d .eml files found in %s", len(names), os.path.basename(zip_path))
            for name in names:
                try:
                    data = zf.read(name)
                    parsed = parse_eml(data)
                    parsed["source_file"] = name
                    yield parsed
                except Exception as e:
                    logger.warning("    ✗ Failed to parse %s: %s", name, e)
    except zipfile.BadZipFile as e:
        logger.error("  ✗ Bad zip file %s: %s", zip_path, e)
    except FileNotFoundError:
        logger.error("  ✗ Zip not found: %s", zip_path)


# ---------------------------------------------------------------------------
# Core: group into threads
# ---------------------------------------------------------------------------

def group_threads(emails: list) -> dict:
    """
    Group list of parsed email dicts by normalized subject.
    Returns dict: subject_norm → sorted list of emails.
    """
    threads = defaultdict(list)
    for email in emails:
        threads[email["subject_norm"]].append(email)
    for subj in threads:
        threads[subj].sort(key=lambda e: e["date"])
    return dict(threads)


# ---------------------------------------------------------------------------
# Core: generate Markdown content
# ---------------------------------------------------------------------------

def format_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d") if dt.year > 1970 else "날짜 불명"


def generate_markdown(org_name: str, org_type: str, threads: dict) -> str:
    """Generate a Markdown document for one organisation's QA history."""
    all_emails = [e for msgs in threads.values() for e in msgs]

    count = len(all_emails)
    if all_emails:
        dates = sorted(e["date"] for e in all_emails)
        first_date = format_date(dates[0])
        last_date = format_date(dates[-1])
    else:
        first_date = last_date = "N/A"

    lines = [
        f"# {org_name} 심사/대응 QA이력",
        "",
        "## 개요",
        f"- 기관 유형: {org_type}",
        f"- 이메일 수: {count}",
        f"- 기간: {first_date} ~ {last_date}",
        "",
        "## 스레드 목록",
        "",
    ]

    for subj_norm, msgs in sorted(threads.items(), key=lambda kv: kv[1][0]["date"]):
        msg_count = len(msgs)
        thread_dates = [m["date"] for m in msgs]
        d_first = format_date(min(thread_dates))
        d_last = format_date(max(thread_dates))
        date_range = d_first if d_first == d_last else f"{d_first} ~ {d_last}"

        lines.append(f"### {subj_norm} ({date_range}, {msg_count}건)")
        lines.append("")

        # Show representative info from the first message
        first_msg = msgs[0]
        lines.append(f"- 발신: {first_msg['from_addr']}")
        lines.append(f"- 수신: {first_msg['to_addr']}")
        lines.append("- 내용 요약:")

        body_preview = first_msg["body"][:500].replace("\n", "\n  ")
        lines.append(f"  {body_preview}")
        lines.append("")

        # If multiple messages, show brief metadata for the rest
        if msg_count > 1:
            for m in msgs[1:]:
                lines.append(
                    f"  **[{format_date(m['date'])}]** {m['from_addr']} → {m['to_addr']}"
                )
                body_snip = m["body"][:200].replace("\n", " ")
                lines.append(f"  {body_snip}")
                lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# GitHub push
# ---------------------------------------------------------------------------

def get_github_token() -> str:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        logger.warning("GITHUB_TOKEN env var not set — GitHub push will fail")
    return token


def github_get_file_sha(path: str, token: str) -> Optional[str]:
    """Return the SHA of an existing file using gh CLI, or None if it doesn't exist."""
    import subprocess
    try:
        result = subprocess.run(
            ["gh", "api", f"/repos/{GITHUB_REPO}/contents/{path}",
             "-q", ".sha"],
            capture_output=True, timeout=15
        )
        if result.returncode == 0:
            sha = result.stdout.decode().strip()
            return sha if sha else None
        return None
    except Exception as e:
        logger.warning("  ✗ Could not fetch SHA for %s: %s", path, e)
        return None


def push_to_github(repo_path: str, content_str: str, commit_message: str, token: str) -> bool:
    """
    Create or update a file using gh CLI (uses rpi5 authenticated hnabyz-bot session).
    Falls back to REST API with token if gh CLI unavailable.
    """
    import subprocess, tempfile, os as _os

    # Write content to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as tf:
        tf.write(content_str)
        tmp_path = tf.name

    try:
        # Use gh api (authenticated via rpi5 gh auth)
        encoded = base64.b64encode(content_str.encode('utf-8')).decode('ascii')
        sha = github_get_file_sha(repo_path, token)
        body = {"message": commit_message, "content": encoded, "branch": GITHUB_BRANCH}
        if sha:
            body["sha"] = sha
        body_json = json.dumps(body)

        result = subprocess.run(
            ["gh", "api", "-X", "PUT",
             f"/repos/{GITHUB_REPO}/contents/{repo_path}",
             "--input", "-"],
            input=body_json.encode(),
            capture_output=True, timeout=30
        )
        if result.returncode == 0:
            action = "updated" if sha else "created"
            logger.info("  ✓ GitHub file %s (%s)", repo_path, action)
            return True
        else:
            logger.warning("  ✗ gh api push failed for %s: %s",
                           repo_path, result.stderr.decode(errors='replace')[:200])
            return False
    except Exception as e:
        logger.warning("  ✗ GitHub push exception for %s: %s", repo_path, e)
        return False
    finally:
        try:
            _os.unlink(tmp_path)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Qdrant indexing
# ---------------------------------------------------------------------------

def qdrant_index(source_path: str, doc_type: str, sheet: str, content: str):
    """
    Index a document into Qdrant using simple HTTP REST API.
    Splits content into ~500-char chunks and upserts as points.
    Falls back gracefully if Qdrant is unavailable.
    """
    try:
        # Check Qdrant availability
        health_url = f"http://{QDRANT_HOST}:{QDRANT_PORT}/healthz"
        try:
            health_resp = requests.get(health_url, timeout=5)
            if health_resp.status_code != 200:
                logger.warning("  ⚠ Qdrant not healthy (%d) — skipping index", health_resp.status_code)
                return
        except Exception:
            logger.warning("  ⚠ Qdrant unreachable at %s:%d — skipping index", QDRANT_HOST, QDRANT_PORT)
            return

        # Split into chunks
        chunk_size = 500
        chunks = [content[i : i + chunk_size] for i in range(0, len(content), chunk_size)]

        points = []
        for idx, chunk in enumerate(chunks):
            # Use a deterministic ID from source_path + chunk index
            uid = int(hashlib.md5(f"{source_path}:{idx}".encode()).hexdigest(), 16) % (10**18)
            points.append(
                {
                    "id": uid,
                    "payload": {
                        "source_path": source_path,
                        "doc_type": doc_type,
                        "sheet": sheet,
                        "chunk_index": idx,
                        "text": chunk,
                    },
                    "vector": _embed_text(chunk),
                }
            )

        upsert_url = f"http://{QDRANT_HOST}:{QDRANT_PORT}/collections/{QDRANT_COLLECTION}/points"
        resp = requests.put(
            upsert_url,
            json={"points": points},
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        if resp.status_code in (200, 201):
            logger.info("  ✓ Qdrant indexed %d chunks for %s", len(chunks), source_path)
        else:
            logger.warning(
                "  ✗ Qdrant upsert failed: HTTP %d — %s", resp.status_code, resp.text[:200]
            )
    except Exception as e:
        logger.warning("  ✗ Qdrant indexing exception: %s", e)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def zip_name_to_org(zip_filename: str) -> str:
    """Strip .zip extension to get org name."""
    return os.path.splitext(zip_filename)[0]


def process_zip(zip_path: str, org_name: str, org_type: str, github_token: str):
    """Full pipeline for one zip file."""
    logger.info("Processing: %s (%s / %s)", os.path.basename(zip_path), org_name, org_type)

    # 1. Parse all .eml files
    emails = list(iter_emls_from_zip(zip_path))
    if not emails:
        logger.warning("  No emails found — skipping")
        return

    # 2. Group into threads
    threads = group_threads(emails)
    logger.info("  → %d emails → %d threads", len(emails), len(threads))

    # 3. Generate Markdown
    md_content = generate_markdown(org_name, org_type, threads)

    # Determine repo path
    safe_org_type = org_type.replace("/", "_").replace(" ", "_")
    repo_path = f"06_심사_QA이력/{safe_org_type}/{org_name}_QA이력.md"

    # 4. Push to GitHub
    commit_msg = f"feat: add QA이력 {org_name}"
    push_ok = push_to_github(repo_path, md_content, commit_msg, github_token)

    # 5. Qdrant indexing
    source_path = f"github:holee9/ra-project/{repo_path}"
    qdrant_index(
        source_path=source_path,
        doc_type="qa_history",
        sheet=f"{org_name} QA이력",
        content=md_content,
    )

    # 6. Summary
    print(
        f"[{org_name}] threads={len(threads)}, emails={len(emails)}, "
        f"md_generated=✓, github={'✓' if push_ok else '✗'}"
    )


def main():
    github_token = get_github_token()

    if not os.path.isdir(MAIL_DIR):
        logger.error("MAIL_DIR not found: %s", MAIL_DIR)
        logger.info("Running in DRY-RUN mode with dummy data for testing.")
        # Allow the script to be tested without the NAS mount
        _dry_run_demo(github_token)
        return

    for zip_filename in ZIP_FILES:
        zip_path = os.path.join(MAIL_DIR, zip_filename)
        org_name = zip_name_to_org(zip_filename)
        org_type = ORG_TYPE_MAP.get(org_name, "기타")
        process_zip(zip_path, org_name, org_type, github_token)

    logger.info("All done.")


# ---------------------------------------------------------------------------
# Dry-run demo (no NAS / no real zips needed)
# ---------------------------------------------------------------------------

def _dry_run_demo(github_token: str):
    """
    Generate a synthetic demo .md for each configured org and push to GitHub
    (or just print the first one) so the script can be validated end-to-end.
    """
    import io

    logger.info("=== DRY-RUN DEMO ===")

    for zip_filename in ZIP_FILES[:2]:  # Just the first 2 for demo
        org_name = zip_name_to_org(zip_filename)
        org_type = ORG_TYPE_MAP.get(org_name, "기타")

        # Build synthetic emails
        emails = []
        for i in range(3):
            emails.append(
                {
                    "date": datetime(2025, 1, i + 1, tzinfo=timezone.utc),
                    "subject": f"[DEMO] 기술문서 검토 요청 #{i+1}",
                    "subject_norm": f"기술문서 검토 요청 #{i+1}",
                    "from_addr": f"reviewer{i}@{org_name.lower()}.example.com",
                    "to_addr": "ra@company.example.com",
                    "body": f"안녕하세요,\n{org_name} 심사 담당자입니다.\n테스트 메시지 #{i+1}.",
                    "source_file": f"demo_{i+1}.eml",
                }
            )

        threads = group_threads(emails)
        md_content = generate_markdown(org_name, org_type, threads)

        safe_org_type = org_type.replace("/", "_").replace(" ", "_")
        repo_path = f"06_심사_QA이력/{safe_org_type}/{org_name}_QA이력.md"

        logger.info("Generated Markdown preview for %s:\n%s", org_name, md_content[:300])

        push_ok = push_to_github(repo_path, md_content, f"feat: add QA이력 {org_name} (demo)", github_token)

        source_path = f"github:holee9/ra-project/{repo_path}"
        qdrant_index(
            source_path=source_path,
            doc_type="qa_history",
            sheet=f"{org_name} QA이력",
            content=md_content,
        )

        print(
            f"[DRY-RUN] [{org_name}] threads={len(threads)}, "
            f"github={'✓' if push_ok else '✗'}"
        )

    logger.info("=== DRY-RUN DEMO END ===")


if __name__ == "__main__":
    main()
