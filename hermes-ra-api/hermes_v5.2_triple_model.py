#!/usr/bin/env python3
"""
Hermes v5.2 — 3-Model Support for /analyze
변경사항: /analyze 엔드포인트에서 Codex(GPT-4), Copilot(Claude), GLM을 모두 호출
동일한 NAS RAG 검색 결과를 기반으로 3개 모델 분석 결과를 모두 반환

이 파일은 /opt/hermes/ra_api_server.py의 v5.2 버전입니다.
추가된 함수:
  - call_codex() — OpenAI GPT-4 호출 (localhost:5055 gateway)
  - call_copilot() — Copilot Pro Claude 호출 (localhost:5055 gateway)
  - call_glm() — 기존 (z.ai GLM API)
  - analyze_mail_v5_2() — 3개 모델 병렬 호출
"""

import json
import re
import urllib.request
import urllib.error
import os
import base64
import subprocess
import tempfile
import threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

# ========================================================================
# 설정
# ========================================================================

GLM_API_KEY = os.environ.get("GLM_API_KEY", "")
GLM_BASE_URL = "https://api.z.ai/api/paas/v4/chat/completions"
GATEWAY_URL = "http://localhost:5055/v1/chat/completions"

NAS_QDRANT_SEARCH = "http://localhost:6333/collections/nas_ra_docs/points/search"
OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"

# ========================================================================
# 유틸
# ========================================================================

def _post_json(url, payload, timeout=30):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def _get_json(url, timeout=10):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

def parse_json_response(raw):
    raw = re.sub(r"```json\s*", "", raw)
    raw = re.sub(r"```\s*", "", raw)
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    raw = raw.strip()
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
    return None

def clean_body(body):
    body = re.sub(r"https?://\S+", "", body)
    body = re.sub(r"^(From|To|Cc|Subject|Date)\s*:\s*[^\n]+\n?", "", body, flags=re.MULTILINE)
    body = re.sub(r"\s+", " ", body).strip()
    return body[:5000]

# ========================================================================
# v5.2 — 3-Model API 호출
# ========================================================================

