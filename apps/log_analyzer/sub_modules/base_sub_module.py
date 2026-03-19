"""Abstract base class for all log source sub-modules."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseSubModule(ABC):
    name: str = ""
    display_name: str = ""

    @abstractmethod
    async def configure(self, config: dict) -> None: ...

    @abstractmethod
    async def fetch_logs(self, tenant_id: str, params: dict) -> list[dict]: ...

    @abstractmethod
    async def analyze(self, tenant_id: str, logs: list[dict]) -> dict: ...

    @abstractmethod
    async def generate_report(self, tenant_id: str, analysis: dict) -> str: ...
