#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cockpit_runtime import atlas_projection, patch_advanced_dashboard, runtime_readiness  # noqa: E402
from dio_secrets import load_secret_env  # noqa: E402
from operator_evidence_intake import stage_controlled_evidence_run  # noqa: E402
from operator_production import (  # noqa: E402
    create_marketing_pack,
    production_state,
    run_evidence_gate,
    run_factory_test,
)
from portfolio_runtime import import_portfolio  # noqa: E402
from presence_core.operator_views import case_detail_view, case_list_view, commercial_pipeline_view  # noqa: E402
from presence_core.state import list_needs_you  # noqa: E402
from products.commercial_pricing_registry import build_commercial_pricing_registry  # noqa: E402
from semantic_marketing import PROFILE_COMPATIBILITY, semantic_marketing_brief  # noqa: E402
from scripts.build_operator_dashboard import build_dashboard_state  # noqa: E402
from scripts.serve_control_deck import EVENT_LOG, emit_event  # noqa: E402
from scripts.serve_control_deck_ms10 import MS10ControlDeckHandler, _read_json_body  # noqa: E402


SEMANTIC_BOUNDARY_ASSET = "config/atlas/dio_meta_incarnation_crosswalk.csv"


def _presence_state_root() -> Path:
    configured = str(os.getenv("DIO_PRESENCE_STATE_ROOT") or "state/presence").strip()
    path = Path(configured)
    return path if path.is_absolute() else ROOT / path


def _commercial_state() -> dict:
    state_root = _presence_state_root()
    cases = case_list_view(state_root, 500)
    pipeline = commercial_pipeline_view(state_root)
    pricing = build_commercial_pricing_registry(ROOT)
    needs_you = [row for row in list_needs_you(state_root, 1000) if row.get("state") == "open"]
    return {
        "schema": "dio.business_commercial_projection.v1",
        "canonical_state_root": str(state_root),
        "cases": cases,
        "pipeline": pipeline,
        "pricing": pricing,
        "needs_you": {"count": len(needs_you), "items": needs_you[:100]},
        "truth_boundary": pipeline.get("value_boundary"),
        "authority_created": False,
        "external_effects": False,
    }


