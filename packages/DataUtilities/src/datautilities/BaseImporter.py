from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypeVar

from data_models.base_record import BaseRecord
from pydantic import ValidationError

T = TypeVar("T", bound=BaseRecord)


class BaseImporter(ABC):
    """Base importer that returns normalized pydantic models."""

    def __init__(self, source_name: str, config: Optional[Dict[str, Any]] = None):
        self.source_name = source_name
        self.config = config or {}

    @abstractmethod
    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch raw records from the source. Return list of dicts (raw rows)."""
        raise NotImplementedError()

    def normalize(self, raw: Dict[str, Any]) -> T:
        pass

    def import_all(self) -> List[T]:
        raw_rows = self.fetch()
        normalized = []
        for r in raw_rows:
            try:
                nr = self.normalize(r)
                normalized.append(nr)
            except (ValidationError, ValueError) as e:
                # In production you might want to log/reject/attach error metadata
                # For now append nothing or attach a special "invalid" record
                print(f"[{self.source_name}] Normalization error for {r}: {e}")
        return normalized
