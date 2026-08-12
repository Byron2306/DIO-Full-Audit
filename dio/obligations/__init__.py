"""DIO Obligation Core v0.1.

The package is deliberately non-executing. It extracts and normalizes bounded
obligation candidates, identifies deadlines, binds evidence, evaluates
fulfilment state, and projects requirements into Governed Case without creating
authority.
"""

from .engine import (
    CAPABILITY_BINDINGS,
    build,
    project,
    validate_bundle,
)
from .extractor import extract
from .normalizer import normalize
from .deadlines import identify_deadlines
from .evidence import bind_evidence
from .status import evaluate

__all__ = [
    "CAPABILITY_BINDINGS",
    "bind_evidence",
    "build",
    "evaluate",
    "extract",
    "identify_deadlines",
    "normalize",
    "project",
    "validate_bundle",
]
