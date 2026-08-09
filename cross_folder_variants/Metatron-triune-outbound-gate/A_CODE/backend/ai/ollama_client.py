"""Ollama HTTP client wrapper.

Provides a simple, dependency-light client with sync and async methods.
Designed for safe failover and easy mocking in tests.
"""
from typing import Optional, Dict, Any
import os
import requests
import asyncio


DEFAULT_OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://host.docker.internal:11434")
DEFAULT_OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "mistral")


class OllamaClient:
    def __init__(self, base_url: str = DEFAULT_OLLAMA_URL, model: str = DEFAULT_OLLAMA_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def get_tags(self, timeout: int = 5) -> Dict[str, Any]:
        """Retrieve Ollama tags/models available."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def generate(self, prompt: str, model: Optional[str] = None, system: Optional[str] = None, timeout: int = 120) -> Dict[str, Any]:
        model = model or self.model
        payload: Dict[str, Any] = {"model": model, "prompt": prompt, "stream": False}
        if system:
            payload["system"] = system
        try:
            resp = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    async def aget_tags(self, timeout: int = 5) -> Dict[str, Any]:
        return await asyncio.to_thread(self.get_tags, timeout)

    async def agenerate(self, prompt: str, model: Optional[str] = None, system: Optional[str] = None, timeout: int = 120) -> Dict[str, Any]:
        return await asyncio.to_thread(self.generate, prompt, model, system, timeout)
