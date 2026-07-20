"""GateExecutor 注册表。"""
from __future__ import annotations

from typing import Any, Dict

from promptops.services.gate_executors.default import DefaultGateExecutor
from promptops.services.gate_executors.llm import LLMBasedGateExecutor
from promptops.services.gate_executors.types import GateContext, GateRuleResult


class GateExecutorRegistry:
    def __init__(self, qodercli_binary: str | None = None) -> None:
        self._executors: Dict[str, Any] = {
            "default": DefaultGateExecutor(),
            "llm": LLMBasedGateExecutor(binary=qodercli_binary),
        }

    def register(self, name: str, executor: Any) -> None:
        self._executors[name] = executor

    def execute(self, name: str, ctx: GateContext) -> GateRuleResult:
        if name not in self._executors:
            raise KeyError(f"GateExecutor '{name}' not found.")
        return self._executors[name].execute(ctx)
