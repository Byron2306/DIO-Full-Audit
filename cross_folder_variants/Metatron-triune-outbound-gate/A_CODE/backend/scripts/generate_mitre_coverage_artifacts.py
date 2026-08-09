import json
import re
import uuid
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
CONFIG_DIR = ROOT / "config"
DATA_DIR = BACKEND_DIR / "data"
SIGMA_DIR = BACKEND_DIR / "sigma_rules" / "generated"
QUERY_CATALOG_PATH = DATA_DIR / "generated_osquery_builtin_queries.json"
SOAR_EXECUTIONS_PATH = DATA_DIR / "generated_soar_executions.json"
SOAR_ARCHIVE_PATH = DATA_DIR / "soar_executions_archive.json"
TECHNIQUE_CATALOG_PATH = DATA_DIR / "generated_mitre_techniques.json"
ATOMIC_CONFIG_PATH = CONFIG_DIR / "atomic_powershell.yml"
ENTERPRISE_ATTACK_PATH = ROOT / "atomic-red-team" / "atomic_red_team" / "enterprise-attack.json"

TECHNIQUE_PATTERN = re.compile(r"\bT\d{4}(?:\.\d{3})?\b", re.IGNORECASE)

# Keep the generated detections intentionally simple and syntactically valid.
SIGMA_TEMPLATES = [
    {
        "suffix": "proc_exec",
        "title": "Process Execution Indicator",
        "description": "Generic process execution indicator aligned to repository coverage mapping.",
        "logsource": {"category": "process_creation", "product": "linux"},
        "detection": {
            "selection": {
                "Image|endswith": ["bash", "sh", "python3", "curl", "wget"],
                "CommandLine|contains": ["/tmp/", "/dev/shm/", "nohup ", "sudo "],
            },
            "condition": "selection",
        },
        "level": "medium",
        "tactic_tag": "attack.execution",
    },
    {
        "suffix": "file_touch",
        "title": "Filesystem Staging Indicator",
        "description": "Generic file staging and artifact placement indicator.",
        "logsource": {"category": "file_event", "product": "linux"},
        "detection": {
            "selection": {
                "TargetFilename|startswith": ["/tmp/", "/var/tmp/", "/dev/shm/", "/etc/"],
            },
            "condition": "selection",
        },
        "level": "medium",
        "tactic_tag": "attack.collection",
    },
    {
        "suffix": "network_activity",
        "title": "Outbound Network Indicator",
        "description": "Generic outbound network activity indicator for technique coverage.",
        "logsource": {"category": "network_connection", "product": "linux"},
        "detection": {
            "selection": {
                "DestinationPort": [22, 53, 80, 443, 4444, 8080, 8443, 31337],
                "Initiated": True,
            },
            "condition": "selection",
        },
        "level": "medium",
        "tactic_tag": "attack.command_and_control",
    },
    {
        "suffix": "defense_evasion",
        "title": "Defense Evasion Indicator",
        "description": "Generic defense evasion and cleanup indicator.",
        "logsource": {"category": "process_creation", "product": "linux"},
        "detection": {
            "selection": {
                "CommandLine|contains": [
                    "rm -f ",
                    "truncate -s 0",
                    "base64 -d",
                    "chmod +x",
                    "history -c",
                ],
            },
            "condition": "selection",
        },
        "level": "high",
        "tactic_tag": "attack.defense_evasion",
    },
]

OSQUERY_TEMPLATES = [
    {
        "suffix": "processes",
        "description": "Inspect suspicious process metadata relevant to the mapped ATT&CK technique.",
        "sql": "SELECT pid, parent, name, path, cmdline, cwd, on_disk FROM processes LIMIT 200;",
    },
    {
        "suffix": "filesystem",
        "description": "Inspect suspicious filesystem artifacts relevant to the mapped ATT&CK technique.",
        "sql": "SELECT path, filename, directory, size, uid, gid, mode, mtime FROM file WHERE path LIKE '/tmp/%' OR path LIKE '/var/tmp/%' OR path LIKE '/dev/shm/%' LIMIT 200;",
    },
    {
        "suffix": "network",
        "description": "Inspect suspicious socket activity relevant to the mapped ATT&CK technique.",
        "sql": "SELECT pid, fd, socket, family, protocol, local_address, remote_address, local_port, remote_port, state FROM process_open_sockets LIMIT 200;",
    },
]


def _discover_backend_techniques() -> set[str]:
    techniques: set[str] = set()
    for path in BACKEND_DIR.rglob("*.py"):
        if "sigma_rules/generated" in path.as_posix():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in TECHNIQUE_PATTERN.findall(text):
            techniques.add(match.upper())
    return techniques


