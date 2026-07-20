"""qodercli 集成测试。"""
from __future__ import annotations

import os
import shutil
import stat
import tempfile

import pytest

from promptops.adapters.contract import EvalSample
from promptops.fixtures import seed_mock_agent
from promptops.services.qoder_cli import QoderCliClient
from promptops.wiring import build_engine


def _make_fake_qodercli(tmpdir: str) -> str:
    """创建一个模拟真实 qodercli 输出格式的脚本。"""
    path = os.path.join(tmpdir, "qodercli")
    script = '''#!/usr/bin/env python3
import json
import sys

# 模拟 qodercli -p --output-format json <prompt>
prompt = sys.argv[-1]

result = {}
if "prompt optimization assistant" in prompt:
    result = {
        "optimized_prompt": prompt.split("Current prompt:")[1].split("---")[0].strip() + "\\n\\n[qodercli] 已针对失败样本优化：请确保满足所有要求。",
        "reason": "Optimized by fake qodercli.",
        "expected_improvement": "Better alignment with requirements.",
        "potential_risks": ["May overfit to failed samples."],
    }
elif "semantic diff analyzer" in prompt:
    result = {
        "findings": [{
            "section": "systemPrompt",
            "kind": "semantic_change",
            "description": "AI-generated semantic finding.",
            "risk_level": "medium",
            "affected_samples": [],
        }]
    }
elif "release gate evaluator" in prompt:
    result = {
        "passed": True,
        "message": "LLM condition satisfied.",
        "evidences": [{"kind": "llm", "detail": "condition check"}],
    }

json.dump({
    "type": "result",
    "subtype": "success",
    "is_error": False,
    "result": json.dumps(result),
}, sys.stdout)
'''
    with open(path, "w", encoding="utf-8") as f:
        f.write(script)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


@pytest.fixture
def qoder_env():
    tmp = tempfile.mkdtemp()
    binary = _make_fake_qodercli(tmp)
    yield tmp, binary
    shutil.rmtree(tmp, ignore_errors=True)


async def test_qodercli_optimizer(qoder_env):
    workspace, binary = qoder_env
    seed_mock_agent(workspace, "support-agent")
    engine = build_engine(workspace)
    engine.qodercli_binary = binary
    engine.optimizer_registry.get("qoder-cli")._client._binary = binary

    result = await engine.connect(
        platform="mock",
        platform_agent_id="support-agent",
        reason="test qodercli",
    )
    change_id = result.changeId

    samples = [
        EvalSample(id="s1", input="test", assertions=["order number"]),
    ]
    await engine.evaluate(change_id, samples, role="baseline")
    patch = await engine.optimize_patch(change_id, implementation="qoder-cli")
    assert "[qodercli]" in patch.afterValue
    assert patch.source == "optimizer"


async def test_qodercli_diff(qoder_env):
    workspace, binary = qoder_env
    seed_mock_agent(workspace, "support-agent")
    engine = build_engine(workspace)
    engine.qodercli_binary = binary
    engine.diff_analyzer_registry.get("qoder-cli")._client._binary = binary

    result = await engine.connect(
        platform="mock",
        platform_agent_id="support-agent",
        reason="test qodercli diff",
    )
    change_id = result.changeId

    await engine.propose_patch(
        change_id,
        section="systemPrompt",
        after="You are a helpful assistant. Ask for order number.",
        reason="test diff",
    )
    diff = await engine.diff(change_id, implementation="qoder-cli")
    assert len(diff.findings) == 1
    assert diff.findings[0].description == "AI-generated semantic finding."


async def test_qodercli_client_call_missing():
    # 当 qodercli 不存在时，调用方法应抛出异常
    client = QoderCliClient(binary="definitely-not-qodercli-xyz")
    with pytest.raises(Exception):
        client.optimize(current_prompt="x", section="systemPrompt", failed_samples=[], feedback=[])
