#!/usr/bin/env python3
"""
tvr_honest_regenerator.py
==========================
Regenerates TVRs using HONEST evidence scoring.

Key changes:
- K0 (observed kernel denial) = can certify PLATINUM
- K2 (deductive prevention) = supports only, does not certify
- L2 (synthetic audit) = support only, marked explicitly
- A0 (simulated PCAP) = pipeline/scaffold only
- Tier promotion requires at least one HARD_POSITIVE source
- No auto-promotion based on evidence layer count
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List

NOW = lambda: datetime.now(timezone.utc).isoformat()
REPO = Path(__file__).resolve().parent.parent

# Evidence strength mapping
EVIDENCE_STRENGTH = {
    # HARD_POSITIVE (can certify alone)
    "H0": {"strength": "HARD_POSITIVE", "can_certify": True, "description": "Direct observed host execution"},
    "D0": {"strength": "HARD_POSITIVE", "can_certify": True, "description": "Direct detection fired"},
    "K0": {"strength": "HARD_POSITIVE", "can_certify": True, "description": "Observed kernel denial (EPERM)"},
    "L0": {"strength": "HARD_POSITIVE", "can_certify": True, "description": "Real vendor audit log"},
    "L1": {"strength": "HARD_POSITIVE", "can_certify": True, "description": "Lab API audit log"},
    "A2": {"strength": "HARD_POSITIVE", "can_certify": True, "description": "Real Arkime PCAP export"},

    # STRONG_SUPPORT (corroborating, not certifying)
    "K1": {"strength": "STRONG_SUPPORT", "can_certify": False, "description": "Arda substrate proof only"},
    "K2": {"strength": "STRONG_SUPPORT", "can_certify": False, "description": "Deductive prevention (untrusted /tmp form)"},
    "L2": {"strength": "STRONG_SUPPORT", "can_certify": False, "description": "Lab-synthetic audit event"},
    "A1": {"strength": "STRONG_SUPPORT", "can_certify": False, "description": "Lab-generated PCAP (hashed)"},
    "C1": {"strength": "STRONG_SUPPORT", "can_certify": False, "description": "Multi-source correlation"},
    "D1": {"strength": "STRONG_SUPPORT", "can_certify": False, "description": "Detection rule mapped"},

    # CONTEXTUAL_SUPPORT
    "H1": {"strength": "CONTEXTUAL_SUPPORT", "can_certify": False, "description": "Host telemetry + lure"},
    "H2": {"strength": "CONTEXTUAL_SUPPORT", "can_certify": False, "description": "Host telemetry only"},
    "C0": {"strength": "CONTEXTUAL_SUPPORT", "can_certify": False, "description": "Context telemetry"},
    "D2": {"strength": "CONTEXTUAL_SUPPORT", "can_certify": False, "description": "Detection capability"},

    # PIPELINE_SUPPORT
    "A0": {"strength": "PIPELINE_SUPPORT", "can_certify": False, "description": "Simulated Arkime metadata"},
    "M0": {"strength": "PIPELINE_SUPPORT", "can_certify": False, "description": "Mapped query/rule"},
}

def classify_evidence(tech_id: str, evidence_dir: Path) -> Dict[str, Any]:
    """Classify evidence for a technique using honest evidence mode."""

    evidence_modes = []
    hard_positives = []

    # Check Arda kernel
    arda_file = evidence_dir / "arda_kernel_prevention.json"
    if arda_file.exists():
        with open(arda_file) as f:
            arda = json.load(f)

        observed = arda.get("observed_run_count", 0)
        if observed > 0:
            # This is K0: observed kernel denial
            evidence_modes.append({
                "mode": "K0",
                "description": "Observed kernel denial (EPERM)",
                "count": observed,
                "can_certify": True,
            })
            hard_positives.append("K0")
        else:
            # This is K2: deductive prevention
            evidence_modes.append({
                "mode": "K2",
                "description": f"Deductive prevention ({arda.get('deductive_run_count', 0)} modelled runs)",
                "count": arda.get("deductive_run_count", 0),
                "can_certify": False,
                "note": "Substrate proof applies, but no observed execution",
            })
            # K1: substrate proof
            evidence_modes.append({
                "mode": "K1",
                "description": "Arda substrate proof (cryptographic)",
                "substrate_hash": arda.get("substrate_proof", {}).get("bpf_program", {}).get("sha256"),
                "can_certify": False,
            })

    # Check Arkime
    arkime_file = evidence_dir / "arkime_network_forensics.json"
    if arkime_file.exists():
        with open(arkime_file) as f:
            arkime = json.load(f)

        # Detect real A2 evidence (schema v2 from run_arkime_network_capture.py)
        if arkime.get("evidence_mode") == "A2" and arkime.get("evidence_strength") == "HARD_POSITIVE":
            sessions_in_window = arkime.get("session_data", {}).get("sessions_in_window", 0)
            sessions_sampled = arkime.get("session_data", {}).get("sessions_sampled", 0)
            evidence_modes.append({
                "mode": "A2",
                "description": "Real Arkime-indexed PCAP sessions (HARD_POSITIVE)",
                "sessions_in_window": sessions_in_window,
                "sessions_sampled": sessions_sampled,
                "capture_interface": arkime.get("arkime_capture", {}).get("interface", ""),
                "elasticsearch": arkime.get("arkime_capture", {}).get("elasticsearch", ""),
                "can_certify": True,
                "note": f"Real packet capture: {sessions_in_window} sessions indexed by Arkime v5",
            })
            hard_positives.append("A2")
        elif "pcap_file" in arkime.get("capture", {}):
            evidence_modes.append({
                "mode": "A0/A1",
                "description": "Arkime forensic scaffold (design proof, not verified PCAP)",
                "sessions": arkime.get("session_count", 0),
                "note": "Real PCAP would be A2; currently this is scaffolding",
                "can_certify": False,
            })

    # Check Cloud/SaaS L1 evidence
    cloud_file = evidence_dir / "cloud_saas_evidence.json"
    if cloud_file.exists():
        with open(cloud_file) as f:
            cloud = json.load(f)
        if cloud.get("evidence_mode") == "L1" and cloud.get("evidence_strength") == "HARD_POSITIVE":
            successful = cloud.get("summary", {}).get("successful_calls", 0)
            if successful > 0:
                evidence_modes.append({
                    "mode": "L1",
                    "description": "Lab API audit log — real GitHub API responses (HARD_POSITIVE)",
                    "provider": cloud.get("provider", "GitHub REST API v3"),
                    "actor": cloud.get("actor", ""),
                    "successful_calls": successful,
                    "can_certify": True,
                })
                hard_positives.append("L1")

    cloud_audit_file = evidence_dir / "cloud_audit_events.json"
    if cloud_audit_file.exists():
        with open(cloud_audit_file) as f:
            cloud_audit = json.load(f)
        if cloud_audit.get("evidence_mode") == "L1" and cloud_audit.get("evidence_strength") == "HARD_POSITIVE":
            evidence_items = cloud_audit.get("summary", {}).get("evidence_items", len(cloud_audit.get("data", [])))
            if evidence_items > 0:
                evidence_modes.append({
                    "mode": "L1",
                    "description": "Lab API audit log — real AWS CloudTrail management events (HARD_POSITIVE)",
                    "provider": cloud_audit.get("provider", "AWS CloudTrail"),
                    "actor": cloud_audit.get("actor", ""),
                    "successful_calls": cloud_audit.get("summary", {}).get("successful_calls", evidence_items),
                    "can_certify": True,
                })
                hard_positives.append("L1")

    # Check Mobile/MDM
    mdm_file = evidence_dir / "mdm_mobile_evidence.json"
    if mdm_file.exists():
        with open(mdm_file) as f:
            mdm = json.load(f)
        evidence_modes.append({
            "mode": "L2",
            "description": "Lab-synthetic MDM audit event",
            "mdm_providers": [p["provider"] for p in mdm.get("mdm_providers", [])],
            "can_certify": False,
            "note": "Real MDM audit would be L0/L1",
        })

    # Check osquery
    osquery_file = evidence_dir / "live_osquery.json"
    if osquery_file.exists():
        evidence_modes.append({
            "mode": "H1/C0",
            "description": "Live osquery telemetry",
            "can_certify": False,
        })

    return {
        "evidence_modes": evidence_modes,
        "hard_positives_present": len(hard_positives) > 0,
        "hard_positive_types": hard_positives,
        "can_certify_platinum": len(hard_positives) > 0,
    }

def score_tier(evidence_class: Dict[str, Any]) -> str:
    """Score tier based on HONEST evidence classification."""

    # PLATINUM: needs at least one HARD_POSITIVE
    if evidence_class["can_certify_platinum"]:
        return "platinum"

    # GOLD: strong corroboration
    has_strong = any(
        m.get("can_certify") == False and "STRONG" in str(m.get("description", ""))
        for m in evidence_class["evidence_modes"]
    )
    if has_strong:
        return "gold"

    # SILVER: some support
    if evidence_class["evidence_modes"]:
        return "silver"

    # BRONZE: just exists
    return "bronze"

def main():
    print("Honest TVR Regeneration")
    print("=" * 70)

    # Load all 691 canonical techniques
    bundle_path = REPO / "metatron_evidence_bundle_20260427T052729_platinum"
    tech_index_path = bundle_path / "technique_index.json"

    with open(tech_index_path) as f:
        index = json.load(f)

    all_techniques = sorted(index.get("techniques", {}).keys())
    evidence_dir_base = REPO / "evidence-bundle/integration_evidence"

    # Classify each technique
    platinum_honest = 0
    gold = 0
    silver = 0
    bronze = 0

    classification_report = {}

    for tech_id in all_techniques:
        tech_evidence_dir = evidence_dir_base / tech_id

        evidence_class = classify_evidence(tech_id, tech_evidence_dir)
        tier = score_tier(evidence_class)

        classification_report[tech_id] = {
            "tier": tier,
            "evidence": evidence_class,
        }

        if tier == "platinum":
            platinum_honest += 1
        elif tier == "gold":
            gold += 1
        elif tier == "silver":
            silver += 1
        else:
            bronze += 1

    print()
    print("HONEST TIER DISTRIBUTION:")
    print(f"  Platinum (HARD_POSITIVE evidence): {platinum_honest}")
    print(f"  Gold (STRONG_SUPPORT):            {gold}")
    print(f"  Silver (multiple sources):        {silver}")
    print(f"  Bronze (capability only):         {bronze}")
    print()

    # Check K0 vs K2
    k0_count = 0
    k2_count = 0
    for tech_id, report in classification_report.items():
        for ev in report["evidence"]["evidence_modes"]:
            if ev.get("mode") == "K0":
                k0_count += 1
            elif ev.get("mode") == "K2":
                k2_count += 1

    print("ARDA KERNEL EVIDENCE BREAKDOWN:")
    print(f"  K0 (observed kernel denial):  {k0_count} techniques")
    print(f"  K2 (deductive prevention):    {k2_count} techniques")

    # Check A2 count
    a2_count = sum(
        1 for report in classification_report.values()
        for ev in report["evidence"]["evidence_modes"]
        if ev.get("mode") == "A2"
    )
    print(f"\nARKIME NETWORK EVIDENCE:")
    print(f"  A2 (real PCAP indexed):       {a2_count} techniques")

    l1_count = sum(
        1 for report in classification_report.values()
        for ev in report["evidence"]["evidence_modes"]
        if ev.get("mode") == "L1"
    )
    print(f"\nCLOUD/SaaS EVIDENCE:")
    print(f"  L1 (real GitHub API audit):   {l1_count} techniques")
    print()

    # Save report
    report_file = REPO / "metatron_honest_tvr_classification_20260427.json"
    with open(report_file, "w") as f:
        json.dump(classification_report, f, indent=2, default=str)

    print(f"Classification report: {report_file.name}")
    print()
    print("=" * 70)
    print("✅ HONEST CLASSIFICATION COMPLETE")
    print()
    print("KEY INSIGHT:")
    print(f"  This bundle provides STRONG CORROBORATION for {platinum_honest + gold} techniques")
    print(f"  But only {k0_count} have HARD_POSITIVE kernel evidence (K0)")
    print(f"  The remainder use deductive/synthetic evidence (valuable but not certifying alone)")

    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
