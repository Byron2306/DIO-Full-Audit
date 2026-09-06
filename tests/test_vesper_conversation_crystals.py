from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BEAST_CODE_ROOT = REPO_ROOT / "cross_folder_variants" / "EdgeK-BEAST" / "A_CODE"
if str(BEAST_CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(BEAST_CODE_ROOT))

from app.kernel.compute.operator_language import (
    EvidenceBinding,
    OperatorMeaningDomain,
    compile_bounded_meaning,
)
from app.kernel.compute.residual_contracts import sha256_digest
from app.kernel.compute.semantic_generalizer import (
    SemanticCrystalRegistry,
    SemanticEpisode,
    SemanticGeneralizer,
)

from adapters.lingua.conversation_crystals import resolve_conversation_crystal


def _digest(value: str) -> str:
    return sha256_digest(value)


@pytest.fixture
def vesper_crystal_registry(tmp_path):
    registry_path = tmp_path / "state" / "lingua" / "vesper_conversation_semantic_crystals.jsonl"
    world = _digest("public-world")
    policy = _digest("no-authority")
    temporal = _digest("current")
    evidence = EvidenceBinding(
        evidence_digest=_digest("public-evidence"),
        source="public-dio-facts",
        world_digest=world,
        policy_digest=policy,
        temporal_scope_digest=temporal,
    )
    meaning, frame = compile_bounded_meaning(
        meaning_id="meaning:vesper-dio-explain",
        domain=OperatorMeaningDomain.SERVICE,
        intent="explain_dio",
        slots={
            "name": "DIO",
            "status": "available",
            "title": "DIO",
            "body": "DIO is a governed intelligence orchestration system that keeps conversational guidance separate from execution authority.",
        },
        evidence=(evidence,),
        confidence=1.0,
        template_id="vesper.dio.summary.v1",
    )
    common = {
        "meaning": meaning,
        "answer_frame": frame,
        "schema_digest": _digest("vesper-schema"),
        "discourse_digest": _digest("public-discourse"),
        "world_digest": world,
        "capability_digest": _digest("conversation"),
        "evidence_digest": _digest("public-evidence"),
        "policy_digest": policy,
        "temporal_scope_digest": temporal,
        "verified": True,
        "provider_calls": 1,
    }
    episodes = (
        SemanticEpisode(
            episode_id="episode-dio-1",
            utterance="tell me about dio",
            verification_evidence_digest=_digest("verification-1"),
            **common,
        ),
        SemanticEpisode(
            episode_id="episode-dio-2",
            utterance="what is dio",
            verification_evidence_digest=_digest("verification-2"),
            **common,
        ),
    )
    record = SemanticGeneralizer(minimum_verified_episodes=2).promote_record(
        episodes,
        crystal_id="vesper-dio-summary-v1",
        verifier_id="test-verifier",
    )
    SemanticCrystalRegistry(registry_path).promote(record)
    return registry_path


def test_verified_active_crystal_reuses_without_provider(tmp_path, vesper_crystal_registry):
    result = resolve_conversation_crystal(
        root=tmp_path,
        text="please tell me about dio",
        registry_path=vesper_crystal_registry,
    )
    assert result is not None
    assert result["source"] == "lingua_crystal"
    assert result["provider_called"] is False
    assert result["authority_created"] is False
    assert result["crystal_id"] == "vesper-dio-summary-v1"
    assert "execution authority" in result["reply"].lower()


def test_revoked_crystal_is_not_reused(tmp_path, vesper_crystal_registry):
    registry = SemanticCrystalRegistry(vesper_crystal_registry)
    registry.load()
    crystal_id = registry.records()[0].crystal.crystal_id
    registry.revoke(crystal_id, reason="test revocation")
    result = resolve_conversation_crystal(
        root=tmp_path,
        text="tell me about dio",
        registry_path=vesper_crystal_registry,
    )
    assert result is None


def test_missing_registry_returns_none(tmp_path):
    result = resolve_conversation_crystal(root=tmp_path, text="tell me about dio")
    assert result is None


def test_live_adapter_has_no_promotion_surface():
    import adapters.lingua.conversation_crystals as module

    assert not hasattr(module, "promote_conversation_crystal")
