#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import shutil
import subprocess
import urllib.parse
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "dio_marketing_integration.json"
LAYERS_PATH = ROOT / "config" / "product_layers.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def write_json_if_missing(path: Path, payload: Any) -> None:
    if not path.exists():
        write_json(path, payload)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_id(prefix: str, parts: list[str], length: int = 12) -> str:
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:length]
    return f"{prefix}-{digest.upper()}"


def slug(value: str, limit: int = 60) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:limit] or "campaign"


class WaveArchive:
    def __init__(self, path: Path):
        self.path = path.resolve()
        self.archive = zipfile.ZipFile(self.path)
        self.names = self.archive.namelist()

    def member(self, basename: str) -> str:
        matches = [name for name in self.names if Path(name).name == basename]
        if len(matches) != 1:
            raise ValueError(f"Expected one {basename} in {self.path}, found {len(matches)}")
        return matches[0]

    def json(self, basename: str) -> dict[str, Any]:
        return json.loads(self.archive.read(self.member(basename)).decode("utf-8-sig"))

    def csv(self, basename: str) -> list[dict[str, str]]:
        content = self.archive.read(self.member(basename)).decode("utf-8-sig")
        return [dict(row) for row in csv.DictReader(io.StringIO(content))]

    def close(self) -> None:
        self.archive.close()


