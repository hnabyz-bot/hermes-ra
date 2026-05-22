#!/usr/bin/env python3
"""
hermes-api-server.py — hermes oneshot HTTP 래퍼 서버
OpenAI /v1/chat/completions 호환 엔드포인트를 제공하며,
내부적으로 `hermes -z "..."` 를 실행해 응답을 반환합니다.

포트: 8643 (0.0.0.0 — Docker/n8n 컨테이너에서 172.17.0.1:8643 로 접근 가능)
인증: Authorization: Bearer <API_SERVER_KEY>
"""

import os
import json
import subprocess
import time
from flask import Flask, request, jsonify

app = Flask(__name__)

API_KEY = os.environ.get("API_SERVER_KEY", "")
HERMES_BIN = os.environ.get("HERMES_BIN", "/home/abyz-lab/.local/bin/hermes")
PORT = int(os.environ.get("API_SERVER_PORT", "8643"))
TIMEOUT = int(os.environ.get("HERMES_TIMEOUT", "120"))


def check_auth():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False
    return auth[7:] == API_KEY


@app.route("/v1/models", methods=["GET"])
def list_models():
    if not check_auth():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({
        "object": "list",
        "data": [
            {"id": "default", "object": "model", "created": int(time.time()), "owned_by": "hermes"}
        ]
    })


@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    if not check_auth():
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(force=True, silent=True) or {}
    messages = data.get("messages", [])

    # 마지막 user 메시지를 프롬프트로 사용
    prompt = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            prompt = msg.get("content", "")
            break

    if not prompt:
        return jsonify({"error": "No user message found"}), 400

    try:
        result = subprocess.run(
            [HERMES_BIN, "-z", prompt],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            env={**os.environ, "PYTHONUNBUFFERED": "1"}
        )
        response_text = result.stdout.strip()
        if not response_text and result.stderr:
            # stderr에서 유용한 내용이 있으면 포함
            response_text = f"[hermes error] {result.stderr.strip()[:500]}"
    except subprocess.TimeoutExpired:
        response_text = "[hermes timeout] 응답 시간 초과 (120초)"
    except Exception as e:
        response_text = f"[hermes exception] {str(e)}"

    return jsonify({
        "id": f"chatcmpl-hermes-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": data.get("model", "default"),
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": len(prompt.split()),
            "completion_tokens": len(response_text.split()),
            "total_tokens": len(prompt.split()) + len(response_text.split())
        }
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": True, "service": "hermes-api-server"})


if __name__ == "__main__":
    print(f"[hermes-api-server] Starting on 0.0.0.0:{PORT}")
    print(f"[hermes-api-server] HERMES_BIN={HERMES_BIN}")
    print(f"[hermes-api-server] API_KEY={'*' * len(API_KEY)}")
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
