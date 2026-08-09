from backend.services.world_model import WorldModelService


def test_governance_placeholders_are_instance_isolated():
    first = WorldModelService()
    second = WorldModelService()

    first.set_governance_placeholders(
        current_genre_mode="siege",
        current_score_id="score-1",
        current_governance_epoch="epoch-1",
        current_world_state_hash="hash-1",
        strictness_level="strict",
        manifold_ref="manifold-1",
        covenant_ref="covenant-1",
    )

    assert first.get_governance_placeholders()["current_world_state_hash"] == "hash-1"
    assert second.get_governance_placeholders() == {
        "current_genre_mode": None,
        "current_score_id": None,
        "current_governance_epoch": None,
        "current_world_state_hash": None,
        "strictness_level": None,
    }


def test_set_current_world_state_hash_does_not_mutate_other_instances():
    first = WorldModelService()
    second = WorldModelService()

    first.set_current_world_state_hash("hash-a")
    second.set_current_world_state_hash("hash-b")

    assert first.get_current_world_state_hash() == "hash-a"
    assert second.get_current_world_state_hash() == "hash-b"