def _discover_atomic_config_techniques() -> set[str]:
    if not ATOMIC_CONFIG_PATH.exists():
        return set()

    text = ATOMIC_CONFIG_PATH.read_text(encoding="utf-8", errors="ignore")
    return {match.upper() for match in TECHNIQUE_PATTERN.findall(text)}


def _load_enterprise_attack_techniques() -> tuple[list[str], dict]:
    if not ENTERPRISE_ATTACK_PATH.exists():
        return [], {
            "enterprise_attack_source": None,
            "enterprise_attack_parents": 0,
            "enterprise_attack_subtechniques": 0,
            "enterprise_attack_techniques": 0,
        }

    payload = json.loads(ENTERPRISE_ATTACK_PATH.read_text(encoding="utf-8"))
    objects = payload.get("objects") or []
    attack_patterns = [
        obj for obj in objects
        if obj.get("type") == "attack-pattern"
        and not obj.get("revoked", False)
        and not obj.get("x_mitre_deprecated", False)
    ]

    parents = 0
    subtechniques = 0
    techniques: set[str] = set()
    for obj in attack_patterns:
        external_refs = obj.get("external_references") or []
        attack_id = None
        for ref in external_refs:
            if str(ref.get("source_name") or "").lower() == "mitre-attack":
                attack_id = str(ref.get("external_id") or "").strip().upper()
                break
        if not attack_id:
            continue
        techniques.add(attack_id)
        if obj.get("x_mitre_is_subtechnique"):
            subtechniques += 1
        else:
            parents += 1

    return sorted(techniques), {
        "enterprise_attack_source": str(ENTERPRISE_ATTACK_PATH),
        "enterprise_attack_parents": parents,
        "enterprise_attack_subtechniques": subtechniques,
        "enterprise_attack_techniques": len(techniques),
    }


def discover_techniques() -> tuple[list[str], list[str], dict]:
    catalog_techniques, catalog_metadata = _load_enterprise_attack_techniques()
    backend_techniques = _discover_backend_techniques()
    atomic_config_techniques = _discover_atomic_config_techniques()
    raw_union = backend_techniques | atomic_config_techniques

    # Expand: when a sub-technique (for example, Txxxx.001) is in scope, also
    # include its parent (Txxxx) so the generator produces parent-technique
    # sigma/osquery coverage too.
    parent_ids: set[str] = set()
    for tid in raw_union:
        if "." in tid:
            parent_ids.add(tid.split(".")[0])
    all_techniques = raw_union | parent_ids

    referenced_techniques = sorted(all_techniques)
    techniques = catalog_techniques or referenced_techniques
    metadata = {
        **catalog_metadata,
        "backend_reference_techniques": len(backend_techniques),
        "atomic_config_techniques": len(atomic_config_techniques),
        "referenced_union_techniques": len(referenced_techniques),
        "catalog_techniques": len(techniques),
        "atomic_config_only_techniques": sorted(atomic_config_techniques - backend_techniques),
        "referenced_not_in_catalog": sorted(t for t in referenced_techniques if t not in set(techniques)),
    }
    return techniques, referenced_techniques, metadata


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SIGMA_DIR.mkdir(parents=True, exist_ok=True)


def sigma_rule_doc(technique: str, template: dict) -> dict:
    suffix = template["suffix"]
    return {
        "title": f"Generated {technique} {template['title']}",
        "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"seraph.generated.{technique}.{suffix}")),
        "status": "test",
        "description": f"{template['description']} Generated from repository MITRE references for {technique}.",
        "logsource": template["logsource"],
        "detection": template["detection"],
        "level": template["level"],
        "tags": [template["tactic_tag"], f"attack.{technique.lower()}"],
    }


def write_sigma_rules(techniques: list[str]) -> int:
    for old in SIGMA_DIR.glob("*.yml"):
        old.unlink()

    for technique in techniques:
        out_path = SIGMA_DIR / f"{technique.replace('.', '_').lower()}_generated.yml"
        docs = [sigma_rule_doc(technique, template) for template in SIGMA_TEMPLATES]
        with out_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump_all(docs, handle, sort_keys=False)

    return len(techniques) * len(SIGMA_TEMPLATES)


