"""DIO M2 Commercial Metabolism.

M2 begins from a verified Metamorphic Spine M1 parent. Phase M2-0 freezes the
commercial constitution and harvests existing DIO organs before any new
commercial runtime behavior is introduced.
"""

from .constitution import (
    DEFAULT_CONFIG,
    M2_PHASE0_EXIT_TOKEN,
    REQUIRED_ANCHOR_IDS,
    REQUIRED_LAWS,
    CommercialConstitutionError,
    validate_commercial_constitution,
)

__all__ = [
    "DEFAULT_CONFIG",
    "M2_PHASE0_EXIT_TOKEN",
    "REQUIRED_ANCHOR_IDS",
    "REQUIRED_LAWS",
    "CommercialConstitutionError",
    "validate_commercial_constitution",
]
