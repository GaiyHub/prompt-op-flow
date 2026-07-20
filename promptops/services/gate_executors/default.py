"""DefaultGateExecutor：结构化本地规则执行。"""
from __future__ import annotations

from typing import Any, List

from promptops.domain.models import GateRuleSeverity
from promptops.services.evaluator import compare_runs
from promptops.services.gate_executors.types import GateContext, GateRuleResult


class DefaultGateExecutor:
    """本地结构化 gate rule 执行器。"""

    def execute(self, ctx: GateContext) -> GateRuleResult:
        rule = ctx.rule
        rule_id = rule.id
        severity = rule.severity.value
        params = rule.params

        if rule.type == "pass_rate":
            return self._pass_rate(ctx, rule_id, severity, params)
        elif rule.type == "critical_samples":
            return self._critical_samples(ctx, rule_id, severity, params)
        elif rule.type == "latency":
            return self._latency(ctx, rule_id, severity, params)
        elif rule.type == "cost":
            return self._cost(ctx, rule_id, severity, params)
        elif rule.type == "diff_risk":
            return self._diff_risk(ctx, rule_id, severity, params)
        elif rule.type == "manual_feedback":
            return self._manual_feedback(ctx, rule_id, severity, params)
        else:
            return GateRuleResult(
                rule_id=rule_id,
                severity=severity,
                passed=True,
                message=f"Unknown rule type '{rule.type}', skipped.",
                evidences=[],
            )

    def _pass_rate(
        self,
        ctx: GateContext,
        rule_id: str,
        severity: str,
        params: dict[str, Any],
    ) -> GateRuleResult:
        base = ctx.baseline_eval
        cand = ctx.candidate_eval
        if not base or not cand:
            return GateRuleResult(
                rule_id=rule_id,
                severity=severity,
                passed=False,
                message="Missing baseline or candidate eval run.",
                evidences=[],
            )
        drop = base.passRate - cand.passRate
        threshold = params.get("max_drop", 0.0)
        passed = drop <= threshold
        return GateRuleResult(
            rule_id=rule_id,
            severity=severity,
            passed=passed,
            message=(
                f"Pass rate drop {drop:.2%} <= {threshold:.2%}"
                if passed else
                f"Pass rate drop {drop:.2%} > {threshold:.2%}"
            ),
            evidences=[],
        )

    def _critical_samples(
        self,
        ctx: GateContext,
        rule_id: str,
        severity: str,
        params: dict[str, Any],
    ) -> GateRuleResult:
        base = ctx.baseline_eval
        cand = ctx.candidate_eval
        critical_ids = set(params.get("sample_ids", []))
        if not base or not cand:
            return GateRuleResult(
                rule_id=rule_id,
                severity=severity,
                passed=False,
                message="Missing eval runs for critical samples check.",
                evidences=[],
            )
        comparison = compare_runs(base, cand)
        regressed_critical = [sid for sid in comparison["regressed"] if sid in critical_ids]
        passed = len(regressed_critical) == 0
        return GateRuleResult(
            rule_id=rule_id,
            severity=severity,
            passed=passed,
            message=(
                "Critical samples stable."
                if passed else
                f"Critical samples regressed: {regressed_critical}"
            ),
            evidences=[],
        )

    def _latency(
        self,
        ctx: GateContext,
        rule_id: str,
        severity: str,
        params: dict[str, Any],
    ) -> GateRuleResult:
        base = ctx.baseline_eval
        cand = ctx.candidate_eval
        if not base or not cand:
            return GateRuleResult(rule_id=rule_id, severity=severity, passed=False, message="Missing eval runs.", evidences=[])
        b_lat = base.avgLatencyMs or 0
        c_lat = cand.avgLatencyMs or 0
        max_increase = params.get("max_increase", 0.2)
        passed = (c_lat <= b_lat * (1 + max_increase)) if b_lat else True
        return GateRuleResult(
            rule_id=rule_id,
            severity=severity,
            passed=passed,
            message=f"Latency increase {c_lat - b_lat:.1f}ms.",
            evidences=[],
        )

    def _cost(
        self,
        ctx: GateContext,
        rule_id: str,
        severity: str,
        params: dict[str, Any],
    ) -> GateRuleResult:
        base = ctx.baseline_eval
        cand = ctx.candidate_eval
        if not base or not cand:
            return GateRuleResult(rule_id=rule_id, severity=severity, passed=False, message="Missing eval runs.", evidences=[])
        b_cost = base.totalCostUsd or 0
        c_cost = cand.totalCostUsd or 0
        max_increase = params.get("max_increase", 0.2)
        passed = (c_cost <= b_cost * (1 + max_increase)) if b_cost else True
        return GateRuleResult(
            rule_id=rule_id,
            severity=severity,
            passed=passed,
            message=f"Cost increase ${c_cost - b_cost:.4f}.",
            evidences=[],
        )

    def _diff_risk(
        self,
        ctx: GateContext,
        rule_id: str,
        severity: str,
        params: dict[str, Any],
    ) -> GateRuleResult:
        diff = ctx.diff
        max_allowed = params.get("max_risk", "high")
        if not diff:
            return GateRuleResult(rule_id=rule_id, severity=severity, passed=True, message="No diff available.", evidences=[])
        levels = ["low", "medium", "high", "critical"]
        actual = levels.index(diff.maxRiskLevel.value)
        allowed = levels.index(max_allowed)
        passed = actual <= allowed
        return GateRuleResult(
            rule_id=rule_id,
            severity=severity,
            passed=passed,
            message=f"Max risk level {diff.maxRiskLevel.value} <= {max_allowed}.",
            evidences=[],
        )

    def _manual_feedback(
        self,
        ctx: GateContext,
        rule_id: str,
        severity: str,
        params: dict[str, Any],
    ) -> GateRuleResult:
        # manual_feedback 检查在 gate 编排层做，因为需要访问所有 feedback
        return GateRuleResult(
            rule_id=rule_id,
            severity=severity,
            passed=True,
            message="Manual feedback check handled by gate orchestrator.",
            evidences=[],
        )
