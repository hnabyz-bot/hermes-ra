#!/usr/bin/env python3
"""
hermes-api-server.py — Hermes RA OpenAI-compatible HTTP bridge
Port: 8643 (0.0.0.0)
Auth: Authorization: Bearer <API_SERVER_KEY>

Pipeline:
  1. Qdrant RAG search (Layer 1) — NAS company documents
  2. Build context (email metadata + RAG results + WP list)
  3. hermes -z <context> --skills ra-expert  (PRIMARY, sole LLM engine)
  4. Return wp_comment JSON for OpenProject WP comment posting

RA classification rules and output format are defined in SKILL.md, not here.
"""

import json
import logging
import os
import re
import subprocess
import time
import urllib.request
import urllib.error
from flask import Flask, request, jsonify

app = Flask(__name__)

API_KEY = os.environ.get("API_SERVER_KEY", "")
HERMES_BIN = os.environ.get("HERMES_BIN", "/home/abyz-lab/.local/bin/hermes")
HERMES_MAX_TOKENS = int(os.environ.get("HERMES_MAX_TOKENS", "4096"))
PORT = int(os.environ.get("API_SERVER_PORT", "8643"))
TIMEOUT = int(os.environ.get("HERMES_TIMEOUT", "120"))
RAG_TIMEOUT = int(os.environ.get("RAG_TIMEOUT", "60"))

# Response log for weekly_review.py analysis
RESPONSE_LOG = os.environ.get("RESPONSE_LOG", "/var/log/hermes-responses.jsonl")

_response_logger = logging.getLogger("hermes.responses")
_response_logger.setLevel(logging.INFO)
try:
    _fh = logging.FileHandler(RESPONSE_LOG)
    _fh.setFormatter(logging.Formatter("%(message)s"))
    _response_logger.addHandler(_fh)
except OSError:
    pass  # log dir not writable; skip silently


def log_response(metadata: dict, parsed: dict) -> None:
    """Append one JSONL line per processed request for quality review."""
    try:
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "subject": metadata.get("subject", ""),
            "sender": metadata.get("sender", ""),
            "wp_comment": parsed.get("wp_comment", parsed),
        }
        _response_logger.info(json.dumps(record, ensure_ascii=False))
    except Exception:
        pass

# Layer 1: Qdrant RAG
RAG_SCRIPT = os.environ.get("RAG_SCRIPT", "/opt/hermes-ra/skills/ra-expert/scripts/rag_search.py")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://192.168.100.1:11434")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "qwen3-embedding:latest")


def check_auth() -> bool:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False
    return auth[7:] == API_KEY


