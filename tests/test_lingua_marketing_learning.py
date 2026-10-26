from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from adapters.lingua.lifecycle import register_product_source
from scripts import build_lingua_hustle_campaign_factory as lingua_factory
from scripts import lingua_marketing_learning as learning


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def market_object(root: Path, *, object_id: str, campaign_id: str, content_id: str, hook: str = "Stop rebuilding the evidence trail") -> None:
    register_product_source(
        state_root=root,
        object_id=object_id,
        source_version="1.0.0",
        source_language="English",
        source_rows=[
            {"unit_id": "HOOK", "unit_type": "hook", "text": hook},
            {"unit_id": "BODY", "unit_type": "campaign_body", "text": "One bounded proof-backed pilot with human review."},
        ],
        origin={
            "product": "market",
            "artifact_type": "multichannel_campaign_family",
            "artifact_id": content_id,
            "campaign_id": campaign_id,
            "product_line_id": "EVIDEX_PACK",
            "audience": "Compliance and audit teams",
            "channel": "facebook_page",
            "cta": "Start one bounded pilot",
            "privacy_domain": "public_marketing",
        },
        domain="Professional services marketing",
    )


def make_db(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE channel_snapshots(
          snapshot_id TEXT PRIMARY KEY, channel_id TEXT, campaign_id TEXT,
          impressions INTEGER, reach INTEGER, views INTEGER, clicks INTEGER,
          conversions REAL, spend_minor INTEGER, evidence_grade TEXT,
          source_mode TEXT, raw_json TEXT
        );
        CREATE TABLE attribution_events(
          attribution_id TEXT PRIMARY KEY, campaign_id TEXT, channel_id TEXT,
          content_id TEXT, event_type TEXT, value_minor INTEGER,
          source TEXT, metadata_json TEXT
        );
        CREATE TABLE content_items(content_id TEXT PRIMARY KEY, campaign_id TEXT);
        """
    )
    return con


def test_register_channel_semantics_captures_sales_meaning_without_release_authority():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "lingua"
        family = {
            "family_id": "EVIDEX_PACK--compliance_audit",
            "product": {"id": "EVIDEX_PACK", "offer": "evidence_pack"},
            "audience": {"id": "compliance_audit", "name": "Compliance and audit teams"},
        }
        payload = {
            "commercial_strategy": {
                "buyer_pain": "Review preparation consumes hours of manual searching.",
                "desired_outcome": "A bounded evidence index with gaps visible before review.",
                "offer": {"price_label": "R 7,900 ZAR", "scope": "one bounded case", "launch_price_zar": 7900},
                "proof_angle": "A controlled route leaves inspectable evidence.",
                "commercial_family": "Evidence & Assurance",
                "truth_boundaries": ["Human authority remains with the reviewer."],
            },
            "copy": {
                "headline": "Stop rebuilding the audit trail",
                "body": "Start with one bounded case.",
                "objection": "Is this a black box?",
                "objection_answer": "No. Proof remains inspectable.",
                "cta": "Start one bounded pilot",
                "funnel_stage": "conversion",
            },
        }
        result = learning.register_channel_semantics(
            family=family,
            channel_id="META_ADS",
            channel_payload=payload,
            state_root=root,
        )
        semantic = json.loads((root / "objects" / f"{result['semantic_object_id']}.json").read_text())
        ids = {row["unit_id"] for row in semantic["source"]["units"]}
        assert ids == {"HOOK", "PAIN", "OUTCOME", "BODY", "OFFER", "PROOF", "OBJECTION", "CTA", "BOUNDARY"}
        assert semantic["authority"]["machine_drafts_reusable"] is False
        assert semantic["authority"]["human_approval_required"] is True


def test_simulated_market_evidence_is_not_learned():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        lingua = root / "lingua"
        db = root / "market.sqlite"
        market_object(lingua, object_id="MARKET-SIM", campaign_id="C-SIM", content_id="CNT-SIM")
        con = make_db(db)
        con.execute("INSERT INTO content_items VALUES(?,?)", ("CNT-SIM", "C-SIM"))
        con.execute(
            "INSERT INTO channel_snapshots VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            ("S1", "FACEBOOK_PAGE", "C-SIM", 5000, 4000, 0, 500, 10, 0, "estimated", "manual_import", json.dumps({"simulated": True})),
        )
        con.execute(
            "INSERT INTO attribution_events VALUES(?,?,?,?,?,?,?,?)",
            ("A1", "C-SIM", "FACEBOOK_PAGE", "CNT-SIM", "lead.qualified", 0, "simulated_demo", json.dumps({"simulated": True})),
        )
        con.commit(); con.close()
        result = learning.observe_market_outcomes(db_path=db, lingua_root=lingua, learning_root=root / "learning")
        assert result["candidates"] == 0
        assert result["positive_candidates"] == 0


def test_real_single_content_outcome_creates_positive_candidate_but_not_reuse_authority():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        lingua = root / "lingua"
        learning_root = root / "learning"
        db = root / "market.sqlite"
        market_object(lingua, object_id="MARKET-REAL", campaign_id="C-REAL", content_id="CNT-REAL")
        con = make_db(db)
        con.execute("INSERT INTO content_items VALUES(?,?)", ("CNT-REAL", "C-REAL"))
        con.execute(
            "INSERT INTO channel_snapshots VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            ("S1", "FACEBOOK_PAGE", "C-REAL", 1800, 1600, 0, 54, 0, 0, "platform_api", "api", "{}"),
        )
        con.execute(
            "INSERT INTO attribution_events VALUES(?,?,?,?,?,?,?,?)",
            ("A1", "C-REAL", "FACEBOOK_PAGE", "CNT-REAL", "lead.qualified", 0, "edge_gateway", "{}"),
        )
        con.execute(
            "INSERT INTO attribution_events VALUES(?,?,?,?,?,?,?,?)",
            ("A2", "C-REAL", "FACEBOOK_PAGE", "CNT-REAL", "lead.qualified", 0, "edge_gateway", "{}"),
        )
        con.commit(); con.close()
        result = learning.observe_market_outcomes(db_path=db, lingua_root=lingua, learning_root=learning_root)
        assert result["positive_candidates"] == 1
        candidate = json.loads(next((learning_root / "candidates").glob("*.json")).read_text())
        assert candidate["state"] == "operator_approval_required"
        assert candidate["authority"]["draft_reuse"] is False
        assert candidate["authority"]["publication"] is False
        assert candidate["authority"]["spend"] is False


def test_multi_content_campaign_outcome_does_not_launder_credit_to_one_hook():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        lingua = root / "lingua"
        learning_root = root / "learning"
        db = root / "market.sqlite"
        market_object(lingua, object_id="MARKET-MULTI", campaign_id="C-MULTI", content_id="CNT-ONE")
        con = make_db(db)
        con.execute("INSERT INTO content_items VALUES(?,?)", ("CNT-ONE", "C-MULTI"))
        con.execute("INSERT INTO content_items VALUES(?,?)", ("CNT-TWO", "C-MULTI"))
        con.execute(
            "INSERT INTO channel_snapshots VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            ("S1", "FACEBOOK_PAGE", "C-MULTI", 3000, 2500, 0, 120, 0, 0, "platform_api", "api", "{}"),
        )
        con.execute(
            "INSERT INTO attribution_events VALUES(?,?,?,?,?,?,?,?)",
            ("A1", "C-MULTI", "FACEBOOK_PAGE", None, "lead.qualified", 0, "edge_gateway", "{}"),
        )
        con.execute(
            "INSERT INTO attribution_events VALUES(?,?,?,?,?,?,?,?)",
            ("A2", "C-MULTI", "FACEBOOK_PAGE", None, "lead.qualified", 0, "edge_gateway", "{}"),
        )
        con.commit(); con.close()
        result = learning.observe_market_outcomes(db_path=db, lingua_root=lingua, learning_root=learning_root)
        assert result["candidates"] == 0


def test_positive_pattern_requires_operator_then_only_reorders_held_draft():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        candidate_id = "MKTLEARN-TESTPOSITIVE"
        candidate = {
            "schema": "dio.lingua.commercial_learning_candidate.v1",
            "candidate_id": candidate_id,
            "state": "operator_approval_required",
            "direction": "positive",
            "confidence": 0.88,
            "scope": {"product_line_id": "EVIDEX_PACK", "audience": "Compliance and audit teams", "channel": "META_ADS"},
            "pattern": {"hook": "Stop rebuilding the evidence trail", "body": "Proof-backed body", "cta": "Start one pilot", "hook_fingerprint": "sha256:test"},
            "evidence": {"qualified_leads": 2, "clicks": 54, "exposure": 1800},
        }
        write_json(root / "candidates" / f"{candidate_id}.json", candidate)
        pattern = learning.approve_candidate(candidate_id, approved_by="operator", reason="Two qualified leads on content-attributed evidence", learning_root=root, crystallize=False)
        assert pattern["authority"]["draft_reuse"] is True
        assert pattern["authority"]["publication"] is False
        assert pattern["authority"]["direct_learning_to_execution"] is False
        baseline = {"hooks": ["Old hook", "Another hook"]}
        learned = learning.apply_strategy_learning(baseline, product_id="EVIDEX_PACK", audience="Compliance and audit teams", channel_id="META_ADS", learning_root=root)
        assert learned["hooks"][0] == "Stop rebuilding the evidence trail"
        assert learned["lingua_learning"]["draft_reuse_only"] is True
        assert learned["lingua_learning"]["external_action"] is False


def test_negative_pattern_activates_only_after_repetition():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        base = {
            "direction": "negative",
            "scope": {"product_line_id": "EVIDEX_PACK", "audience": "Compliance and audit teams", "channel": "META_ADS"},
            "pattern": {"hook_fingerprint": "sha256:weak-hook"},
        }
        states = []
        for index in range(3):
            row = dict(base)
            row["candidate_id"] = f"NEG-{index}"
            states.append(learning._update_negative(row, root)["state"])
        assert states == ["observing", "observing", "active"]


def test_lingua_factory_registers_every_channel_for_one_family():
    with tempfile.TemporaryDirectory() as temporary:
        output = Path(temporary) / "factory"
        registry = lingua_factory.build(output, render_reels=False, limit=1, observe_market=False)
        assert registry["schema"] == "dio.marketing.creative_family_registry.v3"
        assert registry["summary"]["lingua_semantic_objects_registered"] == 10
        assert registry["summary"]["lingua_registration_errors"] == 0
        assert registry["summary"]["lingua_reuse_hits"] == 0
        assert registry["lingua_learning"]["direct_learning_to_execution"] is False
        assert registry["lingua_learning"]["publication"] is False
        assert registry["lingua_learning"]["spend"] is False
        objects = list((output / "_lingua" / "objects").glob("NICHE-DRAFT-*.json"))
        assert len(objects) == 10
