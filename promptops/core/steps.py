"""Step type 元数据 + 可插拔 registry（evaluator/optimizer/diff）。"""
from __future__ import annotations

from typing import Any, Callable, Dict

from promptops.domain.models import StepType


# ---------------------------------------------------------------------------
# STEP_TYPE_META
# ---------------------------------------------------------------------------

STEP_TYPE_META: dict[StepType, dict[str, Any]] = {
    StepType.connect: {"interactive": False, "summary": "连接平台，生成基线"},
    StepType.eval: {"interactive": False, "summary": "执行评测"},
    StepType.feedback: {"interactive": True, "summary": "人工反馈"},
    StepType.patch: {"interactive": True, "summary": "提交/生成 patch"},
    StepType.diff: {"interactive": False, "summary": "语义差异分析"},
    StepType.gate: {"interactive": False, "summary": "发布卡点评估"},
    StepType.review: {"interactive": True, "summary": "人工审批"},
    StepType.publish: {"interactive": True, "summary": "发布版本"},
}


def is_interactive(step_type: StepType) -> bool:
    return STEP_TYPE_META.get(step_type, {}).get("interactive", False)


# ---------------------------------------------------------------------------
# 通用可插拔 Registry
# ---------------------------------------------------------------------------

class _PluginRegistry:
    def __init__(self, name: str) -> None:
        self._name = name
        self._impls: Dict[str, Any] = {}

    def register(self, impl_name: str, impl: Any) -> None:
        self._impls[impl_name] = impl

    def get(self, impl_name: str | None = None) -> Any:
        if impl_name is None:
            if not self._impls:
                raise ValueError(f"No implementations registered in {self._name}.")
            return next(iter(self._impls.values()))
        if impl_name not in self._impls:
            available = ", ".join(self._impls.keys()) or "(none)"
            raise KeyError(
                f"Implementation '{impl_name}' not found in {self._name}. Available: {available}"
            )
        return self._impls[impl_name]

    def list(self) -> list[str]:
        return list(self._impls.keys())


class EvaluatorRegistry(_PluginRegistry):
    def __init__(self) -> None:
        super().__init__("EvaluatorRegistry")


class OptimizerRegistry(_PluginRegistry):
    def __init__(self) -> None:
        super().__init__("OptimizerRegistry")


class DiffAnalyzerRegistry(_PluginRegistry):
    def __init__(self) -> None:
        super().__init__("DiffAnalyzerRegistry")
