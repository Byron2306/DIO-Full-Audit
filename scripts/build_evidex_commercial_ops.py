#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EVIDEX_ROOT = Path("/home/byron/Evidex")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        key = key.strip()
        value = raw_value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def is_url(value: str) -> bool:
    return value.strip().lower().startswith(("http://", "https://"))


def google_form_url(form_id_or_url: str) -> str:
    value = (form_id_or_url or "").strip()
    if not value:
        return ""
    if is_url(value):
        return value
    if value.startswith("1FAIpQL"):
        return f"https://docs.google.com/forms/d/e/{value}/viewform"
    return f"https://docs.google.com/forms/d/{value}/edit"


def google_drive_url(folder_id_or_url: str) -> str:
    value = (folder_id_or_url or "").strip()
    if not value:
        return ""
    if is_url(value):
        return value
    return f"https://drive.google.com/drive/folders/{value}"


def redacted_env_presence(values: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in sorted(values.items()):
        upper = key.upper()
        if any(token in upper for token in ["KEY", "SECRET", "TOKEN", "PASSWORD", "PASSPHRASE"]):
            out[key] = "set_redacted" if value else "empty"
        elif key in {"PAYPAL_LINK", "PAYMENT_LINK"}:
            out[key] = "set_public_link_redacted" if value else "empty"
        elif key in {"EVIDEX_GOOGLE_FORM_ID", "EVIDEX_GOOGLE_DRIVE_FOLDER_ID"}:
            out[key] = "set"
        else:
            out[key] = "set" if value else "empty"
    return out


def load_latest_rotation(evidex_root: Path) -> tuple[Path | None, list[dict[str, Any]]]:
    rotation_dir = evidex_root / "output" / "marketing"
    candidates = sorted(rotation_dir.glob("rotation_*.json"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    if not candidates:
        return None, []
    path = candidates[0]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return path, []
    if not isinstance(data, list):
        return path, []
    return path, [item for item in data if isinstance(item, dict)]


def safe_platform(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "platform"


def build_linked_ads(
    rotation: list[dict[str, Any]],
    *,
    google_form: str,
    landing_page: str,
    preview_path: str,
    limit: int,
) -> list[dict[str, Any]]:
    linked: list[dict[str, Any]] = []
    for index, item in enumerate(rotation[:limit], start=1):
        platform = str(item.get("platform") or "LinkedIn")
        response_link = google_form or landing_page
        primary = str(item.get("primary_text") or "").strip()
        suffix = f"\n\nPilot intake: {response_link}\nPreview: {landing_page}#proof"
        linked.append(
            {
                "slot": index,
                "day": item.get("day", ""),
                "stream": item.get("stream", ""),
                "platform": platform,
                "persona": item.get("persona", ""),
                "headline": item.get("headline", ""),
                "tagline": item.get("tagline", ""),
                "primary_text": primary + suffix,
                "cta": item.get("cta", "Request a pilot pack"),
                "template_image": item.get("template_image", ""),
                "response_link": response_link,
                "landing_page": landing_page,
                "preview_path": preview_path,
                "posting_kit_hint": f"campaigns/phase3/evidex/commercial_ops/posting_kits/{index:02d}_{safe_platform(platform)}",
            }
        )
    return linked


def write_public_links_js(path: Path, *, google_form: str, landing_page: str) -> None:
    payload = {
        "google_form_url": google_form,
        "landing_page": landing_page,
        "generated_at": utc_now(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "window.EVIDEX_COMMERCIAL_LINKS = "
        + json.dumps(payload, indent=2)
        + ";\n",
        encoding="utf-8",
    )


def write_markdown(
    path: Path,
    *,
    google_form: str,
    drive_root_public: bool,
    linked_ads: list[dict[str, Any]],
    landing_page: str,
    preview_path: str,
) -> None:
    lines = [
        "# Evidex Commercial Ops Bridge",
        "",
        f"Updated: {utc_now()}",
        "",
        "## Intake Link",
        "",
        f"- Landing page: `{landing_page}`",
        f"- Google intake form: {'configured' if google_form else 'not configured'}",
        f"- Drive root: {'configured, kept internal' if drive_root_public else 'not configured'}",
        "",
        "## Payment Gate",
        "",
        "Evidex already has the right commercial skeleton:",
        "",
        "- Google Form submission creates a Drive job folder under `EvidenceEngine/incoming/<job>/`.",
        "- Apps Script writes `intake.yaml`, `CONTACT_EMAIL.txt`, upload instructions, `INVOICE_ID.txt`, and `INVOICE.txt`.",
        "- Optional payment links are created for Stripe, PayPal, and PayFast depending on configured Script Properties.",
        "- Webhooks or manual operator confirmation create `PAID.txt` and `PAYMENT_RECEIPT.txt`.",
        "- The local watcher can run with `REQUIRE_PAYMENT=1`, which blocks processing until `PAID.txt` exists.",
        "- Delivery emailer can also require `PAID.txt` before sending `DELIVERABLE.zip`.",
        "",
        "## Immediate Sales Use",
        "",
        "Use the landing page for proof and positioning. Use the Google Form for live Drive/payment intake when ready.",
        "",
        f"Preview MP4: `{preview_path}`",
        "",
        "## Linked Ad Slots",
        "",
    ]
    for ad in linked_ads:
        lines.extend(
            [
                f"### {ad['slot']:02d}. {ad['platform']} - {ad.get('persona') or 'General'}",
                "",
                f"**Headline:** {ad.get('headline', '')}",
                "",
                f"**CTA:** {ad.get('cta', '')}",
                "",
                "```text",
                str(ad.get("primary_text", "")).strip(),
                "```",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build(args: argparse.Namespace) -> dict[str, Any]:
    evidex_root = Path(args.evidex_root).expanduser().resolve()
    env_values = read_env(evidex_root / "evidex.env")
    google_form = google_form_url(env_values.get("EVIDEX_GOOGLE_FORM_ID", ""))
    drive_root = google_drive_url(env_values.get("EVIDEX_GOOGLE_DRIVE_FOLDER_ID", ""))
    rotation_path, rotation = load_latest_rotation(evidex_root)

    landing_page = args.landing_page
    preview_path = args.preview_path
    linked_ads = build_linked_ads(
        rotation,
        google_form=google_form,
        landing_page=landing_page,
        preview_path=preview_path,
        limit=args.limit,
    )

    out_dir = ROOT / "campaigns" / "phase3" / "evidex" / "commercial_ops"
    out_dir.mkdir(parents=True, exist_ok=True)
    linked_ads_path = out_dir / "linked_ad_rotation.json"
    linked_ads_path.write_text(json.dumps(linked_ads, indent=2), encoding="utf-8")
    write_markdown(
        out_dir / "COMMERCIAL_OPS_BRIDGE.md",
        google_form=google_form,
        drive_root_public=bool(drive_root),
        linked_ads=linked_ads,
        landing_page=landing_page,
        preview_path=preview_path,
    )
    write_public_links_js(
        ROOT / "sites" / "evidex" / "assets" / "commercial-links.js",
        google_form=google_form,
        landing_page=landing_page,
    )

    receipt = {
        "schema": "knowedge.evidex_commercial_ops_bridge.v1",
        "created_at": utc_now(),
        "status": "commercial_ops_bridge_ready",
        "source_repo": str(evidex_root),
        "env_presence": redacted_env_presence(env_values),
        "public_intake": {
            "google_form_configured": bool(google_form),
            "landing_page": landing_page,
            "site_links_js": "sites/evidex/assets/commercial-links.js",
        },
        "internal_drive": {
            "drive_root_configured": bool(drive_root),
            "note": "Drive folder URL is intentionally not copied into the public landing assets.",
        },
        "payment_gate": {
            "local_payment_link_present": bool(env_values.get("PAYMENT_LINK") or env_values.get("PAYPAL_LINK")),
            "script_support": ["Stripe Checkout", "PayPal Checkout/webhook", "PayFast ITN/webhook", "manual PAID.txt"],
            "processing_blocker": "REQUIRE_PAYMENT=1 makes Evidex watcher wait for PAID.txt before processing.",
            "delivery_blocker": "Drive delivery emailer can also require PAID.txt before sending DELIVERABLE.zip.",
        },
        "ad_rotation": {
            "source": str(rotation_path) if rotation_path else "",
            "source_count": len(rotation),
            "linked_count": len(linked_ads),
            "output": str(linked_ads_path.relative_to(ROOT)),
        },
        "files": [
            "campaigns/phase3/evidex/commercial_ops/COMMERCIAL_OPS_BRIDGE.md",
            "campaigns/phase3/evidex/commercial_ops/linked_ad_rotation.json",
            "sites/evidex/assets/commercial-links.js",
        ],
    }
    receipt_path = out_dir / "COMMERCIAL_OPS_RECEIPT.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Bridge Evidex Google intake, ad links, and payment gates into AutoRelease.")
    parser.add_argument("--evidex-root", default=str(EVIDEX_ROOT))
    parser.add_argument("--landing-page", default="http://127.0.0.1:8787/")
    parser.add_argument(
        "--preview-path",
        default="/home/byron/Downloads/NicheFoundry_Phase11/episodes/knowedge-evidex-evidence-pack-send-the-evidence-mess-get-back-a-review-ready-donor-audit-or-complia-b24cd1d6/free_preview.mp4",
    )
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()
    receipt = build(args)
    print(json.dumps({"status": receipt["status"], "linked_ads": receipt["ad_rotation"]["linked_count"], "google_form_configured": receipt["public_intake"]["google_form_configured"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
