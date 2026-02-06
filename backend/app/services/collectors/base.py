from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.services.types import NormalizedDocument


class MissingCredentials(Exception):
    pass


class Collector(ABC):
    platform: str

    @abstractmethod
    def collect(self, topic: str, since_datetime: datetime) -> list[NormalizedDocument]:
        raise NotImplementedError

