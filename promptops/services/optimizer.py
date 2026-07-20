"""优化器接口与实现。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List, Optional

from promptops.domain.models import (
    AgentProfile,
    EvalRun,
    HumanFeedback,
    PatchProposal,
)
from promptops.util import gen_id, now


class OptimizerContext:
    def __init__(
        self,
        *,
        change_id: str,
        baseline_profile: AgentProfile,
        baseline_eval: EvalRun,
        feedback: list[HumanFeedback],
        target_section: str = "systemPrompt",
        background: str = "",
    ) -> None:
        self.change_id = change_id
        self.baseline_profile = baseline_profile
        self.baseline_eval = baseline_eval
        self.feedback = feedback
        self.target_section = target_section
        self.background = background


class PatchProposalInput:
    def __init__(
        self,
        *,
        after_value: Any,
        reason: str,
        expected_improvement: str = "",
        potential_risks: list[str] | None = None,
    ) -> None:
        self.after_value = after_value
        self.reason = reason
        self.expected_improvement = expected_improvement
        self.potential_risks = potential_risks or []


class Optimizer(ABC):
    @abstractmethod
    def optimize(self, ctx: OptimizerContext) -> PatchProposalInput:
        ...


class RuleBasedOptimizer(Optimizer):
    """根据失败样本的 missing 关键词和反馈，在 systemPrompt 末尾追加要求。"""

    def optimize(self, ctx: OptimizerContext) -> PatchProposalInput:
        failed_samples = [s for s in ctx.baseline_eval.samples if not s.passed]
        # 收集所有 missing 关键词
        all_missing: list[str] = []
        for s in failed_samples:
            output = s.output or {}
            if isinstance(output, dict):
                all_missing.extend(output.get("missing", []))

        # 收集反馈
        feedback_texts = [f.expected for f in ctx.feedback]

        additions: list[str] = []
        if ctx.background:
            additions.append(
                "AGENT BACKGROUND AND GOAL: " + ctx.background.strip()
            )
        if all_missing:
            unique = list(dict.fromkeys(all_missing))
            additions.append(
                "IMPORTANT: Ensure the following are addressed: "
                + ", ".join(unique) + "."
            )
        if feedback_texts:
            additions.append(
                "FEEDBACK: " + "; ".join(feedback_texts) + "."
            )

        current = getattr(ctx.baseline_profile, ctx.target_section) or ""
        new_value = current.rstrip()
        for addition in additions:
            new_value += "\n\n" + addition

        return PatchProposalInput(
            after_value=new_value,
            reason=f"Rule-based optimization for {len(failed_samples)} failed samples.",
            expected_improvement=f"Address {len(all_missing)} missing requirements.",
            potential_risks=["Auto-generated text may not perfectly match intent."],
        )


class QoderCliOptimizer(Optimizer):
    """调用本地 qodercli/qoder-cli 二进制优化 prompt。"""

    def __init__(self, binary: str | None = None) -> None:
        from promptops.services.qoder_cli import QoderCliClient
        self._client = QoderCliClient(binary=binary)

    def optimize(self, ctx: OptimizerContext) -> PatchProposalInput:
        current = getattr(ctx.baseline_profile, ctx.target_section) or ""
        failed_samples = [
            {
                "sample_id": s.sampleId,
                "input": s.input,
                "output": s.output,
                "passed": s.passed,
                "scoring_reason": s.scoringReason,
            }
            for s in ctx.baseline_eval.samples if not s.passed
        ]
        feedback = [
            {
                "source": f.source,
                "issue_type": f.issueType,
                "severity": f.severity,
                "expected": f.expected,
                "section": f.section,
                "sample_id": f.sampleId,
            }
            for f in ctx.feedback
        ]
        result = self._client.optimize(
            current_prompt=current,
            section=ctx.target_section,
            failed_samples=failed_samples,
            feedback=feedback,
            background=ctx.background,
        )
        return PatchProposalInput(
            after_value=result["after_value"],
            reason=result["reason"],
            expected_improvement=result["expected_improvement"],
            potential_risks=result["potential_risks"],
        )


class DspyOptimizer(Optimizer):
    """预留 DSPy 优化器实现。"""

    def optimize(self, ctx: OptimizerContext) -> PatchProposalInput:
        raise NotImplementedError("DspyOptimizer is not yet implemented.")


def build_patch_from_optimizer(
    ctx: OptimizerContext,
    opt_input: PatchProposalInput,
    created_by: str = "optimizer",
) -> PatchProposal:
    current = getattr(ctx.baseline_profile, ctx.target_section)
    return PatchProposal(
        id=gen_id("patch"),
        changeId=ctx.change_id,
        targetSection=ctx.target_section,
        beforeValue=current,
        afterValue=opt_input.after_value,
        reason=opt_input.reason,
        linkedFailures=[s.sampleId for s in ctx.baseline_eval.samples if not s.passed],
        expectedImprovement=opt_input.expected_improvement,
        potentialRisks=opt_input.potential_risks,
        source="optimizer",
        createdBy=created_by,
        createdAt=now(),
    )
