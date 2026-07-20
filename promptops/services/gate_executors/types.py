"""Gate 执行器类型与输入。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

from promptops.domain.models import EvalRun, GateRule, RiskLevel, SemanticDiff


@dataclass
class GateContext:
    change_id: str
    baseline_eval: Optional[EvalRun]
    candidate_eval: Optional[EvalRun]
    diff: Optional[SemanticDiff]
    rule: GateRule
    stage: str = "candidate"


@dataclass
class GateRuleResult:
    rule_id: str
    severity: str
    passed: bool
    message: str
    evidences: List[Any]
