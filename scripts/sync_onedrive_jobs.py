#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.microsoft_graph.client import GraphClient, load_config  # noqa: E402


PRODUCTS = ("HOMS", "EVIDEX", "SOPHIA", "VAMP")
STATES = ("incoming", "processing", "done", "deliveries", "failed")


def timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def remote_path(value: str) -> str:
    return urllib.parse.quote(value.strip("/"), safe="/")


def safe_name(value: str) -> str:
    if not value or value in {".", ".."} or Path(value).name != value or "/" in value or "\\" in value:
        raise ValueError(f"Unsafe OneDrive item name: {value!r}")
    return value


def children(graph: GraphClient, parent: str) -> list[dict[str, Any]]:
    if parent:
        resource = f"/me/drive/root:/{remote_path(parent)}:/children?$top=200"
    else:
        resource = "/me/drive/root/children?$top=200"
    items = []
    while resource:
        page = graph.json("GET", resource)
        items.extend(page.get("value", []))
        resource = page.get("@odata.nextLink")
    return items


def ensure_folder(graph: GraphClient, parent: str, name: str) -> dict[str, Any]:
    name = safe_name(name)
    existing = next((item for item in children(graph, parent) if item.get("name") == name and "folder" in item), None)
    if existing:
        return existing
    endpoint = f"/me/drive/root:/{remote_path(parent)}:/children" if parent else "/me/drive/root/children"
    return graph.json(
        "POST",
        endpoint,
        headers={"Content-Type": "application/json"},
        json={"name": name, "folder": {}, "@microsoft.graph.conflictBehavior": "fail"},
    )


def ensure_tree(graph: GraphClient, root_name: str) -> list[str]:
    created = []
    ensure_folder(graph, "", root_name)
    created.append(root_name)
    for product in PRODUCTS:
        product_path = f"{root_name}/{product}"
        ensure_folder(graph, root_name, product)
        created.append(product_path)
        for state in STATES:
            ensure_folder(graph, product_path, state)
            created.append(f"{product_path}/{state}")
    return created


def download_item(graph: GraphClient, item: dict[str, Any], destination: Path) -> int:
    name = safe_name(item["name"])
    target = destination / name
    if "folder" in item:
        target.mkdir(parents=True, exist_ok=True)
        total = 0
        page = graph.json("GET", f"/me/drive/items/{item['id']}/children?$top=200")
        while True:
            for child in page.get("value", []):
                total += download_item(graph, child, target)
            next_link = page.get("@odata.nextLink")
            if not next_link:
                break
            page = graph.json("GET", next_link)
        marker = {"remote_item_id": item["id"], "remote_etag": item.get("eTag"), "downloaded_at": timestamp()}
        (target / ".dio_onedrive_item.json").write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")
        return total
    target.parent.mkdir(parents=True, exist_ok=True)
    response = graph.request("GET", f"/me/drive/items/{item['id']}/content")
    temporary = target.with_suffix(target.suffix + ".download")
    temporary.write_bytes(response.content)
    temporary.replace(target)
    return 1


def pull_incoming(graph: GraphClient, root_name: str, mirror_root: Path, products: list[str]) -> dict[str, Any]:
    jobs = []
    for product in products:
        product = product.upper()
        if product not in PRODUCTS:
            raise ValueError(f"Unknown product: {product}")
        parent = f"{root_name}/{product}/incoming"
        destination = mirror_root / product / "incoming"
        destination.mkdir(parents=True, exist_ok=True)
        for item in children(graph, parent):
            if "folder" not in item:
                continue
            local_job = destination / safe_name(item["name"])
            marker_path = local_job / ".dio_onedrive_item.json"
            marker = json.loads(marker_path.read_text(encoding="utf-8")) if marker_path.exists() else {}
            if marker.get("remote_etag") == item.get("eTag"):
                jobs.append({"product": product, "job": item["name"], "state": "unchanged", "files": 0})
                continue
            files = download_item(graph, item, destination)
            jobs.append({"product": product, "job": item["name"], "state": "downloaded", "files": files})
    return {"schema": "dio.onedrive.pull_receipt.v1", "created_at": timestamp(), "jobs": jobs}


def upload_file(graph: GraphClient, local_file: Path, target_path: str) -> None:
    mime = mimetypes.guess_type(local_file.name)[0] or "application/octet-stream"
    graph.request(
        "PUT",
        f"/me/drive/root:/{remote_path(target_path)}:/content",
        headers={"Content-Type": mime},
        data=local_file.read_bytes(),
    )


def push_delivery(graph: GraphClient, root_name: str, product: str, job_dir: Path) -> dict[str, Any]:
    product = product.upper()
    if product not in PRODUCTS:
        raise ValueError(f"Unknown product: {product}")
    if not job_dir.is_dir():
        raise FileNotFoundError(job_dir)
    job_name = safe_name(job_dir.name)
    parent = f"{root_name}/{product}/deliveries"
    ensure_folder(graph, parent, job_name)
    uploaded = []
    for local_file in sorted(job_dir.rglob("*")):
        if not local_file.is_file() or local_file.name.startswith(".dio_"):
            continue
        relative = local_file.relative_to(job_dir)
        current_parent = f"{parent}/{job_name}"
        for part in relative.parts[:-1]:
            ensure_folder(graph, current_parent, safe_name(part))
            current_parent = f"{current_parent}/{part}"
        target = f"{parent}/{job_name}/{relative.as_posix()}"
        upload_file(graph, local_file, target)
        uploaded.append(relative.as_posix())
    return {
        "schema": "dio.onedrive.delivery_receipt.v1",
        "created_at": timestamp(),
        "product": product,
        "job": job_name,
        "remote_path": f"{parent}/{job_name}",
        "uploaded_files": uploaded,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Move governed DIO jobs between OneDrive and the local processing mirror.")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "microsoft_graph.local.json")
    parser.add_argument("--device-login", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init")
    pull = subparsers.add_parser("pull")
    pull.add_argument("--product", action="append", choices=PRODUCTS)
    push = subparsers.add_parser("push")
    push.add_argument("--product", required=True, choices=PRODUCTS)
    push.add_argument("--job-dir", type=Path, required=True)
    args = parser.parse_args()

    config = load_config(args.config.resolve())
    graph = GraphClient(config)
    graph.acquire_token(interactive=args.device_login)
    root_name = safe_name(config.get("onedrive_remote_root", "DIO"))
    mirror_root = Path(config["local_mirror_root"]).expanduser().resolve()
    receipt_dir = ROOT / "runs" / "microsoft_graph"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    if args.command == "init":
        receipt = {"schema": "dio.onedrive.init_receipt.v1", "created_at": timestamp(), "folders": ensure_tree(graph, root_name)}
    elif args.command == "pull":
        receipt = pull_incoming(graph, root_name, mirror_root, args.product or ["HOMS", "EVIDEX"])
    else:
        receipt = push_delivery(graph, root_name, args.product, args.job_dir.resolve())
    receipt_path = receipt_dir / f"{args.command}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**receipt, "receipt_path": str(receipt_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
