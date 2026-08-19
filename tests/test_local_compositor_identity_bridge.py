from __future__ import annotations

from adapters.document_studio import local_media_compositor as local_media
from scripts.local_compositor_identity_bridge import install_local_compositor_identity_bridge


def test_two_part_matrix_family_still_resolves_normally() -> None:
    install_local_compositor_identity_bridge()
    product, audience = local_media.resolve_product_audience("HOMS_ASSESS--tutors_publishers")
    assert product["id"] == "HOMS_ASSESS"
    assert audience["id"] == "tutors_publishers"


def test_exact_incarnation_namespace_does_not_become_part_of_audience_id() -> None:
    install_local_compositor_identity_bridge()
    product, audience = local_media.resolve_product_audience(
        "HOMS_ASSESS--HOMS Assess--tutors_publishers"
    )
    assert product["id"] == "HOMS_ASSESS"
    assert audience["id"] == "tutors_publishers"
    assert audience["name"] == "Tutors and education publishers"


def test_namespaced_identity_can_contain_multiple_middle_lineage_segments() -> None:
    install_local_compositor_identity_bridge()
    product, audience = local_media.resolve_product_audience(
        "HOMS_ASSESS--portfolio--HOMS Assess--tutors_publishers"
    )
    assert product["id"] == "HOMS_ASSESS"
    assert audience["id"] == "tutors_publishers"
