from __future__ import annotations

from pathlib import Path

from products.site_visual_diversity import audit_suite_visual_diversity, geometry_hash


def _svg(path: Path, *, x: int, fill: str, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'''<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
        <rect x="{x}" y="10" width="40" height="40" fill="{fill}" />
        <text x="10" y="90">{label}</text>
        </svg>''',
        encoding="utf-8",
    )


def _contract() -> dict:
    return {
        "schema": "dio.site_visual_diversity_contract.v1",
        "minimum_unique_geometry_ratio_per_repeated_role": 0.67,
        "maximum_identical_geometry_reuse_per_role": 2,
        "minimum_unique_geometry_ratio_portfolio": 0.67,
        "ignore_svg_elements": ["text", "tspan", "title", "desc"],
        "ignore_svg_attributes": ["fill", "stroke", "style", "class", "id"],
    }


def test_geometry_hash_ignores_palette_and_text_but_not_composition(tmp_path: Path) -> None:
    first = tmp_path / "first.svg"
    second = tmp_path / "second.svg"
    third = tmp_path / "third.svg"
    _svg(first, x=10, fill="#111111", label="Education")
    _svg(second, x=10, fill="#ff0000", label="Trust")
    _svg(third, x=30, fill="#111111", label="Education")

    assert geometry_hash(first, contract=_contract()) == geometry_hash(second, contract=_contract())
    assert geometry_hash(first, contract=_contract()) != geometry_hash(third, contract=_contract())


def test_visual_diversity_refuses_same_geometry_across_suites(tmp_path: Path) -> None:
    root = tmp_path / "svg"
    for suite, fill in (("education", "#111"), ("enterprise", "#222"), ("trust", "#333")):
        _svg(root / suite / "proof.svg", x=10, fill=fill, label=suite)
        _svg(root / suite / "method.svg", x=20, fill=fill, label=suite)

    receipt = audit_suite_visual_diversity(root, contract=_contract())

    assert receipt["visual_diversity_verified"] is False
    assert receipt["role_results"]["proof"]["unique_geometry_count"] == 1
    assert receipt["role_results"]["proof"]["maximum_identical_reuse"] == 3
    assert receipt["acceptance_token"] == "DIO_SITE_VISUAL_DIVERSITY_REFUSED"


def test_visual_diversity_accepts_distinct_suite_compositions(tmp_path: Path) -> None:
    root = tmp_path / "svg"
    for index, suite in enumerate(("education", "enterprise", "trust"), 1):
        _svg(root / suite / "proof.svg", x=10 * index, fill="#111", label=suite)
        _svg(root / suite / "method.svg", x=10 * index + 3, fill="#222", label=suite)

    receipt = audit_suite_visual_diversity(root, contract=_contract())

    assert receipt["visual_diversity_verified"] is True
    assert receipt["role_results"]["proof"]["unique_geometry_count"] == 3
    assert receipt["role_results"]["method"]["unique_geometry_count"] == 3
    assert receipt["acceptance_token"] == "DIO_SITE_VISUAL_DIVERSITY_VERIFIED"
