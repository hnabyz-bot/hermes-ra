#!/usr/bin/env python3
"""
hermes-api-server.py — Hermes RA OpenAI-compatible HTTP bridge
Port: 8643 (0.0.0.0)
Auth: Authorization: Bearer <API_SERVER_KEY>

Builds a rich RA context from the incoming request metadata (subject, sender,
attachments) before calling `hermes -z`, and wraps the response in a wp_comment
JSON structure that n8n can post directly to OpenProject.
"""

import json
import os
import re
import subprocess
import time
from flask import Flask, request, jsonify

app = Flask(__name__)

API_KEY = os.environ.get("API_SERVER_KEY", "")
HERMES_BIN = os.environ.get("HERMES_BIN", "/home/abyz-lab/.local/bin/hermes")
PORT = int(os.environ.get("API_SERVER_PORT", "8643"))
TIMEOUT = int(os.environ.get("HERMES_TIMEOUT", "120"))


def check_auth() -> bool:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False
    return auth[7:] == API_KEY


def build_ra_prompt(messages: list[dict], metadata: dict) -> str:
    """Build a rich RA analysis prompt from messages + metadata."""
    last_user_content = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_content = msg.get("content", "")
            break

    subject = metadata.get("subject", "")
    sender = metadata.get("sender", "")
    attachments = metadata.get("attachments", [])

    parts = ["[RA 분석 요청]"]
    if subject:
        parts.append(f"제목: {subject}")
    if sender:
        parts.append(f"발신자: {sender}")
    if attachments:
        parts.append(f"첨부파일: {', '.join(attachments)}")
    parts.append("")
    parts.append(last_user_content)
    parts.append("")
    parts.append(
        "위 내용을 분석하여 반드시 다음 JSON 형식으로만 응답하세요:\n"
        '{"wp_comment": {"summary": "한국어 1-2문장 요약", '
        '"market_analysis": {"mfds": null, "ce_mdr": null, "fda": null}, '
        '"source_docs": [], "recommendation": "다음 단계 권고사항", '
        '"confidence": "high|medium|low"}}'
    )

    return "\n".join(parts)


def extract_metadata(data: dict) -> dict:
    """Extract RA metadata from the request payload (set by n8n workflow)."""
    return {
        "subject": data.get("subject", data.get("mail_subject", "")),
        "sender": data.get("sender", data.get("mail_sender", data.get("from", ""))),
        "attachments": data.get("attachments", data.get("mail_attachments", [])),
    }


def parse_wp_comment(text: str) -> dict | None:
    """Try to extract wp_comment JSON from hermes output."""
    json_pattern = re.search(r'\{.*"wp_comment".*\}', text, re.DOTALL)
    if json_pattern:
        try:
            return json.loads(json_pattern.group(0))
        except json.JSONDecodeError:
            pass
    return None


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
        return jsonify({"error": "No messages provided"}), 400

    metadata = extract_metadata(data)
    prompt = build_ra_prompt(messages, metadata)

    try:
        result = subprocess.run(
            [HERMES_BIN, "-z", prompt],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        response_text = result.stdout.strip()
        if not response_text and result.stderr:
            response_text = f"[hermes error] {result.stderr.strip()[:500]}"
    except subprocess.TimeoutExpired:
        response_text = json.dumps({
            "wp_comment": {
                "summary": "Hermes 에이전트 응답 시간 초과 (120초)",
                "market_analysis": {"mfds": None, "ce_mdr": None, "fda": None},
                "source_docs": [],
                "recommendation": "서버 상태를 확인하고 재시도하세요.",
                "confidence": "low",
                "flags": ["timeout"],
            }
        })
    except Exception as e:
        response_text = json.dumps({
            "wp_comment": {
                "summary": f"Hermes 에이전트 오류: {str(e)[:100]}",
                "market_analysis": {"mfds": None, "ce_mdr": None, "fda": None},
                "source_docs": [],
                "recommendation": "서버 로그를 확인하세요.",
                "confidence": "low",
                "flags": ["exception"],
            }
        })

    # If hermes returned raw wp_comment JSON, embed it; otherwise wrap as-is
    parsed = parse_wp_comment(response_text)
    if parsed:
        content = json.dumps(parsed, ensure_ascii=False)
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
            "prompt_tokens": len(prompt.split()),
            "completion_tokens": len(content.split()),
            "total_tokens": len(prompt.split()) + len(content.split()),
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
