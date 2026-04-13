"""Ollama LLM 클라이언트 래퍼"""

import json
import random
import time
from typing import Optional, Dict, Any
import os

try:
    import ollama
except ImportError:
    ollama = None


class OllamaClient:
    """Ollama 로컬 LLM 클라이언트"""

    def __init__(self, base_url: str = None, timeout: int = 60):
        self.base_url = base_url or os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.timeout = timeout

    def chat(
        self,
        model: str,
        messages: list,
        temperature: float = 0.7,
        retry_count: int = 3,
    ) -> Dict[str, Any]:
        """
        LLM 호출 (exponential backoff 포함)

        Args:
            model: 모델명 (gemma4-unsloth-e4b:latest, gemma4:26b-a4b-it-q4_K_M)
            messages: [{"role": "user", "content": "..."}, ...]
            temperature: 0~2
            retry_count: 실패 시 재시도 횟수

        Returns:
            {
                "content": "...",  # 응답 텍스트
                "stop_reason": "stop",
                "model": "gemma4-unsloth-e4b:latest"
            }
        """
        if ollama is None:
            raise RuntimeError("ollama 패키지 필요: pip install ollama")

        _TRANSIENT = (ConnectionError, TimeoutError, OSError)

        for attempt in range(retry_count):
            try:
                response = ollama.chat(
                    model=model,
                    messages=messages,
                    options={"temperature": temperature},
                    stream=False,
                )
                return {
                    "content": response.get("message", {}).get("content", ""),
                    "stop_reason": response.get("stop_reason", "stop"),
                    "model": model,
                }
            except _TRANSIENT as e:
                if attempt < retry_count - 1:
                    backoff_seconds = 2 ** attempt + random.uniform(0, 1)
                    time.sleep(backoff_seconds)
                else:
                    raise RuntimeError(f"LLM failed after {retry_count} retries: {str(e)}") from e
            except Exception as e:
                # 버그성 오류(ValueError, RuntimeError 등)는 재시도 없이 즉시 전파
                raise

    def generate_with_image(
        self,
        model: str,
        prompt: str,
        image_base64: str,
        temperature: float = 0.3,
        retry_count: int = 3,
    ) -> Dict[str, Any]:
        """
        Vision LLM 호출 — 이미지 + 프롬프트 (Ollama /api/generate)

        Args:
            model: Vision 지원 모델명 (gemma4:26b-a4b-it-q4_K_M)
            prompt: 텍스트 프롬프트
            image_base64: base64 인코딩된 JPEG 문자열
            temperature: 0~2 (분류 작업은 0.3 권장)
            retry_count: 일시적 오류 재시도 횟수

        Returns:
            {"content": "...", "stop_reason": "stop", "model": "..."}
        """
        if ollama is None:
            raise RuntimeError("ollama 패키지 필요: pip install ollama")

        _TRANSIENT = (ConnectionError, TimeoutError, OSError)

        for attempt in range(retry_count):
            try:
                response = ollama.generate(
                    model=model,
                    prompt=prompt,
                    images=[image_base64],
                    stream=False,
                    options={"temperature": temperature},
                )
                return {
                    "content": response.get("response", ""),
                    "stop_reason": response.get("done_reason", "stop"),
                    "model": model,
                }
            except _TRANSIENT as e:
                if attempt < retry_count - 1:
                    backoff_seconds = 2 ** attempt + random.uniform(0, 1)
                    time.sleep(backoff_seconds)
                else:
                    raise RuntimeError(
                        f"Vision LLM failed after {retry_count} retries: {str(e)}"
                    ) from e
            except Exception:
                raise

    def parse_json_response(self, content: str) -> Dict[str, Any]:
        """LLM 응답을 JSON으로 파싱"""
        try:
            # JSON 블록 추출 (```json ... ```)
            if "```json" in content:
                start = content.index("```json") + 7
                end = content.index("```", start)
                json_str = content[start:end].strip()
            elif "```" in content:
                start = content.index("```") + 3
                end = content.index("```", start)
                json_str = content[start:end].strip()
            else:
                json_str = content

            return json.loads(json_str)
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"JSON parse error: {str(e)}\nContent: {content[:200]}")


# 글로벌 인스턴스
_client_instance: Optional[OllamaClient] = None


def get_ollama_client() -> OllamaClient:
    """글로벌 Ollama 클라이언트 반환"""
    global _client_instance
    if _client_instance is None:
        _client_instance = OllamaClient()
    return _client_instance
