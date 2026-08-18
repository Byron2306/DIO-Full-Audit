from scripts.diagnose_vesper_presence import default_space_url, infer_edge_role


def test_operator_space_name_infers_operator_role() -> None:
    assert infer_edge_role(None, {}, "Byron230686/dio-lilith-operator-wave2") == "operator"


def test_explicit_public_role_wins_over_name_inference() -> None:
    assert infer_edge_role("public", {}, "owner/operator-looking-name") == "public"


def test_standard_hf_space_url_is_derived_from_repo_id() -> None:
    assert default_space_url("Byron230686/dio-lilith-operator-wave2") == (
        "https://byron230686-dio-lilith-operator-wave2.hf.space"
    )


def test_missing_repo_id_has_no_derived_url() -> None:
    assert default_space_url(None) is None
    assert default_space_url("not-a-repo-id") is None