def _run_rag_search(query: str, top: int = 5) -> list[dict]:
    """Layer 1: Search NAS Qdrant for relevant RA documents."""
    if not query.strip():
        return []
    try:
        result = subprocess.run(
            ["python3", RAG_SCRIPT, query, "--top", str(top)],
            capture_output=True,
            text=True,
            timeout=RAG_TIMEOUT,
            env={
                **os.environ,
                "QDRANT_URL": QDRANT_URL,
                "OLLAMA_URL": OLLAMA_URL,
                "EMBED_MODEL": EMBED_MODEL,
            },
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            return data.get("results", [])
    except Exception:
        pass
    return []


def build_context(messages: list[dict], metadata: dict, rag_results: list[dict], wp_list: str) -> str:
    """Build context for Hermes: email data + RAG results + WP list.
    RA classification rules and output format are in SKILL.md, not here.
    """
    last_user_content = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_content = msg.get("content", "")
            break

    subject = metadata.get("subject", "")
    sender = metadata.get("sender", "")
    attachments = metadata.get("attachments", [])
    if isinstance(attachments, str):
        attachments = [attachments] if attachments else []

    parts = ["## 수신 이메일"]
    if subject:
        parts.append(f"제목: {subject}")
    if sender:
        parts.append(f"발신자: {sender}")
    if attachments:
        parts.append(f"첨부파일: {', '.join(str(a) for a in attachments)}")
    parts.append("")
    parts.append(last_user_content)

    if rag_results:
        parts.append("")
        parts.append("## NAS 문서 검색 결과")
        for i, r in enumerate(rag_results[:5], 1):
            src = r.get("source_file", "unknown")
            score = r.get("score", 0)
            text = r.get("text", "")[:400]
            parts.append(f"[{i}] {src} (관련도: {score:.3f})")
            if text:
                parts.append(text)
        parts.append("")
        parts.append("위 문서를 source_docs에 인용하세요.")

    if wp_list.strip():
        parts.append("")
        parts.append("## 기존 OpenProject WP 목록")
        parts.append(wp_list)
        parts.append("")
        parts.append("이 이메일과 관련 있는 WP가 있으면 matched_wp_id에 숫자로 반환하세요. 없으면 null.")

    parts.append("")
    parts.append("## 출력 지시")
    parts.append("반드시 다음 JSON 형식으로만 응답하세요 (다른 텍스트 금지, 마크다운 코드블록 금지):")
    parts.append('{"wp_comment": {"email_type": "완료통보|액션필요|정보수신", "wp_title": "...", "summary": "...", "recommendation": "...", "confidence": 0.9, "deadline": null, "product": "...", "org": "...", "matched_wp_id": null}}')
    return "\n".join(parts)


def extract_metadata(data: dict) -> dict:
    return {
        "subject": data.get("subject", data.get("mail_subject", "")),
        "sender": data.get("sender", data.get("mail_sender", data.get("from", ""))),
        "attachments": data.get("attachments", data.get("mail_attachments", [])),
    }


def parse_wp_comment(text: str) -> dict | None:
    """Extract wp_comment JSON from Hermes output."""
    json_pattern = re.search(r'\{.*"wp_comment".*\}', text, re.DOTALL)
    if json_pattern:
        try:
            return json.loads(json_pattern.group(0))
        except json.JSONDecodeError:
            pass
    return None


def ensure_real_source_paths(parsed: dict, rag_results: list[dict]) -> dict:
    """Replace LLM-generated index numbers with real NAS file paths."""
    if not rag_results:
        return parsed
    wpc = parsed.get("wp_comment", {})
    existing = wpc.get("source_docs", [])
    has_real_paths = any(
        (isinstance(d, str) and "/" in d)
        or (isinstance(d, dict) and "/" in d.get("file", ""))
        for d in existing
    )
    if not has_real_paths:
        wpc["source_docs"] = [
            {
                "file": r.get("source_file", ""),
                "score": r.get("score", 0),
                "excerpt": r.get("text", "")[:200],
            }
            for r in rag_results[:3]
        ]
        parsed["wp_comment"] = wpc
    return parsed


@app.route("/v1/models", methods=["GET"])
def list_models():
    if not check_auth():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({
        "object": "list",
        "data": [{"id": "hermes-ra", "object": "model", "created": int(time.time()), "owned_by": "hermes"}],
    })


@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    if not check_auth():
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(force=True, silent=True) or {}
    messages = data.get("messages", [])

    if not messages:
        body_content = data.get("body", data.get("content", ""))
        if body_content:
            messages = [{"role": "user", "content": body_content}]
        else:
            return jsonify({"error": "No messages provided"}), 400

    metadata = extract_metadata(data)
    wp_list = data.get("wp_list", "")

    # Layer 1: Qdrant RAG
    search_query = metadata.get("subject", "")
    if not search_query.strip():
        for msg in reversed(messages):
            if msg.get("role") == "user":
                search_query = msg.get("content", "")[:150]
                break
    rag_results = _run_rag_search(search_query, top=5)

    context = build_context(messages, metadata, rag_results, wp_list)

    # PRIMARY: Nous Hermes Agent with ra-expert skill
    response_text = ""
    error_detail = ""
    try:
        result = subprocess.run(
            [HERMES_BIN, "-z", context, "--skills", "ra-expert"],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        response_text = result.stdout.strip()
        if not response_text and result.stderr:
            error_detail = result.stderr.strip()[:500]
    except subprocess.TimeoutExpired:
        error_detail = f"hermes -z timeout after {TIMEOUT}s"
    except FileNotFoundError:
        error_detail = f"hermes binary not found: {HERMES_BIN}"
    except Exception as e:
        error_detail = str(e)

    if not response_text:
        content = json.dumps({
            "wp_comment": {
                "email_type": "액션필요",
                "matched_wp_id": None,
                "wp_title": f"[오류] {metadata.get('subject', '이메일 처리 실패')}",
                "summary": "Hermes Agent 호출에 실패했습니다. 서버 로그를 확인하세요.",
                "market_analysis": {"mfds": None, "ce_mdr": None, "fda": None},
                "source_docs": [],
                "recommendation": f"hermes 서비스 상태 확인: journalctl -u hermes-api-server. 오류: {error_detail}",
                "confidence": "low",
                "deadline": None,
                "product": None,
                "org": None,
                "flags": ["hermes_failed"],
            }
        }, ensure_ascii=False)
    else:
        parsed = parse_wp_comment(response_text)
        if parsed:
            parsed = ensure_real_source_paths(parsed, rag_results)
            content = json.dumps(parsed, ensure_ascii=False)
            log_response(metadata, parsed)
        else:
            content = response_text

    return jsonify({
        "id": f"chatcmpl-hermes-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": data.get("model", "hermes-ra"),
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": len(context.split()),
            "completion_tokens": len(content.split()),
            "total_tokens": len(context.split()) + len(content.split()),
        },
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": True, "service": "hermes-api-server"})


if __name__ == "__main__":
    print(f"[hermes-api-server] Starting on 0.0.0.0:{PORT}")
    print(f"[hermes-api-server] HERMES_BIN={HERMES_BIN}")
    print(f"[hermes-api-server] API_KEY={'*' * len(API_KEY)}")
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
