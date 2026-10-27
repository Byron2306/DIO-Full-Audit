#!/usr/bin/env python3
from __future__ import annotations

import fnmatch
import json
from pathlib import Path
from typing import Any, Mapping


CLASSIFICATIONS = {
    "retained_proof",
    "redacted_fixture",
    "generated_output",
    "private_operational_state",
}


def load_policy(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != "dio.public_state_policy.v1":
        raise ValueError("Unsupported public-state policy schema.")
    return payload


def classify_path(path: Path, policy: Mapping[str, Any]) -> str | None:
    relative = Path(path).as_posix().lstrip("./")
    for rule in policy.get("rules") or []:
        classification = str(rule.get("classification") or "")
        if classification not in CLASSIFICATIONS:
            raise ValueError(f"Unsupported public-state classification: {classification}")
        if fnmatch.fnmatchcase(relative, str(rule.get("pattern") or "")):
            return classification
    return None
