#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.microsoft_graph.client import GraphClient, GraphError, load_config  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Authorise and safely probe the DIO Microsoft Graph account.")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "microsoft_graph.local.json")
    parser.add_argument("--device-login", action="store_true", help="Show a Microsoft device-login code when no cached token exists.")
    args = parser.parse_args()
    config = load_config(args.config.resolve())
    graph = GraphClient(config)
    account = graph.json("GET", "/me?$select=id,displayName,userPrincipalName,mail", interactive=args.device_login)
    inbox = graph.json("GET", "/me/mailFolders/inbox?$select=id,displayName,totalItemCount,unreadItemCount")
    drive = graph.json("GET", "/me/drive?$select=id,driveType,owner,quota")
    result = {
        "status": "connected",
        "account": {key: account.get(key) for key in ["displayName", "userPrincipalName", "mail"]},
        "mail": {key: inbox.get(key) for key in ["displayName", "totalItemCount", "unreadItemCount"]},
        "onedrive": {
            "driveType": drive.get("driveType"),
            "owner": drive.get("owner", {}).get("user", {}).get("displayName"),
            "quota_state": drive.get("quota", {}).get("state"),
        },
        "granted_send_authority": "https://graph.microsoft.com/Mail.Send" in config["scopes"],
        "outbound_graph_send_enabled": bool(config.get("outbound_graph_send_enabled")),
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GraphError as error:
        print(f"Microsoft Graph setup required: {error}", file=sys.stderr)
        raise SystemExit(2)
