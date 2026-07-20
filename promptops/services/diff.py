"""文本/结构化/语义差异。"""
from __future__ import annotations

import difflib
from abc import ABC, abstractmethod
from typing import Any, List

from promptops.domain.models import (
    PROFILE_SECTIONS,
    AgentProfile,
    RiskLevel,
    SemanticDiff,
    SemanticDiffFinding,
)
from promptops.util import gen_id, now


# ---------------------------------------------------------------------------
# 文本差异
# ---------------------------------------------------------------------------

def text_diff(baseline: AgentProfile, candidate: AgentProfile) -> str:
    """行级文本差异（unified diff）。"""
    b_text = baseline.systemPrompt or ""
    c_text = candidate.systemPrompt or ""
    lines = list(difflib.unified_diff(
        b_text.splitlines(keepends=True),
        c_text.splitlines(keepends=True),
        fromfile="baseline/systemPrompt",
        tofile="candidate/systemPrompt",
    ))
    # userPrompt
    b_up = baseline.userPrompt or ""
    c_up = candidate.userPrompt or ""
    if b_up != c_up:
        lines.extend(difflib.unified_diff(
            b_up.splitlines(keepends=True),
            c_up.splitlines(keepends=True),
            fromfile="baseline/userPrompt",
            tofile="candidate/userPrompt",
        ))
    return "".join(lines)


# ---------------------------------------------------------------------------
# 结构化差异
# ---------------------------------------------------------------------------

def structured_diff(
    baseline: AgentProfile,
    candidate: AgentProfile,
) -> dict[str, dict[str, Any]]:
    """仅返回变化 section 的 before/after。"""
    result: dict[str, dict[str, Any]] = {}
    for section in PROFILE_SECTIONS:
        b_val = getattr(baseline, section)
        c_val = getattr(candidate, section)
        if b_val != c_val:
            result[section] = {"before": b_val, "after": c_val}
    return result


# ---------------------------------------------------------------------------
# 语义风险分析（启发式）
# ---------------------------------------------------------------------------

_RISK_KEYWORDS = {
    "high": ["delete", "remove", "ignore", "skip", "disable", "override"],
    "medium": ["change", "modify", "replace", "update", "rewrite"],
    "low": ["add", "append", "extend", "include"],
}


def analyze_semantics(
    baseline: AgentProfile,
    candidate: AgentProfile,
) -> list[SemanticDiffFinding]:
    """启发式语义风险分析。"""
    findings: list[SemanticDiffFinding] = []
    sdiff = structured_diff(baseline, candidate)
    for section, change in sdiff.items():
        before_text = str(change.get("before", ""))
        after_text = str(change.get("after", ""))

        # 检测删除的行
        removed_lines = set(before_text.splitlines()) - set(after_text.splitlines())
        added_lines = set(after_text.splitlines()) - set(before_text.splitlines())

        risk = RiskLevel.low
        kind = "modification"

        for line in removed_lines:
            lower = line.lower()
            for kw in _RISK_KEYWORDS["high"]:
                if kw in lower:
                    risk = RiskLevel.high
                    kind = "removal_with_risk_keyword"
                    break
            if risk == RiskLevel.high:
                break

        if risk == RiskLevel.low and len(removed_lines) > len(added_lines):
            risk = RiskLevel.medium
            kind = "net_removal"

        if section == "systemPrompt" and risk != RiskLevel.low:
            # systemPrompt 变更提升风险
            if risk == RiskLevel.medium:
                risk = RiskLevel.high

        findings.append(SemanticDiffFinding(
            section=section,
            kind=kind,
            description=f"{len(removed_lines)} lines removed, {len(added_lines)} lines added in {section}.",
            riskLevel=risk,
        ))
    return findings


# ---------------------------------------------------------------------------
# 聚合
# ---------------------------------------------------------------------------

def build_semantic_diff(
    *,
    change_id: str,
    agent_id: str | None,
    baseline: AgentProfile,
    candidate: AgentProfile,
    baseline_ref: str,
    candidate_ref: str,
    findings: list[SemanticDiffFinding] | None = None,
) -> SemanticDiff:
    if findings is None:
        findings = analyze_semantics(baseline, candidate)
    max_risk = RiskLevel.low
    for f in findings:
        levels = [RiskLevel.low, RiskLevel.medium, RiskLevel.high, RiskLevel.critical]
        if levels.index(f.riskLevel) > levels.index(max_risk):
            max_risk = f.riskLevel
    return SemanticDiff(
        id=gen_id("diff"),
        changeId=change_id,
        agentId=agent_id,
        baselineRef=baseline_ref,
        candidateRef=candidate_ref,
        textDiff=text_diff(baseline, candidate),
        structuredDiff=structured_diff(baseline, candidate),
        findings=findings,
        maxRiskLevel=max_risk,
        createdAt=now(),
    )


# ---------------------------------------------------------------------------
# Markdown 渲染
# ---------------------------------------------------------------------------

def render_diff_markdown(diff: SemanticDiff) -> str:
    lines = [
        "# 语义差异报告\n",
        f"- **Change ID**: {diff.changeId}",
        f"- **最高风险等级**: {diff.maxRiskLevel.value}",
        f"- **发现数量**: {len(diff.findings)}\n",
        "## 发现\n",
    ]
    for i, f in enumerate(diff.findings, 1):
        lines.append(f"### {i}. [{f.riskLevel.value}] {f.section} - {f.kind}")
        lines.append(f"  {f.description}\n")
    if diff.textDiff:
        lines.append("## 文本差异\n")
        lines.append("```diff")
        lines.append(diff.textDiff)
        lines.append("```")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# DiffAnalyzer 接口
# ---------------------------------------------------------------------------

class DiffAnalyzer(ABC):
    @abstractmethod
    def analyze(
        self,
        baseline: AgentProfile,
        candidate: AgentProfile,
    ) -> list[SemanticDiffFinding]:
        ...


class HeuristicDiffAnalyzer(DiffAnalyzer):
    def analyze(
        self,
        baseline: AgentProfile,
        candidate: AgentProfile,
    ) -> list[SemanticDiffFinding]:
        return analyze_semantics(baseline, candidate)


class QoderCliSemanticDiffAnalyzer(DiffAnalyzer):
    """调用 qodercli 生成语义 findings。"""

    def __init__(self, binary: str | None = None) -> None:
        from promptops.services.qoder_cli import QoderCliClient
        self._client = QoderCliClient(binary=binary)

    def analyze(
        self,
        baseline: AgentProfile,
        candidate: AgentProfile,
    ) -> list[SemanticDiffFinding]:
        return self._client.diff(
            baseline=baseline.model_dump(),
            candidate=candidate.model_dump(),
        )
