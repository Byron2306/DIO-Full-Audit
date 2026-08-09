#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDGE_ROOT = ROOT / "edge" / "dio-edge-gateway"


def prompt(label: str) -> str:
    value = getpass.getpass(f"{label} (input hidden): ").strip()
    if not value:
        raise ValueError(f"{label} cannot be blank.")
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
        raise RuntimeError(f"Cloudflare rejected {name}.")


def listed_secrets(environment: str) -> set[str]:
    command = ["npx", "wrangler", "secret", "list"]
    if environment == "live":
        command.extend(["--env", "live"])
    result = subprocess.run(command, cwd=EDGE_ROOT, text=True, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError("Cloudflare secret verification failed.")
    return {str(item.get("name")) for item in json.loads(result.stdout)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Securely install DIO payment-provider Worker secrets.")
    parser.add_argument("provider", choices=["paypal", "payfast"])
    parser.add_argument("--environment", choices=["sandbox", "live"], default="sandbox")
    args = parser.parse_args()
    if args.provider == "paypal":
        values = {
            "PAYPAL_CLIENT_ID": prompt("PayPal client ID"),
            "PAYPAL_CLIENT_SECRET": prompt("PayPal client secret"),
            "PAYPAL_WEBHOOK_ID": prompt("PayPal webhook ID for the DIO Worker URL"),
        }
    else:
        values = {
            "PAYFAST_MERCHANT_ID": prompt("PayFast merchant ID"),
            "PAYFAST_MERCHANT_KEY": prompt("PayFast merchant key"),
            "PAYFAST_PASSPHRASE": prompt("PayFast passphrase"),
        }
    for name, value in values.items():
        upload_secret(name, value, args.environment)
    missing = set(values) - listed_secrets(args.environment)
    if missing:
        raise RuntimeError(f"Cloudflare did not report the expected {args.environment} secrets: {sorted(missing)}")
    print(
        f"{args.provider.title()} {args.environment} secrets installed in Cloudflare. "
        "Values were not displayed or stored in the project."
    )
    print(f"Verified secret names in the {args.environment} Worker namespace.")
    print("Provider activation remains controlled by the selected Worker's environment configuration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
