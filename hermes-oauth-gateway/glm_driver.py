import os
import asyncio
import httpx
import json
import logging

logger = logging.getLogger(__name__)


async def run_glm(prompt: str, model: str = "glm-4-flash", timeout: int = 120) -> dict:
    """
    Zhipu AI GLM API를 통한 분석 (z.ai 구독)

    Args:
        prompt: 사용자 프롬프트
        model: GLM 모델 (기본값: glm-4-flash)
        timeout: 타임아웃 초

    Returns:
        {
            "text": 응답 텍스트,
            "input_tokens": 입력 토큰,
            "output_tokens": 출력 토큰
        }
    """
    api_key = os.getenv("GLM_API_KEY")
    if not api_key:
        raise ValueError("GLM_API_KEY environment variable not set")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "top_p": 0.9
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                headers=headers,
                json=payload,
                timeout=float(timeout)
            )

            if response.status_code != 200:
                error_text = response.text
                logger.error(f"GLM API error: {response.status_code} - {error_text}")
                raise Exception(f"GLM API returned {response.status_code}: {error_text}")

            data = response.json()

            # Zhipu AI 응답 파싱
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

            logger.info(f"GLM {model}: {input_tokens} input + {output_tokens} output tokens")

            return {
                "text": text,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens
            }

    except asyncio.TimeoutError:
        logger.error(f"GLM API timeout after {timeout}s")
        raise
    except Exception as e:
        logger.error(f"GLM API error: {str(e)}")
        raise