def float_value(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def int_value(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def product_layers() -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in load_json(LAYERS_PATH)["layers"]}


def install_nichefoundry_studio(config: dict[str, Any]) -> Path:
    source = (ROOT / config["nichefoundry_studio_pack"]).resolve()
    destination = Path(config["nichefoundry_root"]).resolve() / "studios" / "custom" / source.name
    if not source.exists():
        raise FileNotFoundError(f"Configured NicheFoundry studio pack does not exist: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists() or destination.read_bytes() != source.read_bytes():
        shutil.copy2(source, destination)
    return destination


def verify_wave(manifest: dict[str, Any], datasets: dict[str, list[dict[str, str]]]) -> list[str]:
    checks = {
        "buyer_unit_targets": len(datasets["buyer_unit_targets"]),
        "product_opportunities": len(datasets["product_opportunities"]),
        "enrichment_queue": len(datasets["contact_enrichment_queue"]),
        "current_public_routes": len(datasets["current_public_routes"]),
    }
    errors = []
    for key, actual in checks.items():
        expected = int_value(manifest.get(key), -1)
        if expected != actual:
            errors.append(f"{key}: manifest={expected}, archive={actual}")
    return errors


def write_wave_lineage(output_root: Path, active_archive: Path) -> list[dict[str, Any]]:
    lineage = []
    for archive_path in sorted(ROOT.glob("DIO_Prospect_Intelligence_Wave*.zip")):
        archive = WaveArchive(archive_path)
        try:
            manifest = archive.json("manifest.json")
        finally:
            archive.close()
        summary = manifest.get("summary", {})
        lineage.append(
            {
                "archive": archive_path.name,
                "archive_sha256": sha256(archive_path),
                "schema": manifest.get("schema"),
                "created_at": manifest.get("created_at") or manifest.get("built_at"),
                "active": archive_path.resolve() == active_archive.resolve(),
                "counts": {
                    "prospects": manifest.get("master_prospects") or manifest.get("prospects") or summary.get("total_prospects"),
                    "product_opportunities": manifest.get("product_opportunities"),
                    "buyer_unit_targets": manifest.get("buyer_unit_targets"),
                    "electronic_sales_allowed": manifest.get("electronic_sales_allowed", manifest.get("permitted_product_outreach")),
                },
            }
        )
    write_json(
        output_root / "REGISTRY_WAVE_LINEAGE.json",
        {"schema": "dio.registry_wave_lineage.v1", "generated_at": utc_now(), "waves": lineage},
    )
    return lineage


def target_index(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {(row["prospect_id"], row["product_line_id"]): row for row in rows}


def choose_hypothesis(
    product_line_id: str,
    hypotheses: list[dict[str, str]],
    targets: dict[tuple[str, str], dict[str, str]],
    product_config: dict[str, Any],
    route_priority: dict[str, int],
) -> tuple[dict[str, str], dict[str, str]]:
    candidates = []
    preferred = set(product_config.get("preferred_route_states") or [])
    registry_product_line_id = product_config.get("registry_product_line_id") or product_line_id
    for hypothesis in hypotheses:
        if hypothesis.get("product_line_id") != registry_product_line_id:
            continue
        target = targets.get((hypothesis.get("prospect_id", ""), registry_product_line_id), {})
        route_state = target.get("route_state") or "RESEARCH_ONLY"
        candidates.append(
            (
                1 if route_state in preferred else 0,
                int(route_priority.get(route_state, 0)),
                float_value(hypothesis.get("attack_score")),
                -int_value(hypothesis.get("rank"), 99999),
                hypothesis,
                target,
            )
        )
    if not candidates:
        raise ValueError(f"No campaign hypothesis found for {product_line_id}")
    _, _, _, _, hypothesis, target = max(candidates, key=lambda item: item[:4])
    return hypothesis, target


def outreach_allowed(target: dict[str, str], config: dict[str, Any]) -> bool:
    allowed = set(config["governance"]["electronic_outreach_allowed_states"])
    return (
        target.get("outreach_state") == "Sales outreach allowed"
        and target.get("consent_status") in allowed
        and target.get("do_not_contact") != "Yes"
    )


def route_mode(target: dict[str, str]) -> str:
    state = target.get("route_state") or "RESEARCH_ONLY"
    if state == "SELF_SERVE_AVAILABLE":
        return "self_serve_listing"
    if state == "CHANNEL_SUBMISSION_AVAILABLE":
        return "reviewed_channel_submission"
    if state == "PARTNERSHIP_ROUTE_AVAILABLE":
        return "operator_reviewed_partnership_request"
    if state == "INSTITUTIONAL_ROUTE_AVAILABLE":
        return "operator_reviewed_institutional_request"
    return "public_proof_content_only"


def build_observation(
    archive_path: Path,
    archive_hash: str,
    hypothesis: dict[str, str],
    target: dict[str, str],
) -> dict[str, Any]:
    observation_id = stable_id("OBS", ["wave4", hypothesis["hypothesis_id"], archive_hash])
    return {
        "schema": "dio.market_observation.v1",
        "observation_id": observation_id,
        "observed_at": target.get("contact_verified_date") or "2026-08-08",
        "recorded_at": utc_now(),
        "source": {
            "kind": "prospect_registry_wave",
            "wave": "wave4",
            "archive": str(archive_path),
            "archive_sha256": archive_hash,
            "registry_hypothesis_id": hypothesis["hypothesis_id"],
            "target_id": target.get("target_id"),
            "source_reference": target.get("contact_source"),
        },
        "product_line_id": hypothesis["product_line_id"],
        "market": {
            "organisation": hypothesis.get("organisation"),
            "segment": target.get("segment"),
            "province_or_reach": target.get("province_or_reach"),
            "buyer_unit": hypothesis.get("buyer_unit"),
        },
        "signals": {
            "attack_score": float_value(hypothesis.get("attack_score")),
            "route_state": target.get("route_state") or "RESEARCH_ONLY",
            "route_mode": route_mode(target),
            "proof_readiness_score": float_value(target.get("proof_readiness_score")),
            "timing_score": float_value(target.get("timing_score")),
            "seasonal_urgency": target.get("seasonal_urgency"),
            "seasonal_trigger": target.get("seasonal_trigger"),
        },
        "controls": {
            "outreach_state": target.get("outreach_state") or "Research only",
            "consent_status": target.get("consent_status") or "Not recorded",
            "do_not_contact": target.get("do_not_contact") or "No",
            "high_score_is_permission": False,
        },
    }


def build_hypothesis_record(
    config: dict[str, Any],
    archive_hash: str,
    hypothesis: dict[str, str],
    target: dict[str, str],
    product: dict[str, Any],
    observation: dict[str, Any],
) -> dict[str, Any]:
    product_layer = product["product_layer"]
    campaign_id = stable_id("CMP", ["wave4", hypothesis["hypothesis_id"], product_layer])
    direct_allowed = outreach_allowed(target, config)
    return {
        "schema": "dio.hivenance.marketing_hypothesis.v1",
        "hypothesis_id": hypothesis["hypothesis_id"],
        "campaign_id": campaign_id,
        "registered_at": utc_now(),
        "registered_by": "dio_registry_hivenance_bridge",
        "immutable": True,
        "source": {
            "registry_wave": "wave4",
            "registry_hypothesis_id": hypothesis["hypothesis_id"],
            "target_id": target.get("target_id"),
            "observation_id": observation["observation_id"],
            "archive_sha256": archive_hash,
        },
        "product": {
            "product_line_id": hypothesis["product_line_id"],
            "product_layer": product_layer,
            "public_name": product["public_name"],
            "offer_id": product["offer_id"],
        },
        "audience": {
            "public_segment": product["generic_audience"],
            "internal_research_organisation": hypothesis.get("organisation"),
            "internal_buyer_unit": hypothesis.get("buyer_unit"),
            "personalisation_allowed": direct_allowed,
        },
        "hypothesis": hypothesis["hypothesis"],
        "experiment": {
            "mode": route_mode(target),
            "channel": hypothesis.get("primary_channel"),
            "proof_asset": product["proof_pointer"],
            "proof_summary": product["proof_summary"],
            "public_hook": product["public_hook"],
            "cta": product["public_cta"],
            "success_event": hypothesis.get("success_event") or "qualified_pilot_conversation",
            "kill_condition": hypothesis.get("kill_condition"),
            "window_days": int(config["default_experiment_window_days"]),
            "budget_cap_minor": int(config["default_paid_budget_cap_minor"]),
            "currency": config["currency"],
        },
        "gates": {
            "content_generation": "allowed",
            "publication": "operator_approval_required",
            "personalised_outreach": "allowed" if direct_allowed else "blocked",
            "electronic_sales_outreach": "allowed" if direct_allowed else "blocked",
            "registry_outreach_gate": hypothesis.get("outreach_gate"),
            "reason": (
                "Registry records a valid outreach permission basis."
                if direct_allowed
                else "Research and proof-content generation are allowed; no valid electronic sales permission is recorded."
            ),
        },
        "settlement": {
            "state": "unstarted",
            "decision": "pending",
            "measurement_path": "measurement.json",
            "decision_path": "HIVENANCE_SETTLEMENT.json",
        },
    }


def write_immutable(path: Path, record: dict[str, Any]) -> str:
    if not path.exists():
        write_json(path, record)
        return "registered"
    existing = load_json(path)
    stable_keys = ["schema", "hypothesis_id", "campaign_id", "source", "product", "audience", "hypothesis", "experiment", "gates"]
    if any(existing.get(key) != record.get(key) for key in stable_keys):
        raise RuntimeError(f"Immutable hypothesis collision at {path}")
    return "already_registered"


def sync_hivenance_marketing_register(
    config: dict[str, Any],
    output_root: Path,
    campaigns: list[dict[str, Any]],
) -> dict[str, Any]:
    hivenance_root = Path(config["hivenance_root"]).resolve()
    if not (hivenance_root / "scripts" / "register_hypothesis.py").exists():
        raise FileNotFoundError(f"Configured Hivenance root is not valid: {hivenance_root}")
    register_dir = hivenance_root / "data" / "hypothesis_registry" / "marketing"
    register_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for item in campaigns:
        record = item["record"]
        destination = register_dir / f"{record['hypothesis_id']}.json"
        state = write_immutable(destination, record)
        records.append(
            {
                "hypothesis_id": record["hypothesis_id"],
                "campaign_id": record["campaign_id"],
                "state": state,
                "path": str(destination),
                "sha256": sha256(destination),
            }
        )
    receipt = {
        "schema": "dio.hivenance.marketing_register_bridge.v1",
        "synced_at": utc_now(),
        "source_root": str(ROOT),
        "source_output": str(output_root),
        "hivenance_root": str(hivenance_root),
        "register_namespace": "marketing",
        "trading_execution_connected": False,
        "records": records,
    }
    write_json(register_dir / "DIO_MARKETING_BRIDGE_RECEIPT.json", receipt)
    write_json(output_root / "HIVENANCE_REGISTER_SYNC.json", receipt)
    return receipt


def build_foundry_opportunity(record: dict[str, Any]) -> dict[str, Any]:
    experiment = record["experiment"]
    product = record["product"]
    route_risk = 0.2 if experiment["mode"] in {"self_serve_listing", "reviewed_channel_submission"} else 0.42
    return {
        "title": f"{product['public_name']}: proof before promises",
        "topic": f"{product['public_name']} proof-led pilot campaign for {record['audience']['public_segment']}",
        "angle": f"{experiment['public_hook']} Show the real proof artifact, the human approval boundary and the bounded pilot offer.",
        "viewer_job": f"decide whether {product['public_name']} can solve this workflow pain without surrendering professional control",
        "source_hints": [
            experiment["proof_asset"],
            f"DIO immutable hypothesis {record['hypothesis_id']}",
            "DIO Prospect Intelligence Wave 4",
        ],
        "series_hint": "Proof-bearing workflow services for South African education and evidence teams",
        "content_role": "commercial_intent",
        "signals": {
            "series_potential": 0.72,
            "visual_potential": 0.9 if product["product_layer"] == "homs" else 0.78,
            "monetization_alignment": 0.88,
            "evidence_availability": 0.95,
            "production_burden": 0.2,
            "policy_risk": route_risk,
            "freshness_risk": 0.08,
        },
        "operator_notes": (
            f"Generated from campaign {record['campaign_id']}. Contact details and named-target personalisation are intentionally excluded. "
            f"Publication gate: {record['gates']['publication']}; outreach gate: {record['gates']['electronic_sales_outreach']}."
        ),
    }


def build_storyboard(record: dict[str, Any], layer: dict[str, Any], studio_id: str) -> dict[str, Any]:
    product = record["product"]
    experiment = record["experiment"]
    campaign_id = record["campaign_id"]
    scenes = [
        ("hook", 7, experiment["public_hook"], product["public_name"], "Open on the real finished proof, not an abstract AI graphic."),
        ("pain", 10, layer["pain"], "The actual workload", "Show the source mess or assessment-production burden with realistic work objects."),
        ("proof", 14, experiment["proof_summary"], "Inspect the proof", "Move through legible excerpts from the existing proof asset."),
        ("workflow", 12, layer["promise"], "Input -> review -> delivery", "Show the controlled workflow and its receipts."),
        ("boundary", 9, layer["risk_boundary"], "Human authority remains", "Show the explicit operator or educator approval gate."),
        ("cta", 8, experiment["cta"], layer["offer"], "End on one bounded action and the proof landing page."),
    ]
    return {
        "schema": "knowedge.phase3.storyboard.v1",
        "episode_id": f"{slug(product['product_layer'])}-{campaign_id.lower()}",
        "campaign_id": campaign_id,
        "hypothesis_id": record["hypothesis_id"],
        "studio_id": studio_id,
        "product_layer": product["product_layer"],
        "created_at": utc_now(),
        "target_runtime_seconds": sum(item[1] for item in scenes),
        "scenes": [
            {
                "scene_id": f"scene_{index:02d}",
                "role": role,
                "duration_seconds": duration,
                "narration": narration,
                "screen_text": screen,
                "visual": visual,
            }
            for index, (role, duration, narration, screen, visual) in enumerate(scenes, start=1)
        ],
        "approval_required": True,
    }


def build_visual_plan(record: dict[str, Any], storyboard: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "knowedge.phase3.visual_plan.v1",
        "campaign_id": record["campaign_id"],
        "episode_id": storyboard["episode_id"],
        "studio_id": storyboard["studio_id"],
        "visual_identity": {
            "motif": "real proof under inspection",
            "palette": {"paper": "#F7F8F6", "ink": "#18212B", "blue": "#225C7A", "green": "#1F6B3A", "gold": "#D4A23A"},
            "rules": [
                "Use actual proof artifacts or faithful close-ups.",
                "Keep text legible at phone size.",
                "Do not use generic AI imagery or slide-template decoration.",
                "Do not expose prospect names, contact details or private data."
            ],
        },
        "thumbnail": {
            "headline": record["product"]["public_name"],
            "subline": "Proof before promises",
            "composition": "one striking real artifact with a clear before-to-after signal",
        },
        "scene_visuals": [
            {"scene_id": scene["scene_id"], "objective": scene["visual"], "safe_area": "caption-safe lower third"}
            for scene in storyboard["scenes"]
        ],
    }


def attributed_url(record: dict[str, Any], product: dict[str, Any]) -> str:
    params = {
        "utm_source": "nichefoundry",
        "utm_medium": "proof_content",
        "utm_campaign": record["campaign_id"].lower(),
        "utm_content": f"{record['product']['product_layer']}-proof-before-promises",
        "campaign_id": record["campaign_id"],
        "offer_id": record["product"]["offer_id"],
    }
    return f"{product['landing_page']}?{urllib.parse.urlencode(params)}"


def build_metadata(record: dict[str, Any], product: dict[str, Any], storyboard: dict[str, Any]) -> dict[str, Any]:
    title = f"{record['product']['public_name']}: proof before promises"
    return {
        "schema": "nichefoundry.youtube_metadata.v1",
        "campaign_id": record["campaign_id"],
        "episode_id": storyboard["episode_id"],
        "snippet": {
            "title": title[:100],
            "description": (
                f"{record['experiment']['public_hook']}\n\n"
                f"Proof: {record['experiment']['proof_summary']}\n\n"
                f"{record['experiment']['cta']}\n"
                f"{attributed_url(record, product)}\n\n"
                "Human approval remains required. This campaign contains no customer testimonial or guaranteed outcome."
            ),
            "tags": ["KnowEdge", "DIO", record["product"]["product_layer"], "workflow automation", "human review"],
            "categoryId": "27",
            "defaultLanguage": "en",
        },
        "status": {"privacyStatus": "private", "containsSyntheticMedia": True, "embeddable": True},
    }


def build_editorial(record: dict[str, Any], storyboard: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "knowedge.phase3.editorial_review.v1",
        "campaign_id": record["campaign_id"],
        "episode_id": storyboard["episode_id"],
        "created_at": utc_now(),
        "status": "operator_review_required",
        "blocking_rules": [
            "No publication before PHASE3_APPROVAL.json records operator approval.",
            "No prospect name or contact detail in public creative.",
            "No direct electronic sales outreach while the registry gate is blocked.",
            "No fake metrics, testimonials, endorsements or guaranteed outcomes.",
            "The human approval boundary must remain visible.",
        ],
        "review_files": ["CAMPAIGN_PACK.md", "storyboard.json", "visual_plan.json", "metadata_package.json", "foundry_opportunity.json"],
    }


def measurement_template(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "dio.marketing.measurement.v1",
        "campaign_id": record["campaign_id"],
        "measurement_window": {"started_at": None, "ended_at": None},
        "acquisition": {"impressions": 0, "views": 0, "clicks": 0, "landing_visits": 0},
        "leads": {"enquiries": 0, "qualified_leads": 0, "quotes": 0},
        "commerce": {"orders": 0, "paid_orders": 0, "revenue_minor": 0, "refunds_minor": 0},
        "fulfilment": {"completed": 0, "delivered": 0, "manual_minutes": 0, "revisions": 0},
        "economics": {"ad_spend_minor": 0, "payment_fees_minor": 0, "external_cost_minor": 0, "manual_labour_minor": 0, "gross_contribution_minor": 0},
        "governance": {"outreach_attempts": 0, "blocked_outreach_attempts": 0, "permission_failures": 0, "publication_approved": False, "unresolved_incidents": 0},
    }


def campaign_markdown(record: dict[str, Any], target: dict[str, str], product: dict[str, Any]) -> str:
    direct = record["gates"]["electronic_sales_outreach"]
    return f"""# DIO Campaign: {record['product']['public_name']}

Campaign: `{record['campaign_id']}`  
Hypothesis: `{record['hypothesis_id']}`  
Status: hypothesis registered; operator review required

## Hivenance Hypothesis

{record['hypothesis']}

## Public Campaign

Audience: {record['audience']['public_segment']}

Hook: {record['experiment']['public_hook']}

Proof: {record['experiment']['proof_summary']}

CTA: {record['experiment']['cta']}

Attributed destination: `{attributed_url(record, product)}`

## Internal Route Evidence

- Research organisation: {record['audience']['internal_research_organisation']}
- Buyer unit: {record['audience']['internal_buyer_unit']}
- Route state: {target.get('route_state') or 'RESEARCH_ONLY'}
- Experiment mode: {record['experiment']['mode']}
- Attack score: {target.get('attack_score') or 'not supplied'}

The named organisation is market evidence, not public creative copy unless a later operator approval explicitly authorises that use.

## Gates

- Content generation: **{record['gates']['content_generation']}**
- Publication: **{record['gates']['publication']}**
- Personalised outreach: **{record['gates']['personalised_outreach']}**
- Electronic sales outreach: **{direct}**

## Measurement

- Success event: `{record['experiment']['success_event']}`
- Window: {record['experiment']['window_days']} days
- Paid budget cap: {record['experiment']['budget_cap_minor']} minor units
- Kill condition: {record['experiment']['kill_condition']}

## Next Gate

Review the creative pack. Approval permits production or channel submission only. It does not override the outreach permission gate.
"""


def write_campaign(
    output_root: Path,
    config: dict[str, Any],
    record: dict[str, Any],
    observation: dict[str, Any],
    target: dict[str, str],
    product: dict[str, Any],
    layer: dict[str, Any],
) -> Path:
    campaign_dir = output_root / "campaigns" / f"{record['product']['product_layer']}-{record['campaign_id'].lower()}"
    campaign_dir.mkdir(parents=True, exist_ok=True)
    opportunity = build_foundry_opportunity(record)
    storyboard = build_storyboard(record, layer, config["nichefoundry_studio"])
    visual_plan = build_visual_plan(record, storyboard)
    metadata = build_metadata(record, product, storyboard)
    editorial = build_editorial(record, storyboard)
    measurement = measurement_template(record)
    request = {
        "schema": "dio.nichefoundry.marketing_campaign_request.v1",
        "created_at": utc_now(),
        "campaign_id": record["campaign_id"],
        "hypothesis_id": record["hypothesis_id"],
        "nichefoundry_root": config["nichefoundry_root"],
        "studio_id": config["nichefoundry_studio"],
        "opportunity": opportunity,
        "requested_outputs": ["short_video", "linkedin_post", "proof_article", "landing_page_variant", "thumbnail"],
        "approval_required": True,
        "contact_data_exported": False,
    }
    gate = {
        "schema": "dio.hivenance.marketing_gate.v1",
        "campaign_id": record["campaign_id"],
        "hypothesis_id": record["hypothesis_id"],
        "evaluated_at": utc_now(),
        "state": "creative_review_ready",
        "gates": record["gates"],
        "next_allowed_action": "operator_editorial_review",
        "blocked_actions": ["automatic_publication", "automatic_direct_message", "automatic_sales_email"],
    }
    files = {
        "MARKET_OBSERVATION.json": observation,
        "HIVENANCE_HYPOTHESIS.json": record,
        "HIVENANCE_GATE.json": gate,
        "foundry_opportunity.json": opportunity,
        "foundry_campaign_request.json": request,
        "storyboard.json": storyboard,
        "visual_plan.json": visual_plan,
        "metadata_package.json": metadata,
        "editorial_review.json": editorial,
        "measurement.json": measurement,
    }
    for name, payload in files.items():
        if name == "measurement.json":
            write_json_if_missing(campaign_dir / name, payload)
        else:
            write_json(campaign_dir / name, payload)
    (campaign_dir / "CAMPAIGN_PACK.md").write_text(campaign_markdown(record, target, product), encoding="utf-8")
    receipt = {
        "schema": "dio.marketing.integration_receipt.v1",
        "campaign_id": record["campaign_id"],
        "hypothesis_id": record["hypothesis_id"],
        "product_layer": record["product"]["product_layer"],
        "created_at": utc_now(),
        "status": "hypothesis_registered_campaign_review_ready",
        "files": sorted([*files.keys(), "CAMPAIGN_PACK.md"]),
        "nichefoundry_scored": False,
        "next_gate": "operator approval before production, publication or channel submission",
    }
    write_json(campaign_dir / "MARKETING_INTEGRATION_RECEIPT.json", receipt)
    write_json(
        campaign_dir / "PHASE3_RECEIPT.json",
        {
            "product_layer": record["product"]["product_layer"],
            "campaign_id": record["campaign_id"],
            "hypothesis_id": record["hypothesis_id"],
            "created_at": utc_now(),
            "status": "campaign_pending",
            "files": sorted([*files.keys(), "CAMPAIGN_PACK.md", "MARKETING_INTEGRATION_RECEIPT.json"]),
            "next_gate": "operator editorial approval before media generation",
        },
    )
    return campaign_dir


def score_with_nichefoundry(campaign_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
    score_path = campaign_dir / "NICHEFOUNDRY_SCORE.json"
    command = [
        "node",
        str(ROOT / "scripts" / "score_nichefoundry_opportunity.js"),
        str(campaign_dir / "foundry_opportunity.json"),
        str(score_path),
        config["nichefoundry_studio"],
        config["nichefoundry_root"],
    ]
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    score = load_json(score_path)
    integration_receipt_path = campaign_dir / "MARKETING_INTEGRATION_RECEIPT.json"
    integration_receipt = load_json(integration_receipt_path)
    receipt_files = set(integration_receipt.get("files", []))
    receipt_files.add(score_path.name)
    integration_receipt.update(
        {
            "files": sorted(receipt_files),
            "nichefoundry_scored": True,
            "nichefoundry_score_path": score_path.name,
            "nichefoundry_decision": score["result"]["decision"],
            "nichefoundry_opportunity_score": score["result"]["opportunity_score"],
            "nichefoundry_fit_passed": score["result"]["studio_fit_passed"],
        }
    )
    write_json(integration_receipt_path, integration_receipt)
    phase_receipt_path = campaign_dir / "PHASE3_RECEIPT.json"
    phase_receipt = load_json(phase_receipt_path)
    phase_files = set(phase_receipt.get("files", []))
    phase_files.add(score_path.name)
    phase_receipt.update(
        {
            "files": sorted(phase_files),
            "nichefoundry_decision": score["result"]["decision"],
            "nichefoundry_opportunity_score": score["result"]["opportunity_score"],
            "nichefoundry_fit_passed": score["result"]["studio_fit_passed"],
        }
    )
    write_json(phase_receipt_path, phase_receipt)
    return {"path": str(score_path), **score["result"], "engine_output": completed.stdout.strip()}


def write_index(output_root: Path, campaigns: list[dict[str, Any]], import_receipt: dict[str, Any]) -> None:
    rows = []
    for item in campaigns:
        record = item["record"]
        target = item["target"]
        campaign_dir = item["campaign_dir"]
        rows.append(
            f"| [{record['product']['public_name']}](campaigns/{campaign_dir.name}/CAMPAIGN_PACK.md) | `{record['campaign_id']}` | "
            f"{record['audience']['internal_research_organisation']} | {target.get('route_state') or 'RESEARCH_ONLY'} | "
            f"{item['foundry_score']['opportunity_score']} / {item['foundry_score']['decision']} | "
            f"{record['gates']['publication']} | {record['gates']['electronic_sales_outreach']} |"
        )
    text = "\n".join(
        [
            "# DIO Wave 4 Marketing Integration",
            "",
            f"Generated: {import_receipt['created_at']}",
            "",
            "Wave 4 is the active market snapshot. Waves 2 and 3 remain source lineage.",
            "",
            "| Campaign | ID | Internal market evidence | Route | NicheFoundry | Publication | Direct outreach |",
            "|---|---|---|---|---|---|---|",
            *rows,
            "",
            "## Control",
            "",
            "These campaigns are approved for operator review only. No electronic sales outreach is authorised by this integration run.",
            "",
            "## Next",
            "",
            "1. Inspect each campaign pack and NicheFoundry score.",
            "2. Approve, revise or reject the public creative.",
            "3. Produce only the approved proof asset or reviewed channel submission.",
            "4. Populate `measurement.json` after publication or channel use.",
            "5. Run the Hivenance settlement command to decide promote, continue, revise or kill.",
        ]
    )
    (output_root / "DIO_MARKETING_INDEX.md").write_text(text + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Bridge a DIO prospect registry wave into Hivenance hypotheses and NicheFoundry campaign packs.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--archive", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    config = load_json(args.config.resolve())
    installed_studio = install_nichefoundry_studio(config)
    archive_path = (args.archive or (ROOT / config["active_registry_archive"])).resolve()
    output_root = (args.out or (ROOT / config["output_root"])).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    archive_hash = sha256(archive_path)
    wave_lineage = write_wave_lineage(output_root, archive_path)
    wave = WaveArchive(archive_path)
    try:
        manifest = wave.json("manifest.json")
        datasets = {
            name: wave.csv(f"{name}.csv")
            for name in [
                "buyer_unit_targets",
                "campaign_hypotheses",
                "contact_enrichment_queue",
                "current_public_routes",
                "product_opportunities",
                "proof_asset_matrix",
            ]
        }
    finally:
        wave.close()

    errors = verify_wave(manifest, datasets)
    if errors:
        raise RuntimeError("Registry wave validation failed: " + "; ".join(errors))
    targets = target_index(datasets["buyer_unit_targets"])
    layers = product_layers()
    registry_dir = output_root / "hivenance_registry"
    registry_dir.mkdir(parents=True, exist_ok=True)
    campaigns = []
    registration_states = []
    for product_line_id in config["active_product_lines"]:
        product = config["product_lines"][product_line_id]
        hypothesis, target = choose_hypothesis(
            product_line_id,
            datasets["campaign_hypotheses"],
            targets,
            product,
            config["route_priority"],
        )
        observation = build_observation(archive_path, archive_hash, hypothesis, target)
        record = build_hypothesis_record(config, archive_hash, hypothesis, target, product, observation)
        registration_path = registry_dir / f"{record['hypothesis_id']}.json"
        if registration_path.exists():
            existing = load_json(registration_path)
            if existing.get("hypothesis_id") != record.get("hypothesis_id") or existing.get("campaign_id") != record.get("campaign_id"):
                raise RuntimeError(f"Immutable hypothesis identity collision at {registration_path}")
            record = existing
            registration_state = "already_registered"
        else:
            registration_state = write_immutable(registration_path, record)
        campaign_dir = write_campaign(output_root, config, record, observation, target, product, layers[product["product_layer"]])
        foundry_score = score_with_nichefoundry(campaign_dir, config)
        campaigns.append({"record": record, "target": target, "campaign_dir": campaign_dir, "foundry_score": foundry_score})
        registration_states.append({"hypothesis_id": record["hypothesis_id"], "state": registration_state})

    hivenance_sync = sync_hivenance_marketing_register(config, output_root, campaigns)

    receipt = {
        "schema": "dio.registry_wave_import_receipt.v1",
        "created_at": utc_now(),
        "status": "completed",
        "registry_wave": config["active_registry_wave"],
        "archive": str(archive_path),
        "archive_sha256": archive_hash,
        "installed_nichefoundry_studio": str(installed_studio),
        "wave_lineage": wave_lineage,
        "manifest": manifest,
        "validated_counts": {name: len(rows) for name, rows in datasets.items()},
        "selected_campaigns": [item["record"]["campaign_id"] for item in campaigns],
        "nichefoundry_scores": {
            item["record"]["campaign_id"]: {
                "decision": item["foundry_score"]["decision"],
                "opportunity_score": item["foundry_score"]["opportunity_score"],
                "studio_fit_passed": item["foundry_score"]["studio_fit_passed"],
            }
            for item in campaigns
        },
        "hivenance_register_sync": hivenance_sync,
        "registrations": registration_states,
        "electronic_sales_outreach_authorised": 0,
    }
    write_json(output_root / "REGISTRY_IMPORT_RECEIPT.json", receipt)
    write_index(output_root, campaigns, receipt)
    print(json.dumps({"status": "completed", "out": str(output_root), "campaigns": receipt["selected_campaigns"], "registrations": registration_states}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
