import json
import logging
import urllib.request
import urllib.error
import asyncio

logger = logging.getLogger("ARDA_BRIDGE")

class OllamaBridge:
    def __init__(self, model="qwen2.5:3b", host="http://localhost:11434"):
        self.model = model
        self.host = host

    async def generate(self, prompt: str, format: str = "text") -> str:
        """The real speech of the bridge to the local Ollama substrate."""
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }
        if format == "json":
            payload["format"] = "json"

        # Use sync urllib in a thread pool to avoid blocking the event loop
        def _call_ollama():
             data = json.dumps(payload).encode("utf-8")
             req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
             try:
                 with urllib.request.urlopen(req, timeout=120.0) as response:
                     if response.status == 200:
                         result = json.loads(response.read().decode("utf-8"))
                         return result.get("response", "")
                     else:
                         logger.error(f"Ollama error: {response.status}")
                         return ""
             except urllib.error.URLError as e:
                 logger.error(f"Connection to Ollama failed: {e}")
                 raise RuntimeError(f"Ollama bridge failure: {e}")
             except Exception as e:
                 logger.error(f"Unexpected bridge error: {e}")
                 return ""

        return await asyncio.to_thread(_call_ollama)
