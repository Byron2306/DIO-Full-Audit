"""Bounded ContractProof product adapter built on shared DIO runtimes."""

from .proof import compile_portable_room, prepare_disclosure, verify_integrity
from .runner import run_contractproof

__all__ = [
    "compile_portable_room",
    "prepare_disclosure",
    "run_contractproof",
    "verify_integrity",
]
