from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MS9_VERIFIED = "DIO_MARKET_SENSORIUM_AUTONOMIC_MULTI_CYCLE_SOAK_VERIFIED"
MS10_VERIFIED = "DIO_MARKET_SENSORIUM_OPERATOR_SURFACE_CONVERGENCE_VERIFIED"

CANONICAL_COCKPIT = "state/market_sensorium/COMMERCIAL_COCKPIT.json"
CANONICAL_SOAK = "state/market_sensorium/MARKET_SENSORIUM_MS9_RECEIPT.json"
CURRENT_ROOT = "/home/byron/DIO-Full-Audit"
STALE_ROOT = "/home/byron/DIO-Product-Factory"

REQUIRED_SENSORIUM_MARKERS = (
    "phase",
    "commercial time",
    "rank",
    "hivenance",
    "competitive offer",
    "habitat",
    "learned",
    "authority",
    "ms-9",
)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _surface(
    root: Path,
    *,
    name: str,
    port: int,
    page: str,
    server: str,
    service: str,
    expected_server_symbol: str,
    preserves: str,
) -> dict[str, Any]:
    page_text = _read(root / page)
    server_text = _read(root / server)
    service_text = _read(root / service)
    lower = page_text.lower()
    markers = {marker: marker in lower for marker in REQUIRED_SENSORIUM_MARKERS}
    canonical_cockpit_bound = CANONICAL_COCKPIT in page_text or "/" + CANONICAL_COCKPIT in page_text
    canonical_soak_bound = CANONICAL_SOAK in page_text or "/" + CANONICAL_SOAK in page_text
    current_repo_bound = CURRENT_ROOT in service_text and STALE_ROOT not in service_text
    expected_server_bound = expected_server_symbol in server_text and server in service_text
    localhost_bound = f"--port {port}" in service_text and "127.0.0.1" in service_text
    return {
        "name": name,
        "port": int(port),
        "page": page,
        "server": server,
        "service": service,
        "page_present": bool(page_text),
        "server_present": bool(server_text),
        "service_present": bool(service_text),
        "canonical_cockpit_bound": canonical_cockpit_bound,
        "canonical_ms9_bound": canonical_soak_bound,
        "sensorium_marker_coverage": sum(1 for value in markers.values() if value),
        "sensorium_markers": markers,
        "current_repo_bound": current_repo_bound,
        "stale_repo_reference_present": STALE_ROOT in service_text,
        "expected_server_bound": expected_server_bound,
        "localhost_bound": localhost_bound,
        "existing_operator_capability_preserved": preserves in server_text or preserves in page_text,
        "independent_sensorium_truth_engine_created": False,
        "authority_created": False,
        "external_effects": False,
    }


def audit_operator_convergence(root: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    ms9 = _json(root / CANONICAL_SOAK)
    shared_page = "dashboard/ms10.html"
    surfaces = [
        _surface(
            root,
            name="CONTROL_DECK",
            port=8765,
            page=shared_page,
            server="scripts/serve_control_deck_ms10.py",
            service="deploy/systemd/dio-control-deck.service",
            expected_server_symbol="ControlDeckHandler",
            preserves="ControlDeckHandler",
        ),
        _surface(
            root,
            name="MARKET_COMMAND",
            port=8770,
            page=shared_page,
            server="scripts/serve_market_command_ms10.py",
            service="deploy/systemd/dio-market-command.service",
            expected_server_symbol="Handler",
            preserves="Handler",
        ),
        _surface(
            root,
            name="GOLDENEYE",
            port=8766,
            page="dashboard/goldeneye-ms10.html",
            server="scripts/serve_goldeneye_ms10.py",
            service="deploy/systemd/dio-goldeneye-portfolio.service",
            expected_server_symbol="ControlDeckHandler",
            preserves="/api/control/state",
        ),
    ]
    canonical = all(item["canonical_cockpit_bound"] and item["canonical_ms9_bound"] for item in surfaces)
    current_repo = all(item["current_repo_bound"] and not item["stale_repo_reference_present"] for item in surfaces)
    servers = all(item["expected_server_bound"] and item["localhost_bound"] for item in surfaces)
    coverage = all(int(item["sensorium_marker_coverage"]) == len(REQUIRED_SENSORIUM_MARKERS) for item in surfaces)
    preserved = all(bool(item["existing_operator_capability_preserved"]) for item in surfaces)
    return {
        "schema": "dio.market_sensorium.operator_surface_convergence.v1",
        "ms9_acceptance": ms9.get("ms9_acceptance") or "UNAVAILABLE",
        "surface_count": len(surfaces),
        "surfaces": surfaces,
        "all_surfaces_canonical_truth_bound": canonical,
        "all_surfaces_current_repo_bound": current_repo,
        "all_surface_servers_current_and_local": servers,
        "all_sensorium_features_visible": coverage,
        "existing_operator_capabilities_preserved": preserved,
        "control_deck_action_plane_preserved": "ControlDeckHandler" in _read(root / "scripts/serve_control_deck_ms10.py"),
        "market_command_action_plane_preserved": "Handler" in _read(root / "scripts/serve_market_command_ms10.py"),
        "goldeneye_portfolio_projection_current_repo_bound": "/api/control/state" in _read(root / "dashboard/goldeneye-ms10.html"),
        "goldeneye_phase9_stale_server_retired": STALE_ROOT not in _read(root / "deploy/systemd/dio-goldeneye-portfolio.service"),
        "independent_sensorium_truth_engines_created": 0,
        "best_target_claimed": False,
        "market_demand_claimed": False,
        "willingness_to_pay_proved": False,
        "commercial_success_proved": False,
        "authority_created": False,
        "external_effects": False,
    }


def apply_ms10_gate(summary: dict[str, Any]) -> str:
    if str(summary.get("ms9_acceptance") or "") != MS9_VERIFIED:
        return "PENDING_VERIFIED_MS9_RECEIPT"
    if int(summary.get("surface_count") or 0) < 3:
        return "PENDING_ALL_OPERATOR_SURFACES"
    if not bool(summary.get("all_surfaces_canonical_truth_bound", False)):
        return "REFUSE_DIVERGENT_OPERATOR_TRUTH_SOURCES"
    if not bool(summary.get("all_surfaces_current_repo_bound", False)):
        return "REFUSE_STALE_OPERATOR_SURFACE_REPOSITORY"
    if not bool(summary.get("all_surface_servers_current_and_local", False)):
        return "PENDING_CURRENT_LOCAL_OPERATOR_SERVERS"
    if not bool(summary.get("all_sensorium_features_visible", False)):
        return "PENDING_COMPLETE_SENSORIUM_SURFACE_COVERAGE"
    if not bool(summary.get("existing_operator_capabilities_preserved", False)):
        return "REFUSE_OPERATOR_CAPABILITY_REGRESSION"
    if int(summary.get("independent_sensorium_truth_engines_created") or 0) != 0:
        return "REFUSE_DUPLICATED_SENSORIUM_TRUTH_ENGINE"
    if any(bool(summary.get(key, False)) for key in (
        "best_target_claimed",
        "market_demand_claimed",
        "willingness_to_pay_proved",
        "commercial_success_proved",
        "authority_created",
        "external_effects",
    )):
        return "REFUSE_OPERATOR_SURFACE_TRUTH_OR_AUTHORITY_INFLATION"
    return MS10_VERIFIED
