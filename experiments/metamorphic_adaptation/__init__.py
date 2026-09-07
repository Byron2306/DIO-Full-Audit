"""DIO Metamorphic Adaptation Gauntlet contracts.

The eight arms form the complete 2×2×2 retained-state design:
S = semantic continuity, M = market/ranking continuity, B = compositional memory.
"""

from __future__ import annotations

ARMS: dict[str, frozenset[str]] = {
    "000": frozenset(),
    "100": frozenset({"S"}),
    "010": frozenset({"M"}),
    "001": frozenset({"B"}),
    "110": frozenset({"S", "M"}),
    "101": frozenset({"S", "B"}),
    "011": frozenset({"M", "B"}),
    "111": frozenset({"S", "M", "B"}),
}

__all__ = ["ARMS"]
