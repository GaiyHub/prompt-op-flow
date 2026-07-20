"""Drift 检测与 accept-drift 测试。"""
from __future__ import annotations

import json
import os

from promptops.adapters.contract import EvalSample
from promptops.domain.models import ChangeStatus, ReviewDecisionType
from promptops.fixtures import seed_mock_agent
from promptops.wiring import build_engine


async def test_accept_drift_updates_change_in_place():
    workspace = "promptops-test-drift"
    os.makedirs(workspace, exist_ok=True)
    try:
        seed_mock_agent(workspace, "support-agent")
        engine = build_engine(workspace)

        # 1. 连接并创建 baseline
        conn = await engine.connect(
            platform="mock",
            platform_agent_id="support-agent",
            reason="initial connect",
        )
        change_a = conn.changeId
        baseline_v1 = conn.baselineVersionId

        # 2. 提出 patch 并发布，使 remote 进入 production
        await engine.propose_patch(
            change_a,
            section="systemPrompt",
            after="You are a helpful support agent. Ask for the order number.",
            reason="add order number requirement",
        )
        samples = [EvalSample(id="s1", input="refund", assertions=["order number"])]
        await engine.evaluate(change_a, samples, role="baseline")
        await engine.evaluate(change_a, samples, role="candidate")
        await engine.diff(change_a)
        await engine.gate(change_a)
        await engine.review(change_a, decision=ReviewDecisionType.approve, reviewer="alice")
        await engine.publish(change_a, publisher="alice")

        # 3. 外部修改 mock agent profile，模拟线上被其他人改动
        mock_state_path = os.path.join(workspace, "mock-agents.json")
        with open(mock_state_path, "r", encoding="utf-8") as f:
            agents = json.load(f)
        agents["support-agent"]["systemPrompt"] = "You are a helpful support agent. Ask for the order number and email."
        agents["support-agent"]["version"] = agents["support-agent"].get("version", 1) + 1
        with open(mock_state_path, "w", encoding="utf-8") as f:
            json.dump(agents, f, ensure_ascii=False, indent=2)

        # 重新 build engine 以加载新的 mock state
        engine = build_engine(workspace)

        # 4. 再次连接，应该检测到 drift
        conn2 = await engine.connect(
            platform="mock",
            platform_agent_id="support-agent",
            reason="connect after external change",
        )
        change_b = conn2.changeId
        assert conn2.driftDetected is True
        assert conn2.driftEventId is not None

        # 5. accept_drift 应该原地更新 change_b，而不是新建 change
        result = await engine.accept_drift_as_baseline(change_b, actor="alice")
        assert result.changeId == change_b
        assert result.baselineVersionId != conn2.baselineVersionId
        assert result.baselineVersionId != baseline_v1

        change = engine.ws.db.get_change(change_b)
        assert change.status == ChangeStatus.open
        assert change.sourceVersionId == result.baselineVersionId
        assert change.targetVersionId is None

        drift = engine.ws.db.unaccepted_drift(change_b)
        assert drift is None
    finally:
        import shutil
        shutil.rmtree(workspace, ignore_errors=True)
