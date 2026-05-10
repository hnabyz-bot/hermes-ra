import fnmatch
import time
import uuid
from pathlib import Path

import yaml
from fastapi import Body, Depends, FastAPI, Header, HTTPException

from codex_driver import run_codex_exec
from copilot_driver import run_copilot
from glm_driver import run_glm
from session_store import log_request

# 설정 로드
GATEWAY_DIR = Path(__file__).parent
with open(GATEWAY_DIR / "routes.yaml") as f:
    ROUTES = yaml.safe_load(f)

VALID_KEYS = {"sk-hermes-dev", "sk-hermes-n8n"}

app = FastAPI(title="Hermes OAuth Gateway", version="1.0.0")


# --- 인증 ---
async def verify_key(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth header")
    key = authorization[7:]
    if key not in VALID_KEYS:
        raise HTTPException(status_code=401, detail="Invalid key")
    return key


# --- 모델 라우팅 ---
def resolve_route(model: str) -> dict:
    for rule in ROUTES.get("models", []):
        if fnmatch.fnmatch(model, rule["match"]):
            upstream = rule["upstream_model"].replace("{model}", model)
            return {"track": rule["track"], "upstream_model": upstream}
    return {"track": ROUTES["default"], "upstream_model": model}


# --- 엔드포인트 ---
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/v1/models")
async def list_models(key: str = Depends(verify_key)):
    models = []
    for rule in ROUTES.get("models", []):
        models.append(rule["match"].replace("*", "-latest"))
    return {
        "object": "list",
        "data": [
            {"id": m, "object": "model", "created": 0, "owned_by": "hermes-oauth-gateway"}
            for m in models
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: dict = Body(...), key: str = Depends(verify_key)):
    model = request.get("model", "gpt-5.5")
    messages = request.get("messages", [])

    if not messages:
        raise HTTPException(status_code=400, detail="messages required")

    # 마지막 user 메시지 추출
    prompt = None
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, list):
                # OpenAI multi-part content
                parts = []
                for p in content:
                    if isinstance(p, dict) and p.get("type") == "text":
                        parts.append(p.get("text", ""))
                content = "\n".join(parts)
            prompt = content
            break

    if not prompt:
        raise HTTPException(status_code=400, detail="No user message found")

    route = resolve_route(model)
    track = route["track"]
    track_cfg = ROUTES.get("tracks", {}).get(track, {})
    timeout = int(track_cfg.get("timeout", 120))

    if track == "codex_cli":
        result = await run_codex_exec(prompt, route["upstream_model"], timeout=timeout)
    elif track == "copilot_cli":
        result = await run_copilot(prompt, timeout=timeout)
    elif track == "glm_zai":
        result = await run_glm(prompt, model=route["upstream_model"], timeout=timeout)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown track: {track}")

    # 로깅
    log_request(
        key,
        model,
        route["track"],
        result["input_tokens"],
        result["output_tokens"],
    )

    # OpenAI-compatible 응답
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": result["text"],
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": result["input_tokens"],
            "completion_tokens": result["output_tokens"],
            "total_tokens": result["input_tokens"] + result["output_tokens"],
        },
    }
