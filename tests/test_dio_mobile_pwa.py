from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard"


def test_android_pwa_manifest_is_standalone_and_loopback_scoped():
    manifest = json.loads((DASHBOARD / "dio-mobile.webmanifest").read_text(encoding="utf-8"))

    assert manifest["name"] == "DIO Mobile"
    assert manifest["short_name"] == "DIO"
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "/"
    assert manifest["scope"] == "/"
    assert manifest["orientation"] == "any"

    icons = {(row["sizes"], row["type"], row.get("purpose")) for row in manifest["icons"]}
    assert ("192x192", "image/png", "any maskable") in icons
    assert ("512x512", "image/png", "any maskable") in icons


def test_android_pwa_icons_are_real_png_assets():
    for size in (192, 512):
        path = DASHBOARD / f"dio-mobile-icon-{size}.png"
        body = path.read_bytes()
        assert body.startswith(b"\x89PNG\r\n\x1a\n")
        assert len(body) > 256


def test_launcher_page_registers_mobile_shell_without_weakening_truth_gate():
    page = (DASHBOARD / "dio-launcher.html").read_text(encoding="utf-8")
    worker = (DASHBOARD / "dio-mobile-sw.js").read_text(encoding="utf-8")

    assert 'rel="manifest" href="/manifest.webmanifest"' in page
    assert 'name="theme-color"' in page
    assert 'name="mobile-web-app-capable" content="yes"' in page
    assert 'navigator.serviceWorker.register("/sw.js")' in page
    assert "window.isSecureContext" in page

    assert "/api/launcher/state" in worker
    assert "networkOnlyTruth" in worker
    assert "cache: \"no-store\"" in worker
    assert "caches.match(request)" not in worker.split("function networkOnlyTruth", 1)[1].split("}", 1)[0]


def test_launcher_server_serves_only_bounded_pwa_assets():
    server = (ROOT / "scripts" / "serve_dio_launcher.py").read_text(encoding="utf-8")

    for marker in (
        '"/manifest.webmanifest"',
        '"/sw.js"',
        '"/dio-mobile-icon-192.png"',
        '"/dio-mobile-icon-512.png"',
    ):
        assert marker in server
    assert "application/manifest+json" in server
    assert "application/javascript; charset=utf-8" in server
    assert "image/png" in server
    assert "def do_POST" in server and "405" in server


def test_termux_tunnel_forwards_every_dio_surface_and_fails_closed():
    script = (ROOT / "scripts" / "android" / "dio-mobile-tunnel.sh").read_text(encoding="utf-8")

    for port in (8764, 8765, 8766, 8770):
        assert f"-L {port}:127.0.0.1:{port}" in script
    assert "ExitOnForwardFailure=yes" in script
    assert "ServerAliveInterval=30" in script
    assert "ServerAliveCountMax=3" in script
    assert "http://127.0.0.1:8764/" in script
    assert "0.0.0.0" not in script
