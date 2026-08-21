from __future__ import annotations

from pathlib import Path

from products.professional_evidence_native_routes import NATIVE_ENGINE_ROUTES
from scripts.run_hymark_history_source_first import (
    ENGINE_IDENTITY,
    _pack_from_plan,
    _parse_customer_sources,
    _plan_errors,
)


def _source_pack(path: Path) -> Path:
    path.write_text(
        """# Grade 11 History customer source pack

## Source A — political meeting leaflet, 1950s

Locked learner source A.

## Source B — parliamentary speech extract, 1948

Locked learner source B.

## Source C — resistance organisation statement, 1952

Locked learner source C.

### Customer note — provenance controls

- Do not invent authors, dates or provenance.
""",
        encoding="utf-8",
    )
    return path


def _good_plan() -> dict:
    mark_pattern = [4, 6, 6, 6, 8]
    sections = []
    for label in ("Source A", "Source B", "Source C"):
        sections.append(
            {
                "source_label": label,
                "questions": [
                    {
                        "question": f"Use {label} to answer substantive historical question {index}.",
                        "marks": marks,
                        "memo": [
                            f"Specific expected answer point {index} drawn from {label}.",
                            f"Specific acceptable contextual alternative {index} within the supplied topic scope.",
                        ],
                    }
                    for index, marks in enumerate(mark_pattern, 1)
                ],
            }
        )
    return {
        "source_sections": sections,
        "essay": {
            "option_a": "Assess the extent to which organised resistance challenged apartheid policy during the period in the supplied scope.",
            "option_b": "Evaluate the changing methods and significance of resistance to apartheid during the period in the supplied scope.",
            "memo_option_a": [f"Option A substantive point {index}." for index in range(1, 8)],
            "memo_option_b": [f"Option B substantive point {index}." for index in range(1, 8)],
            "marking_guidance": ["Sustained argument.", "Relevant evidence.", "Analysis.", "Logical structure."],
        },
    }


def test_history_native_identity_is_source_first_builder() -> None:
    assert ENGINE_IDENTITY == "scripts.run_hymark_history_source_first.run_builder"
    assert NATIVE_ENGINE_ROUTES["homs_raw_exam"] == ENGINE_IDENTITY


def test_customer_note_is_not_rendered_as_source_c(tmp_path: Path) -> None:
    sources = _parse_customer_sources(_source_pack(tmp_path / "source_pack.md"))
    assert [row["label"] for row in sources] == ["Source A", "Source B", "Source C"]
    assert sources[0]["content"] == "Locked learner source A."
    assert sources[2]["content"] == "Locked learner source C."
    assert "provenance controls" not in sources[2]["content"].casefold()
    assert "do not invent" not in sources[2]["content"].casefold()


def test_plan_gate_refuses_fictional_or_described_missing_visual(tmp_path: Path) -> None:
    sources = _parse_customer_sources(_source_pack(tmp_path / "source_pack.md"))
    fictional = _good_plan()
    fictional["source_sections"][0]["questions"][0]["memo"].append("Professor Example, fictional excerpt based on real historiography.")
    assert any("fictional" in error for error in _plan_errors(fictional, sources))

    invisible_photo = _good_plan()
    invisible_photo["source_sections"][1]["questions"][0]["question"] = "Study the photograph and explain what the image shows."
    assert any("visual" in error for error in _plan_errors(invisible_photo, sources))


def test_pack_locks_sources_and_reconciles_150_marks(tmp_path: Path) -> None:
    sources = _parse_customer_sources(_source_pack(tmp_path / "source_pack.md"))
    request = {
        "grade": 11,
        "total_marks": 150,
        "duration_hours": 2,
    }
    pack = _pack_from_plan(request, sources, _good_plan(), 1)
    assert pack["total_marks"] == 150
    assert sum(question["marks"] for section in pack["sections"] for question in section["questions"]) == 150
    assert sum(item["marks"] for item in pack["rubric"]) == 150
    assert pack["sections"][0]["stimulus"] == "Locked learner source A."
    assert pack["sections"][1]["stimulus"] == "Locked learner source B."
    assert pack["sections"][2]["stimulus"] == "Locked learner source C."
    assert pack["source_lock"]["invented_provenance_allowed"] is False
    assert pack["source_lock"]["described_missing_visual_allowed"] is False
