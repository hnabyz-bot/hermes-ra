#!/usr/bin/env python3
"""
hermes-api-server.py — Hermes RA OpenAI-compatible HTTP bridge
Port: 8643 (0.0.0.0)
Auth: Authorization: Bearer <API_SERVER_KEY>

3-layer knowledge pipeline:
  1. Qdrant RAG search (Layer 1) via rag_search.py + qwen3-embedding
  2. Enriched prompt includes NAS source documents + RA classification
  3. LLM call: GLM-4-Air (primary) → OpenRouter (fallback) → hermes -z (last resort)
  4. Returns wp_comment JSON for OpenProject WP comment posting
"""

import json
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

# GLM API (primary)
GLM_API_KEY = os.environ.get("GLM_API_KEY", "")
GLM_BASE_URL = os.environ.get("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
GLM_MODEL = os.environ.get("GLM_MODEL", "glm-4-air-250414")

# OpenRouter (fallback)
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")

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


def _call_glm_direct(prompt: str) -> str:
    """Call GLM-4-Air API directly."""
    payload = json.dumps({
        "model": GLM_MODEL,
        "max_tokens": HERMES_MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{GLM_BASE_URL}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {GLM_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"GLM API 오류 {e.code}: {body}")


def _call_openrouter_direct(prompt: str) -> str:
    """Call OpenRouter API directly (fallback)."""
    payload = json.dumps({
        "model": OPENROUTER_MODEL,
        "max_tokens": HERMES_MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"OpenRouter 오류 {e.code}: {body}")


def build_ra_prompt(messages: list[dict], metadata: dict, rag_results: list[dict] | None = None) -> str:
    """Build enriched RA analysis prompt including NAS source documents."""
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

    parts = [
        "당신은 의료기기 규제 인허가(RA) 전문 에이전트입니다. 아래 수신 이메일을 분석하세요.",
        "",
        "## 수신 이메일",
    ]
    if subject:
        parts.append(f"**제목**: {subject}")
    if sender:
        parts.append(f"**발신자**: {sender}")
    if attachments:
        parts.append(f"**첨부파일**: {', '.join(str(a) for a in attachments)}")
    parts.append("")
    parts.append("**본문**:")
    parts.append(last_user_content)

    if rag_results:
        parts.append("")
        parts.append("## NAS 문서 검색 결과 (Layer 1 — 회사 원본 문서)")
        for i, r in enumerate(rag_results[:5], 1):
            src = r.get("source_file", "unknown")
            score = r.get("score", 0)
            text = r.get("text", "")[:400]
            parts.append(f"### [{i}] {src} (관련도: {score:.3f})")
            if text:
                parts.append(text)
        parts.append("")
        parts.append("*위 문서를 source_docs 배열에 반드시 인용하세요.*")

    parts.append("")
    parts.append("## 분석 지시사항")
    parts.append(
        "이메일을 분석하여 다음 사항을 판단하세요:\n"
        "\n"
        "1. **이메일 유형** (정확히 하나 선택):\n"
        "   - `완료통보`: 이미 완료된 업무 통보 (허가완료, 등록완료, 인증완료 등)\n"
        "   - `정보수신`: 참고용 정보, 회신 불필요 (공지, 업데이트, 현황보고 등)\n"
        "   - `액션필요`: 담당자 조치 필요 (심사요청, 서류제출, 기한준수 등)\n"
        "\n"
        "2. **OpenProject WP 제목** (형식: `[유형] 발신기관/제품 - 핵심업무`):\n"
        "   - 완료통보 예: `[완료] Licarno - EUDAMED 등록 완료`\n"
        "   - 정보수신 예: `[정보] 자비텍 - 운용비 지급 안내`\n"
        "   - 액션필요 예: `[액션] Licarno/Croma - Retrofit+CYAN 기술문서 제출 [2026-05-27]`\n"
        "\n"
        "3. **시장별 규제 분석** (해당 없으면 null):\n"
        "   - MFDS: 한국 식약처 관련 사항\n"
        "   - CE MDR: 유럽 인증 관련 사항\n"
        "   - FDA: 미국 FDA 관련 사항\n"
        "\n"
        "4. **핵심 정보 추출**: 마감일(YYYY-MM-DD), 제품명, 발신기관, 요청사항\n"
        "\n"
        "반드시 다음 JSON 형식으로만 응답하세요 (코드블록 없이 순수 JSON):\n"
        '{"wp_comment": {'
        '"email_type": "완료통보|정보수신|액션필요", '
        '"wp_title": "WP 제목 문자열", '
        '"summary": "한국어 2-3문장 업무 요약", '
        '"market_analysis": {"mfds": "내용 또는 null", "ce_mdr": "내용 또는 null", "fda": "내용 또는 null"}, '
        '"source_docs": [], '
        '"recommendation": "구체적인 다음 단계 권고사항", '
        '"confidence": "high|medium|low", '
        '"deadline": "YYYY-MM-DD 또는 null", '
        '"product": "제품명 또는 null", '
        '"org": "발신기관 또는 null"}}'
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
    """Try to extract wp_comment JSON from LLM output."""
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
        body_content = data.get("body", data.get("content", ""))
        if body_content:
            messages = [{"role": "user", "content": body_content}]
        else:
            return jsonify({"error": "No messages provided"}), 400

    metadata = extract_metadata(data)

    # Layer 1: Qdrant RAG search using email subject as query
    search_query = metadata.get("subject", "")
    if not search_query.strip():
        for msg in reversed(messages):
            if msg.get("role") == "user":
                search_query = msg.get("content", "")[:150]
                break
    rag_results = _run_rag_search(search_query, top=5)

    prompt = build_ra_prompt(messages, metadata, rag_results)

    response_text = ""
    errors = []

    # Primary: GLM-4-Air
    if GLM_API_KEY:
        try:
            response_text = _call_glm_direct(prompt)
        except Exception as e:
            errors.append(f"GLM: {e}")

    # Fallback: OpenRouter
    if not response_text and OPENROUTER_API_KEY:
        try:
            response_text = _call_openrouter_direct(prompt)
        except Exception as e:
            errors.append(f"OpenRouter: {e}")

    # Last resort: hermes -z with RA Expert Skill
    if not response_text:
        try:
            result = subprocess.run(
                [HERMES_BIN, "-z", prompt, "--skills", "ra-expert"],
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
            response_text = result.stdout.strip()
            if not response_text and result.stderr:
                errors.append(f"hermes: {result.stderr.strip()[:200]}")
        except subprocess.TimeoutExpired:
            errors.append("hermes -z timeout")
        except Exception as e:
            errors.append(f"hermes: {e}")

    if not response_text:
        response_text = json.dumps({
            "wp_comment": {
                "email_type": "액션필요",
                "wp_title": f"[오류] {metadata.get('subject', '이메일 처리 실패')}",
                "summary": "모든 LLM 호출이 실패했습니다.",
                "market_analysis": {"mfds": None, "ce_mdr": None, "fda": None},
                "source_docs": [],
                "recommendation": f"서버 로그 확인. 오류: {'; '.join(errors[:3])}",
                "confidence": "low",
                "deadline": None,
                "product": None,
                "org": None,
                "flags": ["all_llm_failed"],
            }
        })

    # Ensure source_docs includes actual RAG hits if LLM left it empty
    parsed = parse_wp_comment(response_text)
    if parsed and rag_results:
        wpc = parsed.get("wp_comment", {})
        if not wpc.get("source_docs"):
            wpc["source_docs"] = [
                {
                    "file": r.get("source_file", ""),
                    "score": r.get("score", 0),
                    "excerpt": r.get("text", "")[:200],
                }
                for r in rag_results[:3]
            ]
            parsed["wp_comment"] = wpc
        content = json.dumps(parsed, ensure_ascii=False)
    elif parsed:
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
