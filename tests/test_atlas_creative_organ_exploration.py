from pathlib import Path

from atlas.creative_organ_exploration import resolve_creative_organs


ROOT = Path(__file__).resolve().parents[1]


def test_creative_organ_domain_union_is_unique_and_candidate_only():
    result = resolve_creative_organs(ROOT)
    rows = result["domains"]
    counts = result["candidate_domain_counts"]
    assert counts == {"sonoris": 18, "pictora": 22, "shared": 17, "unique_union": 23}
    assert len(rows) == len({row["domain_id"] for row in rows}) == counts["unique_union"]
    assert sum("sonoris" in row["organs"] for row in rows) == counts["sonoris"]
    assert sum("pictora" in row["organs"] for row in rows) == counts["pictora"]
    assert all(row["relation_state"] == "ANALOGICAL_CANDIDATE" for row in rows)
    assert all(not row["execution_corroborated_for_these_organs"] and not row["authority_created"] for row in rows)
    assert result["execution_grade_signature_count_for_these_organs"] == 0
