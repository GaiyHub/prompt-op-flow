"""评分与 EvalRun 构造。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List

from promptops.adapters.contract import BatchRunResult, EvalSample
from promptops.domain.models import EvalRun, EvalSampleResult
from promptops.util import gen_id, now


class Evaluator(ABC):
    @abstractmethod
    def score(
        self,
        samples: List[EvalSample],
        results: List[BatchRunResult],
    ) -> List[EvalSampleResult]:
        ...


class LocalEvaluator(Evaluator):
    """默认本地打分：判断 output.ok=True 或 missing=[]。"""

    def score(
        self,
        samples: List[EvalSample],
        results: List[BatchRunResult],
    ) -> List[EvalSampleResult]:
        result_map = {r.sampleId: r for r in results}
        scored: List[EvalSampleResult] = []
        for sample in samples:
            r = result_map.get(sample.id)
            if r is None:
                scored.append(EvalSampleResult(
                    sampleId=sample.id, input=sample.input, output=None,
                    passed=False, scores={"accuracy": 0.0},
                    scoringReason="No result returned.",
                ))
                continue
            passed = r.ok and len(r.missing) == 0
            score = 1.0 if passed else 0.0
            scored.append(EvalSampleResult(
                sampleId=sample.id,
                input=sample.input,
                output=r.output,
                passed=passed,
                scores={"accuracy": score},
                scoringReason="Passed." if passed else f"Missing: {r.missing}",
                latencyMs=r.latencyMs,
                costUsd=r.costUsd,
            ))
        return scored


def build_eval_run(
    *,
    change_id: str,
    profile_ref: str,
    suite: str,
    role: str,
    sample_results: List[EvalSampleResult],
) -> EvalRun:
    passed = sum(1 for s in sample_results if s.passed)
    total = len(sample_results)
    pass_rate = passed / total if total > 0 else 0.0

    # 聚合维度分数
    dim_scores: dict[str, list[float]] = {}
    for s in sample_results:
        for dim, val in s.scores.items():
            dim_scores.setdefault(dim, []).append(val)
    dimension_scores = {k: sum(v) / len(v) for k, v in dim_scores.items()}

    total_cost = sum((s.costUsd or 0) for s in sample_results)
    latencies = [s.latencyMs for s in sample_results if s.latencyMs is not None]
    avg_latency = sum(latencies) / len(latencies) if latencies else None

    return EvalRun(
        id=gen_id("eval"),
        changeId=change_id,
        profileRef=profile_ref,
        suite=suite,
        role=role,  # type: ignore
        passRate=pass_rate,
        dimensionScores=dimension_scores,
        samples=sample_results,
        totalCostUsd=total_cost or None,
        avgLatencyMs=avg_latency,
        createdAt=now(),
    )


def compare_runs(
    baseline: EvalRun,
    candidate: EvalRun,
) -> dict[str, Any]:
    """样本对比，输出 improved/regressed/unchanged。"""
    b_map = {s.sampleId: s for s in baseline.samples}
    c_map = {s.sampleId: s for s in candidate.samples}

    improved: list[str] = []
    regressed: list[str] = []
    unchanged: list[str] = []

    for sid in set(b_map) | set(c_map):
        b = b_map.get(sid)
        c = c_map.get(sid)
        if b and c:
            if not b.passed and c.passed:
                improved.append(sid)
            elif b.passed and not c.passed:
                regressed.append(sid)
            else:
                unchanged.append(sid)
        elif c and not b:
            improved.append(sid)
        elif b and not c:
            regressed.append(sid)

    return {
        "improved": improved,
        "regressed": regressed,
        "unchanged": unchanged,
    }