class BusinessWorkbenchHandler(MS10ControlDeckHandler):
    server_version = "DIOBusinessWorkbench/3.7"

    def _serve_business_page(self) -> None:
        page = (ROOT / "dashboard" / "business.html").read_text(encoding="utf-8")
        page = page.replace(
            '<div class="topnav">',
            '<div class="topnav"><a class="btn green" href="/dashboard/production.html">Production Studio</a><a class="btn gold" href="/dashboard/connections.html">Connections & Secrets</a>',
            1,
        )
        page = page.replace(
            '<a class="btn" href="#presence">Sites & social</a>',
            '<a class="btn" href="#presence">Sites & social</a><a class="btn green" href="/dashboard/production.html">Production</a><a class="btn" href="/dashboard/connections.html">Secrets & connections</a>',
            1,
        )
        youtube = '<a class="card launch social" target="_blank" rel="noreferrer" href="https://www.youtube.com/@DIOworkflows"><small>Social</small><b>YouTube</b><span>@DIOworkflows</span></a>'
        tiktok = (
            '<a class="card launch social" target="_blank" rel="noreferrer" href="https://business.tiktok.com/"><small>Social</small><b>TikTok Business</b><span>Business account / center</span></a>'
            '<a class="card launch social" target="_blank" rel="noreferrer" href="https://ads.tiktok.com/"><small>Advertising</small><b>TikTok Ads</b><span>Ads Manager</span></a>'
        )
        page = page.replace(youtube, youtube + tiktok, 1)
        for injection in (
            '<script src="/dashboard/atlas_slice1.js"></script>',
            '<script src="/dashboard/commercial_slice2.js"></script>',
        ):
            if injection not in page:
                page = page.replace("</body>", injection + "</body>", 1)
        self._send_bytes(page.encode("utf-8"), "text/html; charset=utf-8")

    def _serve_production_page(self) -> None:
        page = (ROOT / "dashboard" / "production.html").read_text(encoding="utf-8")
        for injection in (
            '<script src="/dashboard/production_semantic.js"></script>',
            '<script src="/dashboard/production_slice1.js"></script>',
        ):
            if injection not in page:
                page = page.replace("</body>", injection + "</body>", 1)
        self._send_bytes(page.encode("utf-8"), "text/html; charset=utf-8")

    def _serve_advanced_page(self) -> None:
        page = (ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")
        self._send_bytes(patch_advanced_dashboard(page).encode("utf-8"), "text/html; charset=utf-8")

    @staticmethod
    def _merge_semantic_marketing(payload: dict) -> tuple[dict, dict]:
        merged = dict(payload)
        incarnation = str(merged.get("incarnation") or "").strip()
        if not incarnation:
            raise ValueError("Select a canonical incarnation before creating marketing assets")
        brief = semantic_marketing_brief(incarnation)
        requested_profile = str(merged.get("profile_id") or "").strip()

        if requested_profile:
            allowed = PROFILE_COMPATIBILITY.get(requested_profile)
            if not allowed or incarnation not in allowed:
                raise ValueError(
                    f"Marketing profile {requested_profile} is not evidence-compatible with {incarnation}. "
                    "Let DIO generate the semantic brief for this incarnation instead."
                )
            if not str(merged.get("audience_id") or "").strip() and brief.get("profile_id") == requested_profile:
                merged["audience_id"] = brief.get("audience_id") or ""
        elif brief.get("profile_id"):
            merged["profile_id"] = brief["profile_id"]
            merged["audience_id"] = brief.get("audience_id") or ""
        else:
            for key, value in (brief.get("brief") or {}).items():
                if not str(merged.get(key) or "").strip():
                    merged[key] = value
            if not str(merged.get("source_image") or "").strip() and brief.get("source_image"):
                merged["source_image"] = brief["source_image"]
            if not str(merged.get("proof_asset") or "").strip() and brief.get("proof_asset"):
                merged["proof_asset"] = brief["proof_asset"]

            if not str(merged.get("proof_asset") or "").strip():
                merged["proof_asset"] = SEMANTIC_BOUNDARY_ASSET
                brief["evidence_binding"] = {
                    "kind": "CANONICAL_PORTFOLIO_BOUNDARY",
                    "path": SEMANTIC_BOUNDARY_ASSET,
                    "execution_proof_claimed": False,
                }
            else:
                brief["evidence_binding"] = {
                    "kind": "PRODUCT_PROOF_ASSET",
                    "path": str(merged["proof_asset"]),
                    "execution_proof_claimed": False,
                }
        return merged, brief

    @staticmethod
    def _bind_semantic_receipt(result: dict, brief: dict) -> None:
        output_dir = Path(str(result.get("output_dir") or ""))
        if not output_dir.is_dir():
            return
        brief_path = output_dir / "SEMANTIC_MARKETING_BRIEF.json"
        brief_path.write_text(json.dumps(brief, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        result["semantic_brief_path"] = str(brief_path)
        result["semantic_brief"] = brief
        receipt_path = output_dir / "OPERATOR_MARKETING_RECEIPT.json"
        if receipt_path.is_file():
            try:
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                receipt = {}
            if isinstance(receipt, dict):
                receipt["semantic_brief_path"] = str(brief_path)
                receipt["semantic_brief_truth_class"] = brief.get("truth_class")
                receipt["semantic_generation_mode"] = brief.get("generation_mode")
                receipt["semantic_evidence_binding"] = brief.get("evidence_binding") or {}
                receipt["observed_market_demand"] = False
                receipt["best_audience_proved"] = False
                receipt["authority_created"] = False
                receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    def do_GET(self) -> None:
        split = urlsplit(self.path)
        route = split.path
        if route in {"/dashboard/production.html", "/production"}:
            self._serve_production_page()
            return
        if route == "/dashboard/index.html":
            self._serve_advanced_page()
            return
        if route == "/api/business/commercial/state":
            try:
                self.send_json(_commercial_state())
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                self.send_json({"error": "commercial_state_unavailable", "message": str(exc), "authority_created": False}, HTTPStatus.SERVICE_UNAVAILABLE)
            return
        if route == "/api/business/commercial/case":
            case_id = str((parse_qs(split.query).get("case_id") or [""])[0]).strip()
            if not case_id:
                self.send_json({"error": "case_id_required", "authority_created": False}, HTTPStatus.BAD_REQUEST)
                return
            try:
                self.send_json(case_detail_view(_presence_state_root(), case_id))
            except KeyError:
                self.send_json({"error": "customer_case_not_found", "case_id": case_id, "authority_created": False}, HTTPStatus.NOT_FOUND)
            return
        if route == "/api/business/atlas":
            self.send_json(atlas_projection(ROOT, build_dashboard_state()))
            return
        if route == "/api/business/production/marketing-brief":
            incarnation = str((parse_qs(split.query).get("incarnation") or [""])[0]).strip()
            try:
                self.send_json(semantic_marketing_brief(incarnation))
            except ValueError as exc:
                self.send_json({"error": "semantic_brief_blocked", "message": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if route == "/api/business/production/state":
            state = production_state()
            state["marketing"]["profile_compatibility"] = {key: sorted(value) for key, value in PROFILE_COMPATIBILITY.items()}
            state["marketing"]["semantic_brief_endpoint"] = "/api/business/production/marketing-brief"
            state["marketing"]["manual_pain_audience_required"] = False
            state["marketing"]["semantic_boundary_media_fallback"] = True
            state["runtime_readiness"] = runtime_readiness(ROOT)
            self.send_json(state)
            return
        if route == "/api/business/portfolio":
            self.send_json(import_portfolio(force=False))
            return
        if route == "/api/business/health":
            portfolio = import_portfolio(force=False)
            readiness = runtime_readiness(ROOT)
            self.send_json(
                {
                    "ok": True,
                    "service": "dio-business",
                    "version": "3.7",
                    "portfolio_auto_import": True,
                    "canonical_incarnations": portfolio.get("canonical_incarnation_count", 0),
                    "commercial_spine": True,
                    "commercial_state_endpoint": "/api/business/commercial/state",
                    "production_studio": True,
                    "marketing_asset_factory": True,
                    "semantic_marketing_briefs": True,
                    "manual_pain_audience_required": False,
                    "semantic_boundary_media_fallback": True,
                    "fresh_controlled_evidence_runs": True,
                    "factory_test_bench": True,
                    "evidence_gate": True,
                    "artifact_gateway": True,
                    "atlas_surface": True,
                    "marketing_profile_compatibility_enforced": True,
                    "candidate_incarnations_promoted": False,
                    "runtime_readiness": readiness,
                }
            )
            return
        super().do_GET()

    def do_POST(self) -> None:
        route = urlsplit(self.path).path
        if route not in {
            "/api/business/portfolio/import",
            "/api/business/production/marketing",
            "/api/business/production/evidence-run",
            "/api/business/production/factory-test",
            "/api/business/production/evidence-gate",
        }:
            super().do_POST()
            return
        try:
            payload = _read_json_body(self, 65536)
            if payload.get("confirmed") is not True:
                raise ValueError("Production actions require explicit operator confirmation")
            if route == "/api/business/portfolio/import":
                result = import_portfolio(force=True)
                emit_event(EVENT_LOG, "portfolio.runtime_imported", "info", "portfolio", "DIO-META-PORTFOLIO", {"canonical_incarnations": result.get("canonical_incarnation_count"), "candidate_incarnations_imported": 0})
            elif route == "/api/business/production/marketing":
                payload, semantic_brief = self._merge_semantic_marketing(payload)
                result = create_marketing_pack(payload)
                self._bind_semantic_receipt(result, semantic_brief)
                emit_event(
                    EVENT_LOG,
                    "production.marketing_pack_created",
                    "action",
                    "marketing_pack",
                    result["run_id"],
                    {
                        "incarnation": result["incarnation"],
                        "render_reel_requested": result["render_reel_requested"],
                        "semantic_brief_truth_class": semantic_brief.get("truth_class"),
                        "semantic_generation_mode": semantic_brief.get("generation_mode"),
                        "semantic_evidence_binding": semantic_brief.get("evidence_binding") or {},
                        "publication_authorized": False,
                        "market_demand_claimed": False,
                    },
                )
            elif route == "/api/business/production/evidence-run":
                result = stage_controlled_evidence_run(payload)
                emit_event(EVENT_LOG, "production.controlled_evidence_run_staged", "action", "product_job", result["job_id"], {"incarnation": result["incarnation"], "lane": result["lane"], "next_action": result["next_action"], "controlled": True, "authority_created": False})
            elif route == "/api/business/production/factory-test":
                result = run_factory_test(payload)
                emit_event(EVENT_LOG, "production.factory_test_ran", "info", "factory_test", result["run_id"], {"test_id": result["test_id"], "state": result["state"], "market_validation_claimed": False})
            else:
                result = run_evidence_gate(payload)
                emit_event(EVENT_LOG, "production.evidence_gate_ran", "action", "evidence_gate", result["run_id"], {"incarnation": result["incarnation"], "state": result["state"], "authority_created": False})
            self.send_json({"status": "completed", "result": result})
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
            self.send_json({"error": "production_action_blocked", "message": str(exc)}, HTTPStatus.BAD_REQUEST)


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve DIO BUSINESS with production studio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("DIO BUSINESS must bind to localhost")
    load_secret_env(overwrite=False)
    portfolio = import_portfolio(force=False)
    server = ThreadingHTTPServer((args.host, args.port), BusinessWorkbenchHandler)
    print(f"DIO BUSINESS: http://{args.host}:{args.port}")
    print(f"Portfolio: {portfolio.get('canonical_incarnation_count', 0)} canonical incarnations · Production Studio ACTIVE")
    print("Commercial spine: ACTIVE · same canonical customer-case projection · no browser authority secrets")
    print("Semantic marketing briefs: ACTIVE · manual audience/pain entry: NOT REQUIRED")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())