def build_osquery_catalog(techniques: list[str]) -> list[dict]:
    queries: list[dict] = []
    for technique in techniques:
        technique_name = technique.lower().replace(".", "_")
        for template in OSQUERY_TEMPLATES:
            queries.append(
                {
                    "name": f"{technique_name}_{template['suffix']}",
                    "description": f"{template['description']} Technique {technique}.",
                    "sql": template["sql"],
                    "attack_techniques": [technique],
                }
            )
    return queries


def build_soar_execution_seed(_: list[str]) -> list[dict]:
    if not SOAR_ARCHIVE_PATH.exists():
        return []
    try:
        payload = json.loads(SOAR_ARCHIVE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict) and str(row.get("id") or "").strip()]


def validate_generated_artifacts(
    techniques: list[str],
    osquery_catalog: list[dict],
    soar_seed: list[dict],
    metadata: dict,
) -> dict:
    expected_technique_count = int(metadata.get("enterprise_attack_techniques") or len(techniques))
    sigma_expected = len(techniques) * len(SIGMA_TEMPLATES)
    osquery_expected = len(techniques) * len(OSQUERY_TEMPLATES)
    soar_expected = len(soar_seed)

    unique_techniques = len(set(techniques))
    unique_osquery_names = len({str(row.get("name") or "").strip() for row in osquery_catalog})
    unique_soar_ids = len({str(row.get("id") or "").strip() for row in soar_seed})

    validation = {
        "expected_technique_count": expected_technique_count,
        "generated_technique_count": len(techniques),
        "unique_technique_count": unique_techniques,
        "full_catalog_generated": len(techniques) == expected_technique_count,
        "sigma_rules_expected": sigma_expected,
        "osquery_queries_expected": osquery_expected,
        "osquery_queries_generated": len(osquery_catalog),
        "osquery_queries_unique": unique_osquery_names,
        "soar_rows_expected": soar_expected,
        "soar_rows_generated": len(soar_seed),
        "soar_rows_unique": unique_soar_ids,
    }

    problems: list[str] = []
    if unique_techniques != len(techniques):
        problems.append("Technique catalog contains duplicate ATT&CK IDs")
    if len(techniques) != expected_technique_count:
        problems.append(
            f"Technique catalog generated {len(techniques)} ATT&CK IDs but expected {expected_technique_count}"
        )
    if len(osquery_catalog) != osquery_expected or unique_osquery_names != osquery_expected:
        problems.append(
            f"osquery catalog generated {len(osquery_catalog)} rows ({unique_osquery_names} unique), expected {osquery_expected}"
        )
    if unique_soar_ids != len(soar_seed):
        problems.append(
            f"SOAR snapshot generated {len(soar_seed)} rows ({unique_soar_ids} unique)"
        )

    if problems:
        raise RuntimeError("; ".join(problems))

    return validation


def main() -> None:
    ensure_dirs()
    techniques, referenced_techniques, metadata = discover_techniques()
    sigma_count = write_sigma_rules(techniques)
    osquery_catalog = build_osquery_catalog(techniques)
    soar_seed = build_soar_execution_seed(techniques)
    validation = validate_generated_artifacts(techniques, osquery_catalog, soar_seed, metadata)

    QUERY_CATALOG_PATH.write_text(json.dumps(osquery_catalog, indent=2), encoding="utf-8")
    SOAR_EXECUTIONS_PATH.write_text(json.dumps(soar_seed, indent=2), encoding="utf-8")
    TECHNIQUE_CATALOG_PATH.write_text(
        json.dumps(
            {
                "techniques": techniques,
                "catalog_techniques": techniques,
                "referenced_techniques": referenced_techniques,
                "metadata": {
                    **metadata,
                    **validation,
                    "sigma_rules_per_technique": len(SIGMA_TEMPLATES),
                    "osquery_queries_per_technique": len(OSQUERY_TEMPLATES),
                    "soar_rows_per_technique": 0,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "technique_count": len(techniques),
                "catalog_technique_count": len(techniques),
                "referenced_technique_count": len(referenced_techniques),
                "metadata": {
                    **metadata,
                    **validation,
                    "sigma_rules_per_technique": len(SIGMA_TEMPLATES),
                    "osquery_queries_per_technique": len(OSQUERY_TEMPLATES),
                    "soar_rows_per_technique": 0,
                },
                "sigma_rules_written": sigma_count,
                "sigma_files_written": len(techniques),
                "osquery_queries_written": len(osquery_catalog),
                "soar_execution_rows_written": len(soar_seed),
                "sigma_dir": str(SIGMA_DIR),
                "osquery_catalog_path": str(QUERY_CATALOG_PATH),
                "soar_seed_path": str(SOAR_EXECUTIONS_PATH),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
