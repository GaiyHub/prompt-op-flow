"""适配器注册表。"""
from __future__ import annotations

from typing import Dict

from promptops.adapters.contract import TargetPlatformAdapter


class AdapterRegistry:
    """按 platform name 注册与获取适配器。"""

    def __init__(self) -> None:
        self._adapters: Dict[str, TargetPlatformAdapter] = {}

    def register(self, name: str, adapter: TargetPlatformAdapter) -> None:
        self._adapters[name] = adapter

    def get(self, name: str) -> TargetPlatformAdapter:
        if name not in self._adapters:
            available = ", ".join(self._adapters.keys()) or "(none)"
            raise KeyError(f"Adapter '{name}' not found. Available: {available}")
        return self._adapters[name]

    def list(self) -> list[str]:
        return list(self._adapters.keys())
