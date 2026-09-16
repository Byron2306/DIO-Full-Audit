from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]

BEAST_CODE_ROOT = (
    REPO_ROOT
    / "cross_folder_variants"
    / "EdgeK-BEAST"
    / "A_CODE"
)


def _beast_api() -> dict[str, Any]:
    if str(BEAST_CODE_ROOT) not in sys.path:
        sys.path.insert(0, str(BEAST_CODE_ROOT))

    from app.kernel.compute.operator_language import (
        MeaningResolutionState,
    )
    from app.kernel.compute.residual_contracts import (
        sha256_digest,
    )

    return {
        "MeaningResolutionState":
            MeaningResolutionState,
        "sha256_digest": sha256_digest,
    }


@dataclass(frozen=True)
class VesperSemanticEpisode:
    """Verified Vesper episode with an externally-built reuse key.

    The reuse key MUST come from CURRENT Vesper semantic context.

    This intentionally prevents BEAST SemanticEpisode from
    recalculating a public-conversation fingerprint using its
    operator-language fingerprint function.

    Semantic learning does not create execution authority.
    """

    episode_id: str
    utterance: str
    meaning: Any
    answer_frame: Any
    reuse_key: Any
    verification_evidence_digest: str
    verified: bool = True
    provider_calls: int = 0
    created_at: str = ""

    def __post_init__(self) -> None:
        api = _beast_api()
        resolved = api[
            "MeaningResolutionState"
        ].RESOLVED

        if not self.episode_id.strip():
            raise ValueError(
                "episode_id must not be empty"
            )

        if not self.utterance.strip():
            raise ValueError(
                "utterance must not be empty"
            )

        if not self.verified:
            raise ValueError(
                "Vesper semantic promotion episodes "
                "must be verified"
            )

        if self.provider_calls < 0:
            raise ValueError(
                "provider_calls must be non-negative"
            )

        if (
            self.meaning.resolution_state
            is not resolved
        ):
            raise ValueError(
                "semantic meaning must be resolved"
            )

        if (
            self.answer_frame.resolution_state
            is not resolved
        ):
            raise ValueError(
                "semantic answer frame must be resolved"
            )

        if (
            self.answer_frame.meaning_digest
            != self.meaning.meaning_digest
        ):
            raise ValueError(
                "answer frame is not bound to meaning"
            )

        if not str(
            self.verification_evidence_digest
        ).startswith("sha256:"):
            raise ValueError(
                "verification evidence must be digest-bound"
            )

        if not self.created_at:
            object.__setattr__(
                self,
                "created_at",
                datetime.now(
                    timezone.utc
                ).isoformat(),
            )

    @property
    def episode_digest(self) -> str:
        digest = _beast_api()["sha256_digest"]

        return digest(
            {
                "schema":
                    "dio.vesper.semantic_episode.v1",
                "episode_id": self.episode_id,
                "utterance": self.utterance,
                "meaning_digest":
                    self.meaning.meaning_digest,
                "answer_frame_digest":
                    self.answer_frame.frame_digest,
                "semantic_match_digest":
                    self.reuse_key.semantic_match_digest,
                "surface_key_digest":
                    self.reuse_key.key_digest,
                "verification_evidence_digest":
                    self.verification_evidence_digest,
                "verified": self.verified,
                "provider_calls":
                    self.provider_calls,
            }
        )
