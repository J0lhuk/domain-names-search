from __future__ import annotations

from typing import Protocol

from ..models import AvailabilityResult, HistoryResult, RegistryResult


class RegistryProvider(Protocol):
    async def lookup(self, domain: str) -> RegistryResult: ...


class AvailabilityProvider(Protocol):
    async def check(self, domain: str) -> AvailabilityResult: ...


class HistoryProvider(Protocol):
    async def lookup(self, domain: str) -> HistoryResult: ...
