"""LLMBasedGateExecutor：调用 qodercli 执行自然语言条件规则。"""
from __future__ import annotations

from typing import Any

from promptops.domain.models import IssueEvidence
from promptops.services.gate_executors.types import GateContext, GateRuleResult


class LLMBasedGateExecutor:
    """通过 qodercli 执行自然语言 gate 条件。"""

    def __init__(self, binary: str | None = None) -> None:
        from promptops.services.qoder_cli import QoderCliClient
        self._client = QoderCliClient(binary=binary)

    def execute(self, ctx: GateContext) -> GateRuleResult:
        rule = ctx.rule
        condition = rule.condition or ""
        if not condition:
            return GateRuleResult(
                rule_id=rule.id,
                severity=rule.severity.value,
                passed=True,
                message="No LLM condition provided, skipped.",
                evidences=[],
            )

        context = {
            "change_id": ctx.change_id,
            "stage": ctx.stage,
            "baseline_eval": ctx.baseline_eval.model_dump() if ctx.baseline_eval else None,
            "candidate_eval": ctx.candidate_eval.model_dump() if ctx.candidate_eval else None,
            "diff": ctx.diff.model_dump() if ctx.diff else None,
            "rule_params": rule.params,
        }
        try:
            result = self._client.gate(condition=condition, context=context)
        except Exception as exc:
            return GateRuleResult(
                rule_id=rule.id,
                severity=rule.severity.value,
                passed=False,
                message=f"LLM gate execution failed: {exc}",
                evidences=[IssueEvidence(kind="error", detail=str(exc))],
            )

        raw_evidences = result.get("evidences", [])
        evidences = [
            IssueEvidence(
                kind=e.get("kind", "llm"),
                detail=e.get("detail", ""),
                ref=e.get("ref"),
            )
            for e in raw_evidences
        ]
        return GateRuleResult(
            rule_id=rule.id,
            severity=rule.severity.value,
            passed=bool(result.get("passed", True)),
            message=result.get("message", "LLM gate check completed."),
            evidences=evidences,
        )
