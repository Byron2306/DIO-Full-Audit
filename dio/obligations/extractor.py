from __future__ import annotations

import re
from typing import Any

from .models import normalize_space, require_source, stable_id


DEONTIC_PATTERN = re.compile(
    r"\b(shall|must|is required to|are required to|will be required to)\b",
    re.IGNORECASE,
)


def extract(source: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract bounded obligation candidates from a source-bound clause list.

    Explicit structured obligations are accepted as candidates. Clauses that are
    not explicitly marked may only become conservative deontic candidates when a
    strong marker is present. Those candidates are always review-required.

    Extraction is not a legal interpretation and does not establish compliance,
    validity, approval, waiver, filing authority, or execution authority.
    """
    source_meta = require_source(source)
    candidates: list[dict[str, Any]] = []

    for index, clause in enumerate(source.get("clauses") or [], start=1):
        if not isinstance(clause, dict):
            raise ValueError(f"clause {index} must be an object")
        clause_id = normalize_space(clause.get("clause_id") or index)
        text = normalize_space(clause.get("text"))
        if not text:
            raise ValueError(f"clause {clause_id} requires text")

        explicit = clause.get("obligation") is True
        deontic = bool(DEONTIC_PATTERN.search(text))
        if not explicit and not deontic:
            continue

        extraction_basis = "explicit_structured_obligation" if explicit else "deontic_candidate"
        review_required = bool(clause.get("review_required", False)) if explicit else True
        obligation_id = stable_id(
            "OBL",
            source_meta["source_id"],
            clause_id,
            text,
        )
        candidates.append(
            {
                "obligation_id": obligation_id,
                "source_locator": clause_id,
                "raw_text": text,
                "extraction_basis": extraction_basis,
                "review_required": review_required,
                "declared": {
                    "statement": normalize_space(clause.get("statement") or text),
                    "kind": normalize_space(clause.get("obligation_kind") or "other"),
                    "responsible_party": normalize_space(clause.get("responsible_party")) or None,
                    "due_at": clause.get("due_at"),
                    "expires_at": clause.get("expires_at"),
                    "dependency_refs": [normalize_space(item) for item in clause.get("dependency_refs") or [] if normalize_space(item)],
                    "evidence_requirements": [normalize_space(item) for item in clause.get("evidence_requirements") or [] if normalize_space(item)],
                    "authority_requirement": normalize_space(clause.get("authority_requirement")) or None,
                },
            }
        )

    return candidates
