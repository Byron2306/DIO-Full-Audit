from abc import ABC, abstractmethod
from typing import Any
from backend.arda.ainur.verdicts import AinurVerdict

class AinurInspector(ABC):
    """Abstract base class for all Ainur guardians."""
    name: str

    @abstractmethod
    def inspect(self, context: Any) -> AinurVerdict:
        """Perform recursive constitutional inspection of the given context."""
        raise NotImplementedError
