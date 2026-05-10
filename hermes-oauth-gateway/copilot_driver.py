"""GitHub Copilot CLI driver for Hermes OAuth Gateway (Track B).

holee9 계정의 GitHub Copilot Pro 구독을 통해 ~/.copilot/ 의 OAuth 토큰을 사용한다.
gh 자체 인증(hnabyz-bot) 과는 분리된 토큰 저장소이므로 별도 환경변수 불필요.
"""

import asyncio
import os

COPILOT_BIN = "/home/raspi5p/.hermes/node/bin/copilot"


async def run_copilot(prompt: str, timeout: int = 60) -> dict:
    """Run `copilot -p` non-interactive and return the response text.

    Args:
        prompt: user prompt text
        timeout: hard timeout in seconds

    Returns:
        dict with keys: text, input_tokens, output_tokens
    """
    cmd = [
        COPILOT_BIN,
        "-p",
        prompt,
        "--allow-all-tools",  # required for non-interactive
    ]

    # Strip GH_TOKEN/GITHUB_TOKEN to force use of ~/.copilot OAuth token
    # (classic PAT in those env vars would be rejected by Copilot CLI)
    env = {k: v for k, v in os.environ.items()
           if k not in ("GITHUB_TOKEN", "GH_TOKEN", "COPILOT_GITHUB_TOKEN")}

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,
            env=env,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            return {
                "text": "[Copilot timeout]",
                "input_tokens": 0,
                "output_tokens": 0,
            }

    except Exception as e:
        return {
            "text": f"[Copilot error: {e}]",
            "input_tokens": 0,
            "output_tokens": 0,
        }

    output = stdout.decode(errors="replace").strip() if stdout else ""
    error = stderr.decode(errors="replace").strip() if stderr else ""

    final_text = output or error or "[Copilot no response]"

    return {
        "text": final_text,
        "input_tokens": 0,
        "output_tokens": 0,
    }
