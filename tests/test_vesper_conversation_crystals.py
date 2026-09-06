import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BEAST = REPO_ROOT / "cross_folder_variants" / "EdgeK-BEAST" / "A_CODE"
if str(BEAST) not in sys.path:
    sys.path.insert(0, str(BEAST))

from app.kernel.compute.operator_language import (
    AnswerFrame,
    CandidateMeaning,
    EvidenceBinding,
    MeaningResolutionState,
    OperatorMeaningDomain,
)
from app.kernel.compute.residual_contracts import sha256_digest
from app.kernel.compute.semantic_generalizer import (
    SemanticCrystalRegistry,
    SemanticEpisode,
    SemanticGeneralizer,
)
from adapters.lingua.conversation_crystals import resolve_conversation_crystal


def build_registry(path: Path) -> SemanticCrystalRegistry:
    evidence = EvidenceBinding(
        evidence_digest=sha256_digest("public-dio-fact"),
        source="vesper-test",
        world_digest=sha256_digest("public-world"),
        policy_digest=sha256_digest("no-authority"),
        temporal_scope_digest=sha256_digest("current"),
    )
    meaning = CandidateMeaning(
        meaning_id="meaning:vesper:what-is-dio",
        domain=OperatorMeaningDomain.SERVICE,
        intent="explain_dio",
        slots={"title": "DIO", "body": "DIO is a governed intelligence orchestration system."},
        evidence=(evidence,),
        resolution_state=MeaningResolutionState.RESOLVED,
        confidence=1.0,
    )
    frame = AnswerFrame(
        frame_id="frame:vesper:what-is-dio",
        meaning_digest=meaning.meaning_digest,
        template_id="vesper_public_fact",
        slots={"title": "DIO", "body": "DIO is a governed intelligence orchestration system."},
        evidence_digests=(evidence.binding_digest,),
        resolution_state=MeaningResolutionState.RESOLVED,
    )
    common = {
        "meaning": meaning,
        "answer_frame": frame,
        "schema_digest": sha256_digest("vesper-schema"),
        "discourse_digest": sha256_digest("public-discourse"),
        "world_digest": sha256_digest("public-world"),
        "capability_digest": sha256_digest("conversation"),
        "evidence_digest": sha256_digest("public-evidence"),
        "policy_digest": sha256_digest("no-authority"),
        "temporal_scope_digest": sha256_digest("current"),
        "verified": True,
        "provider_calls": 1,
    }
    episodes = (
        SemanticEpisode(
            episode_id="episode:1",
            utterance="what is dio",
            verification_evidence_digest=sha256_digest("verification-1"),
            **common,
        ),
        SemanticEpisode(
            episode_id="episode:2",
            utterance="tell me about dio",
            verification_evidence_digest=sha256_digest("verification-2"),
            **common,
        ),
    )
    record = SemanticGeneralizer(minimum_verified_episodes=2).promote_record(
        episodes,
        crystal_id="VESPER-DIO-001",
        verifier_id="vesper-test-verifier",
    )
    registry = SemanticCrystalRegistry(path)
    registry.promote(record)
    return registry


@pytest.fixture
def crystal_path(tmp_path):
    path = tmp_path / "state" / "lingua" / "vesper_conversation_semantic_crystals.jsonl"
    path.parent.mkdir(parents=True)
    build_registry(path)
    return path


def test_active_crystal_reuses_without_provider(tmp_path, crystal_path):
    result = resolve_conversation_crystal(root=tmp_path, text="tell me about dio", registry_path=crystal_path)
    assert result["source"] == "lingua_crystal"
    assert result["provider_called"] is False
    assert result["authority_created"] is False
    assert result["crystal_id"] == "VESPER-DIO-001"


def test_revoked_crystal_is_not_reused(tmp_path, crystal_path):
    registry = SemanticCrystalRegistry(crystal_path)
    registry.load()
    registry.revoke("VESPER-DIO-001", reason="test revocation")
    assert resolve_conversation_crystal(root=tmp_path, text="tell me about dio", registry_path=crystal_path) is None


def test_live_adapter_exposes_no_promotion_function():
    import adapters.lingua.conversation_crystals as module
    assert not hasattr(module, "promote_conversation_crystal")