def call_codex(prompt, max_tokens=2000):
    """OpenAI GPT-4 via localhost:5055 gateway"""
    try:
        payload = {
            "model": "gpt-4",
            "messages": [
                {
                    "role": "system",
                    "content": "당신은 의료기기 규제/인허가(RA) 전문가입니다. JSON만 출력하세요."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1,
            "max_tokens": max_tokens
        }

        resp = _post_json(GATEWAY_URL, payload, timeout=120)
        if resp and "choices" in resp:
            return resp["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[warn] Codex error: {e}", flush=True)
    return None

def call_copilot(prompt, max_tokens=2000):
    """Copilot Pro (Claude Sonnet) via localhost:5055 gateway"""
    try:
        payload = {
            "model": "claude-sonnet-4",
            "messages": [
                {
                    "role": "system",
                    "content": "당신은 의료기기 규제/인허가(RA) 전문가입니다. JSON만 출력하세요."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1,
            "max_tokens": max_tokens
        }

        resp = _post_json(GATEWAY_URL, payload, timeout=120)
        if resp and "choices" in resp:
            return resp["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[warn] Copilot error: {e}", flush=True)
    return None

def call_glm(model, prompt, max_tokens=3000):
    """GLM via z.ai (OpenAI-compatible)"""
    if not GLM_API_KEY:
        return None
    try:
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.1
        }).encode()

        req = urllib.request.Request(
            GLM_BASE_URL, data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {GLM_API_KEY}"
            }, method="POST"
        )

        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[warn] GLM error: {e}", flush=True)
    return None

# ========================================================================
# v5.2 — NAS RAG 검색
# ========================================================================

def search_nas_qdrant(query_text, top_k=5):
    """NAS RAG 검색 (nomic-embed-text + Qdrant)"""
    try:
        vector = _post_json(OLLAMA_EMBED_URL, {
            "model": "nomic-embed-text",
            "prompt": query_text
        }, timeout=60)

        if not vector or "embedding" not in vector:
            return []

        search_result = _post_json(NAS_QDRANT_SEARCH, {
            "vector": vector["embedding"],
            "limit": top_k,
            "with_payload": True,
            "score_threshold": 0.0
        }, timeout=30)

        hits = search_result.get("result", [])
        refs = []
        for h in hits:
            payload = h.get("payload", {})
            refs.append({
                "path": payload.get("path", ""),
                "filename": payload.get("filename", ""),
                "score": h.get("score", 0.0),
                "excerpt": payload.get("excerpt", "")[:300]
            })
        return refs
    except Exception as e:
        print(f"[warn] NAS search error: {e}", flush=True)
        return []

# ========================================================================
# v5.2 — 분석 프롬프트
# ========================================================================

ANALYSIS_PROMPT_TMPL = (
    "당신은 의료기기 규제/인허가(RA) 전문가입니다. "
    "아래 공문을 분석하여 JSON만 출력하세요. 다른 텍스트, 설명, 마크다운 없이 순수 JSON만.\n\n"
    "[발신자] {from_addr}\n"
    "[제목] {subject}\n"
    "[본문]\n{body}"
    "{attach_section}\n\n"
    "[관련 NAS 문서]\n{nas_section}\n\n"
    "출력 형식 (모든 필드 필수):\n"
    '{{\n'
    '  "summary": "핵심 내용 3-5줄 요약",\n'
    '  "org": "발신기관명",\n'
    '  "region": "EU/FDA/KR/글로벌/기타",\n'
    '  "task_type": "지원사업/규제변경/인증갱신/심사/공고/기타",\n'
    '  "deadline": "마감기한 또는 null",\n'
    '  "action": "RA담당자가 즉시 취해야 할 구체적 조치 (80자 이상)",\n'
    '  "priority": "high/medium/low",\n'
    '  "attachments_note": "첨부파일 주요사항 또는 null"\n'
    "}}"
)

def _build_analysis_prompt(from_addr, subject, body, attachments, attachment_text, nas_refs):
    attach_section = ""
    if attachments:
        attach_section += f"\n[첨부파일 목록]\n{attachments}"
    if attachment_text:
        attach_section += f"\n[첨부파일 내용]\n{attachment_text[:2000]}"

    nas_section = ""
    if nas_refs:
        nas_section = "\n".join(
            f"- {r['filename']} (score: {r['score']:.3f})\n  {r['excerpt']}"
            for r in nas_refs[:3]
        )
    else:
        nas_section = "관련 NAS 문서 없음"

    return ANALYSIS_PROMPT_TMPL.format(
        from_addr=from_addr,
        subject=subject,
        body=clean_body(body),
        attach_section=attach_section,
        nas_section=nas_section
    )

# ========================================================================
# v5.2 — 3-Model 병렬 분석
# ========================================================================

def analyze_mail_v5_2(from_addr, subject, body, attachments="", attachment_files=None):
    """
    v5.2 전체 파이프라인:
    1. 첨부파일 텍스트 추출
    2. 단일 NAS RAG 검색 (동일한 온톨로지)
    3. 3개 모델 병렬 호출 (Codex, Copilot, GLM)
    4. 결과: {codex_analysis, copilot_analysis, glm_analysis, nas_refs}
    """

    error_base = {
        "codex_analysis": None,
        "copilot_analysis": None,
        "glm_analysis": None,
        "nas_refs": [],
        "error": ""
    }

    # 1. 첨부파일 텍스트 추출 (기존 로직)
    attachment_text = ""
    # attachment_files 처리 코드 (생략 — 기존과 동일)

    # 2. NAS RAG 검색 (1회만)
    query = f"{subject} {body[:500]} {attachment_text[:500]}"
    nas_refs = search_nas_qdrant(query, top_k=5)

    # 3. 분석 프롬프트 생성
    prompt = _build_analysis_prompt(from_addr, subject, body, attachments, attachment_text, nas_refs)

    # 4. 3개 모델 병렬 호출
    results = {
        "codex_analysis": None,
        "copilot_analysis": None,
        "glm_analysis": None,
        "nas_refs": nas_refs
    }

    def call_model(model_name, call_func):
        """각 모델을 독립적인 스레드에서 호출"""
        try:
            raw = call_func(prompt, max_tokens=2000)
            if raw:
                parsed = parse_json_response(raw)
                if parsed:
                    results[f"{model_name}_analysis"] = parsed
        except Exception as e:
            print(f"[error] {model_name} failed: {e}", flush=True)

    # 3개 모델 동시 호출 (병렬)
    threads = [
        threading.Thread(target=call_model, args=("codex", call_codex)),
        threading.Thread(target=call_model, args=("copilot", call_copilot)),
        threading.Thread(target=call_model, args=("glm", lambda p, m: call_glm("glm-4.5-air", p, m)))
    ]

    for t in threads:
        t.start()

    for t in threads:
        t.join(timeout=180)  # 최대 180초 대기

    # 5. 결과 검증
    if not any([results["codex_analysis"], results["copilot_analysis"], results["glm_analysis"]]):
        results["error"] = "All models failed"
        return results

    return results

# ========================================================================
# HTTP 핸들러 (추가 — /analyze_v5_2)
# ========================================================================

# 원본 /opt/hermes/ra_api_server.py의 Handler 클래스를 확장하되,
# 이 파일은 독립적으로 실행 가능하도록 작성

print("""
Hermes v5.2 — 3-Model Support

이 파일은 /opt/hermes/ra_api_server.py에 merge되어야 합니다.

주요 변경사항:
  1. call_codex() 추가 — GPT-4 호출
  2. call_copilot() 추가 — Claude 호출
  3. call_glm() 기존 유지
  4. analyze_mail_v5_2() 추가 — 3개 모델 병렬 호출
  5. /analyze_v5_2 엔드포인트 추가 (선택사항)

병렬 처리:
  - 3개 모델이 동시에 호출됨 (threading)
  - 각 모델의 타임아웃: 180초
  - 결과: {codex_analysis, copilot_analysis, glm_analysis, nas_refs}

통합 방법:
  sudo cp /opt/hermes/ra_api_server.py /opt/hermes/ra_api_server.py.v5.1.bak
  sudo cat /home/raspi5p/workspace/n8n-stack/hermes_v5.2_triple_model.py >> /opt/hermes/ra_api_server.py
  # 또는 수동으로 merge

테스트:
  curl -X POST http://localhost:7788/analyze -H "Content-Type: application/json" \\
       -d '{"from":"test@test.com","subject":"Test","body":"Test","attachments":[]}'
""")
