"""Academic claim classification and verification helpers for Sophia.

These helpers are deterministic, inspectable, and deliberately conservative.
They improve feedback specificity without turning Sophia into an invisible
author or overclaiming what source evidence proves.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


CLAIM_STANDARDS = {
    "definitional": "Needs a clear construct definition and at least one source or local operational definition.",
    "empirical": "Needs data, method, context, denominator/sample, and limitations.",
    "causal": "Needs design capable of causal inference; otherwise downgrade to association or proposal.",
    "methodological": "Needs procedure, corpus/materials, criteria, and reproducibility/audit details.",
    "normative": "Needs policy/ethical warrant and a stated value criterion.",
    "conceptual": "Needs theoretical warrant, construct boundaries, and competing interpretations.",
    "contribution": "Needs novelty relative to literature/systems plus scope limitation.",
    "comparative": "Needs comparator, metric, and basis for comparison.",
    "table_quantitative": "Needs parsed table cells, row/column anchors, calculation, denominator, and table limitations.",
    "scope_limitation": "Needs precise boundary language and what the evidence does not establish.",
    "unknown": "Needs classification before evidence standard can be applied.",
}


def classify_claim_type(text: str) -> Dict[str, Any]:
    lowered = (text or "").lower()
    rules = [
        ("definitional", r"\b(define[sd]?|definition|means|refers to|is understood as|conceptuali[sz]ed as)\b"),
        ("table_quantitative", r"\b(table|row|column|mean|score|percent|%|n\s*=|increase[sd]? by|decrease[sd]? by|\d+(?:\.\d+)?)\b"),
        ("causal", r"\b(causes?|because of|leads to|results in|drives|produces|improves|reduces|effect of|impact of)\b"),
        ("methodological", r"\b(method|procedure|instrument|coding|analysis|rubric|criteria|corpus|design-based|mixed methods?)\b"),
        ("empirical", r"\b(study|data|dataset|sample|participants|survey|interview|experiment|protocol|results?|findings?|evidence shows)\b"),
        ("normative", r"\b(should|ought|must|ethical|lawful|policy|responsibility|rights?|obligation)\b"),
        ("contribution", r"\b(this paper (?:argues|proposes|develops|contributes)|novel|contribution|adds to|extends)\b"),
        ("comparative", r"\b(more than|less than|better than|worse than|compared with|relative to|whereas|unlike)\b"),
        ("scope_limitation", r"\b(does not establish|limitation|scope|boundary|not generalizable|future work|cannot claim)\b"),
        ("conceptual", r"\b(framework|model|theory|construct|lens|account|interpretation|architecture)\b"),
    ]
    matches = [label for label, pattern in rules if re.search(pattern, lowered)]
    claim_type = matches[0] if matches else "conceptual" if len(lowered.split()) >= 8 else "unknown"
    risk = "high" if claim_type in {"causal", "table_quantitative"} else "medium" if claim_type in {"empirical", "normative", "contribution", "comparative"} else "low"
    return {
        "claim_type": claim_type,
        "secondary_types": [item for item in matches[1:] if item != claim_type][:5],
        "evidence_standard": CLAIM_STANDARDS.get(claim_type, CLAIM_STANDARDS["unknown"]),
        "evidence_risk": risk,
        "integrity_prompt": (
            "Classify the claim, check whether the evidence standard is met, "
            "then scaffold a learner-owned revision rather than writing the final answer."
        ),
    }


def source_quality_rubric(source: Dict[str, Any]) -> Dict[str, Any]:
    """Score source quality with visible dimensions, not a single opaque tier."""
    text = " ".join(str(source.get(key) or "") for key in (
        "citation", "source_name", "title", "container_title", "publisher", "url", "doi", "source_type", "metadata_status"
    )).lower()
    doi = bool(source.get("doi")) or "doi.org" in text
    url = bool(source.get("url")) or "http" in text
    peer = bool(re.search(r"\b(journal|peer[- ]reviewed|doi|scopus|web of science|pubmed|eric|arxiv)\b", text))
    policy = bool(re.search(r"\b(policy|guidance|university|unesco|oecd|government|\.edu|\.gov)\b", text))
    recent = _recency_score(str(source.get("year") or source.get("date") or source.get("published") or ""))
    metadata = sum(1 for key in ("authors", "year", "container_title", "publisher", "pages") if source.get(key)) / 5
    direct_span = bool(str(source.get("exact_span") or source.get("matched_span") or source.get("text") or "").strip())
    relevance = _float(source.get("relevance") or source.get("relevance_score"), default=0.5)
    provenance = 1.0 if doi else 0.85 if url and (peer or policy) else 0.65 if url else 0.45
    authority = 0.95 if peer else 0.85 if policy else 0.65 if url else 0.45
    dimensions = {
        "authority": round(authority, 3),
        "provenance": round(provenance, 3),
        "recency": round(recent, 3),
        "metadata_completeness": round(metadata, 3),
        "direct_span_available": 1.0 if direct_span else 0.25,
        "claim_relevance": round(max(0.0, min(1.0, relevance)), 3),
    }
    weights = {
        "authority": 0.22,
        "provenance": 0.22,
        "recency": 0.14,
        "metadata_completeness": 0.12,
        "direct_span_available": 0.18,
        "claim_relevance": 0.12,
    }
    score = round(sum(dimensions[key] * weights[key] for key in weights), 3)
    if score >= 0.85:
        band = "strong"
    elif score >= 0.7:
        band = "usable"
    elif score >= 0.5:
        band = "fragile"
    else:
        band = "weak"
    return {
        "schema_version": "sophia.source_quality_rubric.v1",
        "score": score,
        "band": band,
        "dimensions": dimensions,
        "weights": weights,
        "source_kind": "scholarly" if peer else "policy_or_institutional" if policy else "web_or_local" if url else "unverified",
        "warnings": [
            warning for warning, active in (
                ("no_doi_or_url", not (doi or url)),
                ("no_direct_span", not direct_span),
                ("metadata_incomplete", metadata < 0.6),
                ("low_claim_relevance", relevance < 0.45),
            )
            if active
        ],
        "integrity_rule": "A source lead is not proof until the exact span supports the claim under the claim's evidence standard.",
    }


def verify_table_claim(claim: str, tables: Dict[str, Any]) -> Dict[str, Any]:
    """Check simple quantitative/table claims against parsed cells."""
    claim_l = (claim or "").lower()
    data_claim = re.sub(r"\b(?:table|figure|fig\.?|appendix)\s+\d+(?:\.\d+)?\b", " ", claim_l)
    claim_numbers = sorted(set(re.findall(r"\b\d+(?:\.\d+)?\b", data_claim)))
    parsed_tables = list((tables or {}).get("tables") or [])
    cell_hits: List[Dict[str, Any]] = []
    for table in parsed_tables:
        for row_index, row in enumerate(table.get("rows") or [], start=1):
            if not isinstance(row, dict):
                continue
            for column, value in row.items():
                value_s = str(value)
                for num in claim_numbers:
                    if re.search(rf"(?<!\d){re.escape(num)}(?!\d)", value_s):
                        cell_hits.append({
                            "source_name": table.get("source_name") or "",
                            "parser": table.get("parser") or "",
                            "row_index": row_index,
                            "column": column,
                            "value": value_s,
                            "matched_number": num,
                        })
    numeric_cells = _numeric_table_cells(parsed_tables)
    calculations = _verify_table_calculations(claim_l, claim_numbers, numeric_cells)
    matched_numbers = sorted({hit["matched_number"] for hit in cell_hits})
    derived_numbers = _supported_derived_claim_numbers(calculations)
    status = "not_table_claim"
    if re.search(r"\b(table|row|column|score|percent|%|increase|decrease|mean|n\s*=|\d)\b", claim_l):
        claim_number_set = set(claim_numbers)
        anchored_or_derived = set(matched_numbers) | derived_numbers
        all_numbers_anchored = bool(claim_numbers) and claim_number_set.issubset(anchored_or_derived)
        calc_needed = bool(calculations)
        calc_supported = bool(calculations) and all(item.get("supported") for item in calculations)
        if calc_needed and not calc_supported:
            status = "table_math_not_supported"
        elif all_numbers_anchored and (not calc_needed or calc_supported):
            status = "table_cells_and_math_support_claim" if calc_needed else "table_cells_support_numbers"
        else:
            status = "table_claim_needs_cell_anchor"
    if claim_numbers and not parsed_tables:
        status = "table_claim_no_parsed_table"
    return {
        "schema_version": "sophia.table_claim_verifier.v1",
        "status": status,
        "claim_numbers": claim_numbers,
        "matched_numbers": matched_numbers,
        "cell_hits": cell_hits[:20],
        "calculation_checks": calculations,
        "tables_considered": len(parsed_tables),
        "integrity_rule": "Do not make or repair quantitative/table claims without visible parsed cells, denominator, and method context.",
    }


def _numeric_table_cells(parsed_tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cells: List[Dict[str, Any]] = []
    for table in parsed_tables:
        rows = table.get("rows") or []
        for row_index, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                continue
            row_label = " ".join(str(value or "") for key, value in row.items() if not _is_number_like(str(value or ""))).lower()
            for column, value in row.items():
                raw = str(value or "")
                number = _parse_number(raw)
                if number is None:
                    continue
                cells.append({
                    "source_name": table.get("source_name") or "",
                    "parser": table.get("parser") or "",
                    "row_index": row_index,
                    "row_label": row_label,
                    "column": str(column),
                    "value": raw,
                    "number": number,
                })
    return cells


def _verify_table_calculations(claim_l: str, claim_numbers: List[str], cells: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    if not cells:
        return checks
    claim_values = [_parse_number(num) for num in claim_numbers]
    claim_values = [num for num in claim_values if num is not None]
    from_to = re.search(r"\bfrom\s+(\d+(?:\.\d+)?)\s+to\s+(\d+(?:\.\d+)?)\b", claim_l)
    point_delta = re.search(
        r"\b(?:(?:by|increase(?:d)? of|decrease(?:d)? of)\s+(\d+(?:\.\d+)?)\s*(?:point|points)|(\d+(?:\.\d+)?)\s*(?:point|points)\s+(?:increase|decrease))\b",
        claim_l,
    )
    percent_delta = re.search(
        r"\b(?:(?:by|increase(?:d)? of|decrease(?:d)? of)\s+(\d+(?:\.\d+)?)\s*(?:%|percent)|(\d+(?:\.\d+)?)\s*(?:%|percent)\s+(?:increase|decrease))\b",
        claim_l,
    )
    if from_to:
        start = float(from_to.group(1))
        end = float(from_to.group(2))
        supported = _has_cell_value(cells, start) and _has_cell_value(cells, end)
        checks.append({
            "type": "from_to_values",
            "expected_start": start,
            "expected_end": end,
            "observed_delta": round(end - start, 4),
            "observed_percent_change": round(((end - start) / start) * 100, 4) if start else None,
            "supported": supported,
            "rationale": "Both from/to values must appear in parsed table cells.",
        })
    if point_delta:
        expected = float(point_delta.group(1) or point_delta.group(2))
        candidate_pairs = _candidate_value_pairs(cells, claim_l)
        matched = [pair for pair in candidate_pairs if _close(abs(pair["delta"]), expected)]
        checks.append({
            "type": "point_delta",
            "expected_delta": expected,
            "matched_pairs": matched[:8],
            "supported": bool(matched),
            "rationale": "Point-change claim must equal the difference between visible parsed cell values.",
        })
    if percent_delta:
        expected = float(percent_delta.group(1) or percent_delta.group(2))
        candidate_pairs = _candidate_value_pairs(cells, claim_l)
        matched = [pair for pair in candidate_pairs if pair.get("percent_change") is not None and _close(abs(float(pair["percent_change"])), expected, tolerance=0.75)]
        checks.append({
            "type": "percent_delta",
            "expected_percent_change": expected,
            "matched_pairs": matched[:8],
            "supported": bool(matched),
            "rationale": "Percent-change claim must match visible parsed cell values within rounding tolerance.",
        })
    return checks


def _supported_derived_claim_numbers(calculations: List[Dict[str, Any]]) -> set[str]:
    derived: set[str] = set()
    for check in calculations:
        if not check.get("supported"):
            continue
        for key in ("expected_delta", "expected_percent_change"):
            if key not in check:
                continue
            value = check.get(key)
            if isinstance(value, (int, float)):
                derived.add(str(int(value)) if float(value).is_integer() else str(value))
    return derived


def _candidate_value_pairs(cells: List[Dict[str, Any]], claim_l: str) -> List[Dict[str, Any]]:
    relevant = [
        cell for cell in cells
        if not any(token in str(cell.get("column") or "").lower() for token in ("n", "sample", "count"))
    ]
    pairs: List[Dict[str, Any]] = []
    for i, left in enumerate(relevant):
        for right in relevant[i + 1:]:
            if left.get("column") != right.get("column"):
                continue
            start = float(left["number"])
            end = float(right["number"])
            delta = end - start
            pairs.append({
                "source_name": right.get("source_name") or left.get("source_name") or "",
                "column": right.get("column") or left.get("column") or "",
                "left_row": left.get("row_label") or f"row {left.get('row_index')}",
                "right_row": right.get("row_label") or f"row {right.get('row_index')}",
                "left_value": start,
                "right_value": end,
                "delta": round(delta, 4),
                "percent_change": round((delta / start) * 100, 4) if start else None,
            })
    if "decrease" in claim_l or "reduced" in claim_l:
        pairs = [{**pair, "delta": -float(pair["delta"])} for pair in pairs]
    return pairs


def _has_cell_value(cells: List[Dict[str, Any]], value: float) -> bool:
    return any(_close(float(cell.get("number") or 0.0), value) for cell in cells)


def _parse_number(value: str) -> Optional[float]:
    match = re.search(r"\d+(?:\.\d+)?", value or "")
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _is_number_like(value: str) -> bool:
    return bool(re.fullmatch(r"\s*\d+(?:\.\d+)?\s*(?:%|percent)?\s*", value or "", flags=re.I))


def _close(left: float, right: float, *, tolerance: float = 0.05) -> bool:
    return abs(left - right) <= tolerance


def _recency_score(value: str) -> float:
    years = [int(year) for year in re.findall(r"\b(19\d{2}|20\d{2})\b", value or "")]
    if not years:
        return 0.5
    latest = max(years)
    if latest >= 2023:
        return 1.0
    if latest >= 2018:
        return 0.82
    if latest >= 2010:
        return 0.62
    return 0.42


def _float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
