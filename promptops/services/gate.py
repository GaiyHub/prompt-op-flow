"""gate 编排与默认规则。"""
from __future__ import annotations

from typing import Any, List, Optional

from promptops.domain.models import (
    EvalRun,
    GateIssue,
    GateOutcome,
    GateReport,
    GateRule,
    GateRuleSeverity,
    HumanFeedback,
    IssueEvidence,
    PassedCheck,
    RiskLevel,
    SemanticDiff,
)
from promptops.services.evaluator import compare_runs
from promptops.services.gate_executors.registry import GateExecutorRegistry
from promptops.services.gate_executors.types import GateContext
from promptops.util import gen_id, now


DEFAULT_GATE_RULES = [
    GateRule(
        id="pass_rate",
        type="pass_rate",
        executor="default",
        severity=GateRuleSeverity.blocker,
        stage="candidate",
        params={"max_drop": 0.0},
    ),
    GateRule(
        id="critical_samples",
        type="critical_samples",
        executor="default",
        severity=GateRuleSeverity.blocker,
        stage="candidate",
        params={"sample_ids": []},
    ),
    GateRule(
        id="diff_risk",
        type="diff_risk",
        executor="default",
        severity=GateRuleSeverity.critical,
        stage="candidate",
        params={"max_risk": "high"},
    ),
    GateRule(
        id="manual_feedback",
        type="manual_feedback",
        executor="default",
        severity=GateRuleSeverity.major,
        stage="candidate",
        params={},
    ),
]


def evaluate_gate(
    *,
    change_id: str,
    baseline_eval: Optional[EvalRun],
    candidate_eval: Optional[EvalRun],
    diff: Optional[SemanticDiff],
    feedback: List[HumanFeedback],
    rules: Optional[List[GateRule]] = None,
    stage: str = "candidate",
    executor_registry: Optional[GateExecutorRegistry] = None,
) -> GateReport:
    """按 executor 分组执行规则，汇总 issues 与 passed checks。"""
    if rules is None:
        rules = DEFAULT_GATE_RULES
    registry = executor_registry or GateExecutorRegistry()

    issues: List[GateIssue] = []
    passed_checks: List[PassedCheck] = []
    regressed_samples: List[str] = []
    risks_requiring_confirmation: List[str] = []

    # manual feedback 检查
    negative_feedback = [f for f in feedback if f.severity in ("negative", "high", "critical")]
    if negative_feedback:
        issues.append(GateIssue(
            ruleId="manual_feedback",
            severity=GateRuleSeverity.major,
            message=f"Unresolved negative feedback: {len(negative_feedback)} items.",
            evidences=[IssueEvidence(kind="feedback", detail=f.id) for f in negative_feedback],
        ))
    else:
        passed_checks.append(PassedCheck(ruleId="manual_feedback", message="No unresolved negative feedback."))

    # 执行每条规则
    for rule in rules:
        if rule.id == "manual_feedback":
            continue  # 已在上方处理
        if stage not in rule.stage and rule.stage != "both":
            continue
        ctx = GateContext(
            change_id=change_id,
            baseline_eval=baseline_eval,
            candidate_eval=candidate_eval,
            diff=diff,
            rule=rule,
            stage=stage,
        )
        result = registry.execute(rule.executor, ctx)
        if result.passed:
            passed_checks.append(PassedCheck(ruleId=rule.id, message=result.message))
        else:
            issues.append(GateIssue(
                ruleId=rule.id,
                severity=GateRuleSeverity(result.severity),
                message=result.message,
                evidences=result.evidences,
            ))

    # 收集 regression 样本
    if baseline_eval and candidate_eval:
        regressed_samples = compare_runs(baseline_eval, candidate_eval)["regressed"]

    # 风险确认
    if diff and diff.maxRiskLevel in (RiskLevel.high, RiskLevel.critical):
        risks_requiring_confirmation = [f"{f.section}: {f.kind}" for f in diff.findings if f.riskLevel == diff.maxRiskLevel]

    # 计算 outcome
    blockers = [i for i in issues if i.severity == GateRuleSeverity.blocker]
    if blockers:
        outcome = GateOutcome.blocked
        recommended = f"Resolve {len(blockers)} blocker issue(s)."
    elif issues:
        outcome = GateOutcome.needs_review
        recommended = "Some issues need human review."
    else:
        outcome = GateOutcome.pass_
        recommended = "Ready for review."

    return GateReport(
        id=gen_id("gate"),
        changeId=change_id,
        outcome=outcome,
        issues=issues,
        passedChecks=passed_checks,
        regressedSamples=regressed_samples,
        risksRequiringConfirmation=risks_requiring_confirmation,
        recommendedNextAction=recommended,
        createdAt=now(),
    )
