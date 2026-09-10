from __future__ import annotations

from typing import Any

import requests


class HttpClient:
    def __init__(self, user_agent: str = "DIO-Capital-Census/1.0"):
        self.user_agent = user_agent

    def _headers(self, headers: dict[str, str] | None = None) -> dict[str, str]:
        result = {"User-Agent": self.user_agent, "Accept": "application/json"}
        if headers:
            result.update(headers)
        return result

    def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        timeout: float = 20.0,
        headers: dict[str, str] | None = None,
    ) -> Any:
        response = requests.get(url, params=params, timeout=timeout, headers=self._headers(headers))
        response.raise_for_status()
        return response.json()

    def post_json(
        self,
        url: str,
        *,
        json_body: dict[str, Any],
        timeout: float = 20.0,
        headers: dict[str, str] | None = None,
    ) -> Any:
        request_headers = self._headers(headers)
        request_headers.setdefault("Content-Type", "application/json")
        response = requests.post(url, json=json_body, timeout=timeout, headers=request_headers)
        response.raise_for_status()
        return response.json()
