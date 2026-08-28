from __future__ import annotations

import json
from pathlib import Path

from products.product_explainer_compiler import resolve_product_truth


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _atlas_rows() -> list[dict[str, str]]:
    return [
        {"Suite": "Education & Research", "Incarnation": "HOMS Assess"},
        {"Suite": "Education & Research", "Incarnation": "HOMS Exam"},
        {"Suite": "Education & Research", "Incarnation": "HOMS Moderate"},
        {"Suite": "Education & Research", "Incarnation": "HOMS Curriculum"},
        {"Suite": "Education & Research", "Incarnation": "HOMS Learning Studio"},
        {"Suite": "Education & Research", "Incarnation": "HOMS Accreditation"},
    ]


def test_family_stem_query_aggregates_homs_incarnations(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "state/product_portfolio/DIO_META_PORTFOLIO_ATLAS_IMPORT.json",
        {"schema": "dio.meta_portfolio.import.v1", "incarnations": _atlas_rows()},
    )

    truth = resolve_product_truth("homs", root=tmp_path)

    assert truth["canonical_name"] == "HOMS"
    assert {row["Incarnation"] for row in truth["portfolio_rows"]} == {
        "HOMS Assess",
        "HOMS Exam",
        "HOMS Moderate",
        "HOMS Curriculum",
        "HOMS Learning Studio",
        "HOMS Accreditation",
    }


def test_specific_incarnation_query_remains_singular(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "state/product_portfolio/DIO_META_PORTFOLIO_ATLAS_IMPORT.json",
        {"schema": "dio.meta_portfolio.import.v1", "incarnations": _atlas_rows()},
    )

    truth = resolve_product_truth("HOMS Assess", root=tmp_path)

    assert truth["canonical_name"] == "HOMS Assess"
    assert [row["Incarnation"] for row in truth["portfolio_rows"]] == ["HOMS Assess"]
