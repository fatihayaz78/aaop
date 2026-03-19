"""SubModuleRegistry — central registry for log source sub-modules."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.log_analyzer.sub_modules.base_sub_module import BaseSubModule


class SubModuleRegistry:
    _modules: dict[str, type[BaseSubModule]] = {}

    @classmethod
    def register(cls, module_cls: type[BaseSubModule]) -> type[BaseSubModule]:
        cls._modules[module_cls.name] = module_cls
        return module_cls

    @classmethod
    def get(cls, name: str) -> type[BaseSubModule] | None:
        return cls._modules.get(name)

    @classmethod
    def list_all(cls) -> dict[str, type[BaseSubModule]]:
        return dict(cls._modules)


# Import sub-modules to trigger registration
from apps.log_analyzer.sub_modules.akamai import AkamaiSubModule  # noqa: E402, F401
