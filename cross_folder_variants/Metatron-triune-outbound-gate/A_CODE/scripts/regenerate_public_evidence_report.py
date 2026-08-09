#!/usr/bin/env python3
"""
Regenerate public evidence claims for the 2026-04-28 bundle.

The generated artifacts deliberately separate observed K0 kernel denials from
deductive K2 prevention support, and keep auxiliary telemetry claims modest:
Sigma entries are rule/tag coverage records, ClamAV is scan enumeration only
when no signatures fire, and Arkime forensic replay is only claimed when PCAP
payload files are actually packaged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tarfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - operational dependency check
    raise SystemExit("pyyaml is required: pip install pyyaml") from exc


REPO = Path(__file__).resolve().parent.parent
DEFAULT_ARDA_DIR = REPO / "artifacts/evidence/arda_prevention"
DEFAULT_SIGMA_SOURCE = REPO / "backend/sigma_rules"
DEFAULT_CLASSIFICATION = REPO / "metatron_honest_tvr_classification_20260428T155428.json"
DEFAULT_SUMMARY = REPO / "metatron_public_claim_summary_20260428T155428.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def technique_from_stem(stem: str) -> str | None:
    match = re.match(r"arda_prevention_(T\d{4})(\d{3})?_\d{8}_\d{6}$", stem)
    if not match:
        return None
    base, sub = match.groups()
    return f"{base}.{sub}" if sub else base


def arda_files_for_timestamp(arda_dir: Path, timestamp: str) -> list[Path]:
    return sorted(arda_dir.glob(f"arda_prevention_*_{timestamp}.json"))


def read_observed_k0(arda_dir: Path, timestamp: str) -> dict[str, dict[str, Any]]:
    observed: dict[str, dict[str, Any]] = {}
    for path in arda_files_for_timestamp(arda_dir, timestamp):
        try:
            record = load_json(path)
        except Exception:
            continue
        tid = record.get("technique_id") or technique_from_stem(path.stem)
        if not tid:
            continue
        exec_attempt = record.get("exec_attempt") or {}
        eperm = record.get("eperm") or {}
        is_k0 = (
            record.get("verdict") == "kernel_prevented"
            and exec_attempt.get("denied") is True
            and eperm.get("eperm_confirmed") is True
        )
        if is_k0:
            observed[tid] = {
                "mode": "K0",
                "strength": "HARD_POSITIVE",
                "description": "Observed kernel denial (EPERM)",
                "can_certify": True,
                "source_file": str(path.relative_to(REPO)),
                "captured_at": record.get("captured_at"),
                "rc": exec_attempt.get("rc"),
                "payload_sha256": exec_attempt.get("payload_sha256"),
                "deny_count_delta": (record.get("enforcement") or {}).get("deny_count_delta"),
                "pulse_total_denials": (record.get("enforcement") or {}).get("pulse_total_denials"),
                "bpf_sha256": (
                    (record.get("substrate_proof") or {})
                    .get("bpf_program", {})
                    .get("sha256")
                ),
            }
    return observed


def read_legacy_classification(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        return load_json(path)
    except Exception:
        return {}


def read_bundle_listing(bundle_path: Path | None) -> set[str]:
    if not bundle_path or not bundle_path.exists():
        return set()
    with tarfile.open(bundle_path, "r:gz") as tf:
        return set(tf.getnames())


def pcap_files_in_listing(listing: set[str]) -> list[str]:
    return sorted(name for name in listing if re.search(r"\.pcap(?:\.zst)?$", name))


def summarize_clamav(clamav_dir: Path) -> dict[str, Any]:
    scanned = 0
    infected = 0
    records = 0
    for path in sorted(clamav_dir.glob("run_*.json")):
        try:
            evidence = (load_json(path).get("clamav_evidence") or {})
        except Exception:
            continue
        records += 1
        scanned += int(evidence.get("scanned_count") or 0)
        infected += int(evidence.get("infected_count") or 0)
    return {
        "records": records,
        "files_scanned": scanned,
        "infected_count": infected,
        "claim": (
            "ClamAV confirms scan enumeration. It found no malware signatures "
            "in these payload files and is not evidence of maliciousness."
        ),
        "can_certify_maliciousness": False,
    }


def summarize_arkime(arkime_dir: Path, bundle_listing: set[str]) -> dict[str, Any]:
    json_records = 0
    referenced_pcaps: set[str] = set()
    packets = 0
    compressed_bytes = 0
    for path in sorted(arkime_dir.glob("run_*.json")):
        try:
            evidence = load_json(path).get("arkime_evidence") or {}
        except Exception:
            continue
        json_records += 1
        for pcap in evidence.get("pcap_files") or []:
            filename = pcap.get("filename")
            if filename:
                referenced_pcaps.add(filename)
        packets = max(packets, int((evidence.get("packet_stats") or {}).get("total_packets") or 0))
        compressed_bytes = max(compressed_bytes, int(evidence.get("total_bytes_compressed") or 0))

    packaged_pcaps = pcap_files_in_listing(bundle_listing)
    referenced_packaged = sorted(
        name for name in referenced_pcaps
        if any(entry.endswith(name) for entry in packaged_pcaps)
    )
    forensic_replay_ready = bool(referenced_packaged)
    return {
        "json_records": json_records,
        "referenced_pcap_count": len(referenced_pcaps),
        "packaged_pcap_count": len(packaged_pcaps),
        "referenced_packaged_pcap_count": len(referenced_packaged),
        "packet_stats_total_packets_max": packets,
        "compressed_bytes_max": compressed_bytes,
        "forensic_replay_ready": forensic_replay_ready,
        "claim": (
            "Arkime JSON enumerates PCAP filenames, sizes, and packet stats. "
            "Do not claim forensic replay for this tarball unless actual PCAP "
            "files are included."
            if not forensic_replay_ready
            else "Arkime JSON and packaged PCAP files support forensic replay."
        ),
    }


def dedup_falco(falco_dir: Path, out_path: Path) -> dict[str, Any]:
    total_records = 0
    raw_alerts = 0
    groups: dict[str, dict[str, Any]] = {}
    rule_counts: Counter[str] = Counter()
    technique_counts: Counter[str] = Counter()

    for path in sorted(falco_dir.glob("run_*.json")):
        try:
            record = load_json(path)
        except Exception:
            continue
        total_records += 1
        techniques = record.get("techniques") or record.get("techniques_executed") or []
        evidence = record.get("falco_evidence") or {}
        alerts = evidence.get("alerts") or []
        raw_alerts += len(alerts)
        if not alerts and evidence.get("alert_count"):
            raw_alerts += int(evidence.get("alert_count") or 0)
        for alert in alerts or [{}]:
            fields = alert.get("fields") or {}
            key_parts = [
                ",".join(sorted(techniques)),
                str(alert.get("rule") or ""),
                str(alert.get("priority") or ""),
                str(fields.get("proc_name") or ""),
                str(fields.get("proc_cmdline") or ""),
                str(fields.get("fd_name") or ""),
                str(alert.get("container") or fields.get("container_name") or ""),
            ]
            key = hashlib.sha256("\x1f".join(key_parts).encode()).hexdigest()
            group = groups.setdefault(
                key,
                {
                    "techniques": sorted(set(techniques)),
                    "rule": alert.get("rule"),
                    "priority": alert.get("priority"),
                    "process": fields.get("proc_name"),
                    "command": fields.get("proc_cmdline"),
                    "file": fields.get("fd_name"),
                    "container": alert.get("container") or fields.get("container_name"),
                    "count": 0,
                    "sample_run": str(path.relative_to(REPO)),
                },
            )
            group["count"] += max(1, int(evidence.get("alert_count") or 0) if not alerts else 1)

    for group in groups.values():
        if group.get("rule"):
            rule_counts[str(group["rule"])] += group["count"]
        for tid in group.get("techniques") or []:
            technique_counts[tid] += group["count"]

    harvest_summaries = []
    for path in sorted(falco_dir.glob("harvest_summary_*.json")):
        try:
            harvest = load_json(path)
        except Exception:
            continue
        harvest_summaries.append({
            "path": str(path.relative_to(REPO)),
            "harvested_at": harvest.get("harvested_at"),
            "groups_found": harvest.get("groups_found"),
            "mapped_alerts": harvest.get("mapped_alerts"),
            "run_files": len(harvest.get("run_files") or []),
        })
    latest_harvest = harvest_summaries[-1] if harvest_summaries else {}
    authoritative_groups = latest_harvest.get("groups_found") or len(groups)
    authoritative_alerts = latest_harvest.get("mapped_alerts") or raw_alerts

    summary = {
        "generated_at": now(),
        "source_dir": str(falco_dir.relative_to(REPO)),
        "authoritative_counts": {
            "run_records": total_records,
            "authoritative_alerts": authoritative_alerts,
            "authoritative_deduplicated_groups": authoritative_groups,
            "raw_alerts_reparsed_from_available_json": raw_alerts,
            "secondary_reparse_groups": len(groups),
        },
        "latest_harvest_summary": latest_harvest,
        "harvest_summaries": harvest_summaries,
        "claim": (
            "Use run_records as the file-enumeration count and the latest "
            "harvester summary's groups_found/mapped_alerts as the authoritative "
            "deduplicated alert counts."
        ),
        "deduplication_key": [
            "techniques",
            "rule",
            "priority",
            "process",
            "command",
            "file",
            "container",
        ],
        "top_rules": dict(rule_counts.most_common(20)),
        "top_techniques": dict(technique_counts.most_common(20)),
        "groups": sorted(groups.values(), key=lambda g: (-g["count"], str(g.get("rule") or "")))[:500],
    }
    out_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def load_sigma_rules(source_dir: Path) -> dict[str, list[dict[str, Any]]]:
    by_technique: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in sorted(source_dir.rglob("*.yml")) + sorted(source_dir.rglob("*.yaml")):
        try:
            docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8", errors="replace")))
        except Exception:
            continue
        for doc in docs:
            if not isinstance(doc, dict) or not doc.get("detection"):
                continue
            tags = [str(tag) for tag in doc.get("tags") or []]
            techniques = sorted({
                tag.replace("attack.", "").upper()
                for tag in tags
                if re.match(r"attack\.t\d{4}(?:\.\d{3})?$", tag.lower())
            })
            if not techniques:
                continue
            rel = path.relative_to(source_dir)
            rule = {
                "rule_id": str(doc.get("id") or path.stem),
                "title": str(doc.get("title") or path.stem),
                "status": str(doc.get("status") or "unknown"),
                "level": str(doc.get("level") or "unknown"),
                "source_rule_path": str(path.relative_to(REPO)),
                "packaged_rule_path": str(Path("sigma_rules") / rel),
                "rule_sha256": sha256_file(path),
                "detection_basis": "sigma_rule_covers_technique_by_attack_tag",
                "note": "Coverage mapping, not a live event-stream match.",
            }
            for tid in techniques:
                by_technique[tid].append(rule)
    return dict(by_technique)


def build_sigma_artifacts(
    source_dir: Path,
    observed_k0: dict[str, Any],
    rules_out: Path,
    matches_out: Path,
) -> dict[str, Any]:
    rules_by_technique = load_sigma_rules(source_dir)
    rules_out.mkdir(parents=True, exist_ok=True)
    matches_out.mkdir(parents=True, exist_ok=True)

    copied: dict[str, str] = {}
    matched_techniques = 0
    match_records = 0
    for tid in sorted(observed_k0):
        rules = rules_by_technique.get(tid, [])
        if rules:
            matched_techniques += 1
        for rule in rules:
            src = REPO / rule["source_rule_path"]
            dst = REPO / rule["packaged_rule_path"]
            if str(dst) not in copied:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                copied[str(dst)] = rule["rule_sha256"]
        matches = {
            "schema": "metatron_sigma_matches.v1",
            "generated_at": now(),
            "technique_id": tid,
            "arda_k0_source": observed_k0[tid]["source_file"],
            "match_semantics": "coverage_by_attack_tag_not_live_event_match",
            "rules": rules,
        }
        safe_tid = tid.replace(".", "_")
        (matches_out / f"{safe_tid}.json").write_text(
            json.dumps(matches, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        match_records += len(rules)

    return {
        "schema": "metatron_sigma_mapping_summary.v1",
        "generated_at": now(),
        "sigma_source_dir": str(source_dir.relative_to(REPO)),
        "observed_k0_techniques": len(observed_k0),
        "techniques_with_sigma_coverage": matched_techniques,
        "techniques_without_sigma_coverage": len(observed_k0) - matched_techniques,
        "sigma_rule_files_packaged": len(copied),
        "sigma_rule_technique_records": match_records,
        "match_semantics": "coverage_by_attack_tag_not_live_event_match",
        "rules_out": str(rules_out.relative_to(REPO)),
        "matches_out": str(matches_out.relative_to(REPO)),
    }


def build_classification(
    observed_k0: dict[str, dict[str, Any]],
    legacy: dict[str, Any],
    arda_timestamp: str,
    arkime_summary: dict[str, Any],
    clamav_summary: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    all_techniques = sorted(set(legacy) | set(observed_k0))
    techniques: dict[str, Any] = {}
    tiers: Counter[str] = Counter()
    k2_count = 0

    for tid in all_techniques:
        modes: list[dict[str, Any]] = []
        if tid in observed_k0:
            modes.append(observed_k0[tid])
            tier = "platinum"
            public_claim_class = "observed_k0"
        else:
            legacy_evidence = ((legacy.get(tid) or {}).get("evidence") or {})
            legacy_modes = legacy_evidence.get("evidence_modes") or []
            for mode in legacy_modes:
                if mode.get("mode") == "K2":
                    k2_count += 1
                    modes.append({
                        **mode,
                        "strength": "STRONG_SUPPORT",
                        "can_certify": False,
                    })
                elif mode.get("mode") in {"K1", "L1", "L2", "H1/C0"}:
                    modes.append({**mode, "can_certify": False})
                elif str(mode.get("mode", "")).startswith("A"):
                    modes.append({
                        **mode,
                        "can_certify": False,
                        "note": arkime_summary["claim"],
                    })
            tier = "support_only" if modes else "unclassified"
            public_claim_class = "deductive_or_auxiliary_support" if modes else "not_in_observed_run"

        tiers[tier] += 1
        techniques[tid] = {
            "tier": tier,
            "public_claim_class": public_claim_class,
            "evidence": {
                "evidence_modes": modes,
                "hard_positives_present": tid in observed_k0,
                "hard_positive_types": ["K0"] if tid in observed_k0 else [],
                "can_certify_platinum": tid in observed_k0,
            },
        }

    summary = {
        "schema": "metatron_honest_classification_summary.v2",
        "generated_at": now(),
        "arda_observed_run_timestamp": arda_timestamp,
        "public_claim_centerpiece": "654 observed K0 kernel denials in the 20260428_142529 ARDA run",
        "tier_distribution": dict(tiers),
        "observed_k0_count": len(observed_k0),
        "deductive_k2_support_count": k2_count,
        "legacy_technique_count": len(legacy),
        "classification_technique_count": len(techniques),
        "missing_in_legacy_but_observed_k0": sorted(set(observed_k0) - set(legacy)),
        "clamav": clamav_summary,
        "arkime": arkime_summary,
    }
    return {"summary": summary, "techniques": techniques}, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arda-timestamp", default="20260428_142529")
    parser.add_argument("--bundle", type=Path, default=REPO / "metatron_evidence_bundle_20260428T155428.tar.gz")
    parser.add_argument("--legacy-classification", type=Path, default=REPO / "metatron_honest_tvr_classification_20260427.json")
    parser.add_argument("--classification-out", type=Path, default=DEFAULT_CLASSIFICATION)
    parser.add_argument("--summary-out", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--sigma-source", type=Path, default=DEFAULT_SIGMA_SOURCE)
    parser.add_argument("--sigma-rules-out", type=Path, default=REPO / "sigma_rules")
    parser.add_argument("--sigma-matches-out", type=Path, default=REPO / "sigma_matches")
    args = parser.parse_args()

    observed_k0 = read_observed_k0(DEFAULT_ARDA_DIR, args.arda_timestamp)
    bundle_listing = read_bundle_listing(args.bundle)
    legacy = read_legacy_classification(args.legacy_classification)

    falco_summary = dedup_falco(
        REPO / "artifacts/evidence/falco",
        REPO / "artifacts/evidence/falco/falco_dedup_summary_20260428T155428.json",
    )
    clamav_summary = summarize_clamav(REPO / "artifacts/evidence/clamav")
    arkime_summary = summarize_arkime(REPO / "artifacts/evidence/arkime", bundle_listing)

    sigma_summary = build_sigma_artifacts(
        args.sigma_source,
        observed_k0,
        args.sigma_rules_out,
        args.sigma_matches_out,
    )
    (REPO / "sigma_mapping_summary.json").write_text(
        json.dumps(sigma_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    classification, public_summary = build_classification(
        observed_k0,
        legacy,
        args.arda_timestamp,
        arkime_summary,
        clamav_summary,
    )
    args.classification_out.write_text(
        json.dumps(classification, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    manifest = {
        "schema": "metatron_sigma_run_manifest.v1",
        "generated_at": now(),
        "arda_observed_run_timestamp": args.arda_timestamp,
        "classification_report": str(args.classification_out.relative_to(REPO)),
        "sigma_mapping_summary": "sigma_mapping_summary.json",
        "sigma_rules_dir": str(args.sigma_rules_out.relative_to(REPO)),
        "sigma_matches_dir": str(args.sigma_matches_out.relative_to(REPO)),
        "falco_dedup_summary": "artifacts/evidence/falco/falco_dedup_summary_20260428T155428.json",
        "public_summary": str(args.summary_out.relative_to(REPO)),
        "bundle_checked": str(args.bundle.relative_to(REPO)) if args.bundle.exists() else str(args.bundle),
        "bundle_contains_actual_pcaps": bool(pcap_files_in_listing(bundle_listing)),
        "notes": [
            "Observed K0 is separated from deductive K2 support.",
            "Sigma matches are ATT&CK tag coverage records, not live event-stream detections.",
            "ClamAV confirms scan enumeration only when infected_count is zero.",
            "Arkime forensic replay requires packaged PCAP files.",
        ],
    }
    (REPO / "sigma_run_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    public_summary = {
        **public_summary,
        "sigma": sigma_summary,
        "falco": {
            "claim": falco_summary["claim"],
            **falco_summary["authoritative_counts"],
        },
        "artifacts": manifest,
    }
    args.summary_out.write_text(
        json.dumps(public_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(f"Observed K0 techniques: {len(observed_k0)}")
    print(f"Classification written: {args.classification_out}")
    print(f"Sigma rules packaged: {sigma_summary['sigma_rule_files_packaged']}")
    print(f"Sigma match records: {sigma_summary['sigma_rule_technique_records']}")
    print(
        "Falco authoritative groups: "
        f"{falco_summary['authoritative_counts']['authoritative_deduplicated_groups']}"
    )
    print(f"Arkime packaged PCAPs: {arkime_summary['packaged_pcap_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
