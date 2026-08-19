"""DIO ATLAS — source-bound universal domain/task map and analogical pivot layer.

ATLAS knowledge is not capability truth. Execution-corroborated coverage must
bind back to exact Metamorphic Registry identities. Similarity and negative
commercial learning may create held pivot hypotheses only.
"""

from .registry import (
    ATLAS_BLOCKED_TOKEN,
    ATLAS_CONFIG_ROOT,
    ATLAS_FOUNDATION_TOKEN,
    AtlasCapabilitySignature,
    AtlasRegistry,
    AtlasRegistryError,
    CANONICAL_WORK_PATTERNS,
    CANDIDATE_WORK_PATTERNS,
    EXPECTED_M1_CAPABILITIES,
    atlas_foundation_receipt,
)
from .pivot import (
    ATLAS_PIVOT_BLOCKED_TOKEN,
    ATLAS_PIVOT_TOKEN,
    AnalogicalResolution,
    AtlasPivotError,
    PivotCandidate,
    atlas_pivot_foundation_receipt,
    compile_negative_learning_pivot,
    evaluate_pivot_gauntlet,
    pivot_candidates,
    resolve_task,
)
from .meta_crosswalk import (
    EXPECTED_PROFILE_CLASS_COUNTS,
    META_CROSSWALK_TOKEN,
    PROFILE_FILE,
    validate_meta_profile_crosswalk,
)

__all__ = [
    "ATLAS_BLOCKED_TOKEN",
    "ATLAS_CONFIG_ROOT",
    "ATLAS_FOUNDATION_TOKEN",
    "ATLAS_PIVOT_BLOCKED_TOKEN",
    "ATLAS_PIVOT_TOKEN",
    "AnalogicalResolution",
    "AtlasCapabilitySignature",
    "AtlasPivotError",
    "AtlasRegistry",
    "AtlasRegistryError",
    "CANONICAL_WORK_PATTERNS",
    "CANDIDATE_WORK_PATTERNS",
    "EXPECTED_M1_CAPABILITIES",
    "EXPECTED_PROFILE_CLASS_COUNTS",
    "META_CROSSWALK_TOKEN",
    "PROFILE_FILE",
    "PivotCandidate",
    "atlas_foundation_receipt",
    "atlas_pivot_foundation_receipt",
    "compile_negative_learning_pivot",
    "evaluate_pivot_gauntlet",
    "pivot_candidates",
    "resolve_task",
    "validate_meta_profile_crosswalk",
]
