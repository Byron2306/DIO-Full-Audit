from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import msal
import requests


class GraphError(RuntimeError):
    pass


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    client_id = config.get("client_id", "")
    if not client_id or client_id.startswith("REPLACE_"):
        raise GraphError(f"Set client_id in {path} after registering the DIO public-client application.")
    return config


class GraphClient:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.cache_path = Path(config["token_cache_path"]).expanduser().resolve()
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache = msal.SerializableTokenCache()
        if self.cache_path.exists():
            self.cache.deserialize(self.cache_path.read_text(encoding="utf-8"))
        self.app = msal.PublicClientApplication(
            config["client_id"],
            authority=config.get("authority", "https://login.microsoftonline.com/consumers"),
            token_cache=self.cache,
        )
        self.base_url = config.get("graph_base_url", "https://graph.microsoft.com/v1.0").rstrip("/")

    def save_cache(self) -> None:
        if not self.cache.has_state_changed:
            return
        temporary = self.cache_path.with_suffix(".tmp")
        temporary.write_text(self.cache.serialize(), encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(self.cache_path)

    def acquire_token(self, interactive: bool = False) -> str:
        scopes = self.config["scopes"]
        result = None
        accounts = self.app.get_accounts()
        if accounts:
            result = self.app.acquire_token_silent(scopes=scopes, account=accounts[0])
        if not result and interactive:
            flow = self.app.initiate_device_flow(scopes=scopes)
            if "user_code" not in flow:
                raise GraphError(f"Microsoft device login could not start: {flow.get('error_description', flow)}")
            print(flow["message"], flush=True)
            result = self.app.acquire_token_by_device_flow(flow)
        self.save_cache()
        if not result or "access_token" not in result:
            detail = result.get("error_description") if isinstance(result, dict) else "No cached account. Run with --device-login."
            raise GraphError(detail or "Microsoft Graph authentication failed.")
        return result["access_token"]

    def request(
        self,
        method: str,
        resource: str,
        *,
        interactive: bool = False,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> requests.Response:
        token = self.acquire_token(interactive=interactive)
        request_headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Prefer": 'IdType="ImmutableId"',
            **(headers or {}),
        }
        url = resource if resource.startswith("https://") else f"{self.base_url}/{resource.lstrip('/')}"
        response = requests.request(method, url, headers=request_headers, timeout=60, **kwargs)
        if response.status_code >= 400:
            try:
                detail = response.json().get("error", {})
            except ValueError:
                detail = response.text[:500]
            raise GraphError(f"Graph {method} {resource} failed ({response.status_code}): {detail}")
        return response

    def json(self, method: str, resource: str, **kwargs: Any) -> dict[str, Any]:
        response = self.request(method, resource, **kwargs)
        return response.json() if response.content else {}
