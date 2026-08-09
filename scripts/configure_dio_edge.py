#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import secrets
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDGE_ROOT = ROOT / "edge" / "dio-edge-gateway"
DEFAULT_GRAPH_STATE = Path("~/.local/state/knowedge-dio/graph-webhook-client-state").expanduser()
DEFAULT_EDGE_TOKEN = Path("~/.local/state/knowedge-dio/edge-pull-token").expanduser()


def secret_file(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(secrets.token_urlsafe(48) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)
    value = path.read_text(encoding="utf-8").strip()
    if len(value) < 32:
        raise ValueError(f"Secret at {path} is too short.")
    return value


def upload_secret(name: str, value: str, environment: str) -> None:
    command = ["npx", "wrangler", "secret", "put", name]
    if environment == "live":
        command.extend(["--env", "live"])
    result = subprocess.run(
        command,
        cwd=EDGE_ROOT,
        input=value + "\n",
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"Cloudflare rejected the {name} secret.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create and upload DIO edge secrets without displaying them.")
    parser.add_argument("--graph-state", type=Path, default=DEFAULT_GRAPH_STATE)
    parser.add_argument("--edge-token", type=Path, default=DEFAULT_EDGE_TOKEN)
    parser.add_argument("--environment", choices=["sandbox", "live"], default="sandbox")
    parser.add_argument("--commerce-only", action="store_true", help="Install only DIO_EDGE_TOKEN; omit Graph webhook state.")
    args = parser.parse_args()
    installed = []
    if not args.commerce_only:
        upload_secret("GRAPH_CLIENT_STATE", secret_file(args.graph_state.expanduser()), args.environment)
        installed.append("GRAPH_CLIENT_STATE")
    upload_secret("DIO_EDGE_TOKEN", secret_file(args.edge_token.expanduser()), args.environment)
    installed.append("DIO_EDGE_TOKEN")
    print(f"DIO {args.environment} edge secrets installed: {', '.join(installed)}")
    print(f"Local secret files secured at {args.graph_state.expanduser().parent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
