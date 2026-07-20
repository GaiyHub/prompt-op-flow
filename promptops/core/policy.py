"""AI 决策策略。"""
from __future__ import annotations

from typing import Any

from promptops.domain.models import PolicyVerdict


DEFAULT_AI_POLICY = {
    "autoAllowed": [
        "connect",
        "evaluate",
        "diff",
        "gate",
        "optimize_patch",
        "plan",
        "status",
    ],
    "requireHumanConfirmation": [
        "submit_feedback",
        "propose_patch",
        "review",
        "publish",
        "accept_drift_as_baseline",
    ],
    "neverAllowed": [
        "delete_production_version",
        "force_publish_without_gate",
    ],
}


def evaluate_action(action: str, human: bool = False) -> PolicyVerdict:
    """评估一个动作是否允许执行。"""
    if action in DEFAULT_AI_POLICY["neverAllowed"]:
        return PolicyVerdict(
            allowed=False,
            reason=f"Action '{action}' is never allowed.",
        )
    if action in DEFAULT_AI_POLICY["requireHumanConfirmation"]:
        if not human:
            return PolicyVerdict(
                allowed=False,
                reason=f"Action '{action}' requires human confirmation.",
                requiresHuman=True,
            )
        return PolicyVerdict(allowed=True, reason="Human confirmed.")
    # autoAllowed 或其他未知动作
    return PolicyVerdict(allowed=True, reason="Auto-allowed.")
