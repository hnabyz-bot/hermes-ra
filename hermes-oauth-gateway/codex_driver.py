import asyncio
import json
import os

CODEX_BIN = "/home/raspi5p/.hermes/node/bin/codex"


# ChatGPT subscription으로 codex 사용 시 -m 옵션은 거부됨 (default 모델만 허용).
# API key 모드로 전환 시 이 set에 허용 모델 추가.
CHATGPT_ACCOUNT_MODE = True  # ChatGPT 구독 사용 중이면 True


async def run_codex_exec(prompt: str, model: str, timeout: int = 120) -> dict:
    """
    Run codex exec --json and parse JSONL response.

    Returns:
        {"text": "final response", "input_tokens": int, "output_tokens": int}
    """
    cmd = [
        CODEX_BIN,
        "exec",
        "--json",
        "--skip-git-repo-check",
        "--sandbox", "read-only",
        prompt,
    ]

    # ChatGPT 구독에서는 -m 옵션이 invalid_request_error 발생.
    # 모델 매핑 없이 codex default (gpt-5.5)만 사용.
    if not CHATGPT_ACCOUNT_MODE and model not in ["gpt-5.5", "gpt-5", ""]:
        cmd.insert(3, "-m")
        cmd.insert(4, model)

    env = {**os.environ, "PATH": f"/home/raspi5p/.hermes/node/bin:{os.environ.get('PATH', '')}"}

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,
            env=env,
        )

        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout,
        )

    except asyncio.TimeoutError:
        return {"text": "[Codex timeout]", "input_tokens": 0, "output_tokens": 0}
    except Exception as e:
        return {"text": f"[Codex error: {e}]", "input_tokens": 0, "output_tokens": 0}

    # JSONL parse: item.completed & item.type==agent_message
    lines = stdout.decode(errors="replace").strip().splitlines()
    text_parts = []
    error_msg = None
    input_tokens = output_tokens = 0

    for line in lines:
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        ev_type = event.get("type")
        if ev_type == "item.completed":
            item = event.get("item", {})
            if item.get("type") == "agent_message":
                text_parts.append(item.get("text", ""))
        elif ev_type == "turn.completed":
            usage = event.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
        elif ev_type in ("turn.failed", "error"):
            err = event.get("error") or event
            error_msg = err.get("message") if isinstance(err, dict) else str(err)

    if text_parts:
        final_text = "\n".join(text_parts).strip()
    elif error_msg:
        final_text = f"[Codex error] {error_msg}"
    else:
        err_tail = stderr.decode(errors="replace").strip()[:500] if stderr else ""
        # stderr의 'Reading additional input from stdin...' 메시지는 노이즈로 필터
        if err_tail.startswith("Reading additional input"):
            err_tail = ""
        final_text = err_tail or "[Codex returned no agent_message]"

    return {
        "text": final_text,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }
