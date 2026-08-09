#!/usr/bin/env python3
"""Targeted probes for Sophia system gaps.

Currently covers:
- Source provenance / document evidence quality.
- Harmonic cadence discord detection.

These probes are local and deterministic; they strengthen subsystem evidence
without requiring provider secrets or network access.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT_DIR = ROOT / "evidence" / "system_gap_probes"
FIXTURE_DIR = OUT_DIR / "fixtures"


def write_fixture(name: str, text: str) -> Path:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    path = FIXTURE_DIR / name
    path.write_text(text, encoding="utf-8")
    return path


def probe_document_provenance() -> Dict[str, Any]:
    from arda_os.backend.services.document_evidence import build_document_evidence_bundle

    fixtures = [
        (
            "local_fixture.txt",
            "Local protocol fixture: OCR-supported chart text. Caption conflicts with OCR-supported numeric span.",
            "local_evidence_fixture",
        ),
        (
            "user_notes.txt",
            "Personal notes from /home/byron style local user document without external provenance.",
            "local_evidence_fixture",
        ),
        (
            "unknown_claim.txt",
            "A pasted claim says this proves all learning improved everywhere, but no source URL or author is visible.",
            "local_evidence_fixture",
        ),
    ]
    results: List[Dict[str, Any]] = []
    for name, text, expected_tier in fixtures:
        path = write_fixture(name, text)
        bundle = build_document_evidence_bundle(
            [{"source_path": str(path), "modality": "text_only"}],
            evidence_task="source_provenance_probe",
        )
        doc = bundle["documents"][0]
        provenance = doc.get("source_provenance") or {}
        quality = doc.get("evidence_quality") or {}
        passed = bool(provenance.get("tier")) and float(provenance.get("score") or 0) > 0
        results.append({
            "fixture": str(path),
            "expected_tier_family": expected_tier,
            "observed_tier": provenance.get("tier"),
            "provenance_score": provenance.get("score"),
            "quality": quality,
            "warnings": bundle.get("cross_source_warnings") or [],
            "passed": passed,
        })
    return {
        "name": "document_provenance",
        "total": len(results),
        "passes": sum(1 for row in results if row["passed"]),
        "results": results,
    }


def probe_harmonic_discord() -> Dict[str, Any]:
    from arda_os.backend.services.harmonic_engine import HarmonicEngine

    engine = HarmonicEngine(window_size=32)
    actor = "sophia_gap_probe"
    tool = "presence"
    domain = "covenant"
    env = "local_probe"

    # Establish calm baseline around 200 ms intervals.
    t0 = 1_000_000.0
    for index in range(10):
        engine.observe(
            actor_id=actor,
            tool_name=tool,
            target_domain=domain,
            environment=env,
            stage="baseline",
            timestamp_ms=t0 + index * 200.0,
        )
    calm = engine.observe(
        actor_id=actor,
        tool_name=tool,
        target_domain=domain,
        environment=env,
        stage="normal",
        timestamp_ms=t0 + 10 * 200.0,
    )

    # Inject rapid/chaotic cadence to simulate strain/discord.
    noisy_times = [t0 + 2050, t0 + 2060, t0 + 2070, t0 + 2600, t0 + 2610, t0 + 4000]
    discord = None
    for stamp in noisy_times:
        discord = engine.observe(
            actor_id=actor,
            tool_name=tool,
            target_domain=domain,
            environment=env,
            stage="covenant_pressure",
            timestamp_ms=stamp,
            context={"probe": "rapid_irregular_covenant_pressure"},
        )

    calm_state = (calm.get("harmonic_state") or {})
    discord_state = ((discord or {}).get("harmonic_state") or {})
    passed = (
        float(discord_state.get("discord_score") or 0) > float(calm_state.get("discord_score") or 0)
        and discord_state.get("mode_recommendation") in {
            "monitor_with_obligations",
            "tighten_scrutiny",
            "sandbox_or_contain",
            "observe_and_review",
        }
    )
    return {
        "name": "harmonic_discord",
        "total": 1,
        "passes": int(passed),
        "calm_state": calm_state,
        "discord_state": discord_state,
        "passed": passed,
    }


def main() -> int:
    probes = [probe_document_provenance(), probe_harmonic_discord()]
    total = sum(int(probe["total"]) for probe in probes)
    passes = sum(int(probe["passes"]) for probe in probes)
    artifact = {
        "schema_version": "sophia.system_gap_probes.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total": total,
            "passes": passes,
            "pass_rate": round(passes / total, 4) if total else 0.0,
            "by_probe": {
                probe["name"]: {
                    "total": probe["total"],
                    "passes": probe["passes"],
                    "pass_rate": round(probe["passes"] / probe["total"], 4) if probe["total"] else 0.0,
                }
                for probe in probes
            },
        },
        "probes": probes,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUT_DIR / f"sophia_system_gap_probes_{stamp}.json"
    out.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"artifact": str(out), "summary": artifact["summary"]}, indent=2))
    return 0 if passes == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
