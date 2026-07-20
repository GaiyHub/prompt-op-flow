"""完整 mock 流水线冒烟测试。"""
from __future__ import annotations

import os
import shutil
import tempfile

import pytest

from promptops.adapters.contract import EvalSample
from promptops.domain.models import ReviewDecisionType
from promptops.fixtures import seed_mock_agent
from promptops.wiring import build_engine


@pytest.fixture
def workspace():
    tmp = tempfile.mkdtemp()
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


async def test_full_pipeline(workspace: str) -> None:
    seed_mock_agent(workspace, "support-agent")
    engine = build_engine(workspace)

    # 1. connect
    result = await engine.connect(
        platform="mock",
        platform_agent_id="support-agent",
        reason="add order number check",
    )
    change_id = result.changeId
    assert result.driftDetected is False
    assert os.path.exists(os.path.join(workspace, "registry", "changes", change_id))

    # 2. baseline eval
    samples = [
        EvalSample(id="order-number-required", input="I want a refund.", assertions=["order number"]),
        EvalSample(id="greeting", input="Hello", assertions=["helpful"]),
    ]
    baseline_run = await engine.evaluate(change_id, samples, role="baseline")
    # support-agent 初始 prompt 不含 "order number"，所以该样本失败
    assert baseline_run.passRate == 0.5

    # 3. optimize patch
    patch = await engine.optimize_patch(change_id)
    assert "order number" in patch.afterValue

    # 4. candidate eval
    candidate_run = await engine.evaluate(change_id, samples, role="candidate")
    assert candidate_run.passRate == 1.0

    # 5. diff
    diff = await engine.diff(change_id)
    assert diff.maxRiskLevel.value in ("low", "medium")

    # 6. gate
    gate = await engine.gate(change_id)
    assert gate.outcome.value == "pass"

    # 7. review
    review = await engine.review(
        change_id,
        decision=ReviewDecisionType.approve,
        reviewer="alice",
        comment="lgtm",
    )
    assert review.decision == ReviewDecisionType.approve

    # 8. publish
    publish = await engine.publish(change_id, publisher="alice")
    assert publish.productionVersionId

    # 9. status
    status = engine.status(change_id)
    assert status["change"]["status"] == "published"
