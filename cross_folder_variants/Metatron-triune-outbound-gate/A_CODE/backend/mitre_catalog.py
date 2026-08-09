import json
import os
from pathlib import Path
from typing import Any, Dict


DEFAULT_ENTERPRISE_TECHNIQUE_TOTAL = 691
DEFAULT_ENTERPRISE_PARENT_TOTAL = 216


def load_mitre_catalog_totals() -> Dict[str, Any]:
    catalog_path = Path(
        os.environ.get(
            "MITRE_TECHNIQUE_CATALOG_PATH",
            str(Path(__file__).resolve().parent / "data" / "generated_mitre_techniques.json"),
        )
    )

    env_enterprise_total = int(
        os.environ.get("MITRE_ENTERPRISE_TECHNIQUE_TOTAL", str(DEFAULT_ENTERPRISE_TECHNIQUE_TOTAL))
        or DEFAULT_ENTERPRISE_TECHNIQUE_TOTAL
    )
    env_parent_total = int(
        os.environ.get("MITRE_ENTERPRISE_PARENT_TECHNIQUE_TOTAL", str(DEFAULT_ENTERPRISE_PARENT_TOTAL))
        or DEFAULT_ENTERPRISE_PARENT_TOTAL
    )

    payload: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}
    if catalog_path.exists():
        try:
            payload = json.loads(catalog_path.read_text(encoding="utf-8"))
            metadata = payload.get("metadata") or {}
        except Exception:
            payload = {}
            metadata = {}

    catalog_techniques = payload.get("catalog_techniques") or payload.get("techniques") or []
    enterprise_total = int(
        metadata.get("expected_technique_count")
        or metadata.get("enterprise_attack_techniques")
        or len(catalog_techniques)
        or env_enterprise_total
    )
    parent_total = int(metadata.get("enterprise_attack_parents") or env_parent_total)
    roadmap_total = int(
        os.environ.get("MITRE_ROADMAP_TARGET_TECHNIQUE_TOTAL", str(enterprise_total)) or enterprise_total
    )

    return {
        "catalog_path": str(catalog_path),
        "enterprise_technique_total": enterprise_total,
        "enterprise_parent_total": parent_total,
        "roadmap_target_total": roadmap_total,
    }