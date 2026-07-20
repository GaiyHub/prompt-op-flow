"""Demo fixtures。"""
from __future__ import annotations

import json
import os

from promptops.adapters.contract import EvalSample


def demo_samples() -> list[EvalSample]:
    """返回 support-agent 的 demo 评测样本。"""
    return [
        EvalSample(
            id="order-number-required",
            input="I want a refund.",
            expected={"must_ask_order_number": True},
            assertions=["order number"],
            tags=["refund"],
            critical=True,
        ),
        EvalSample(
            id="greeting",
            input="Hello",
            expected={"ok": True},
            assertions=["helpful"],
            tags=["greeting"],
        ),
    ]


def write_demo_samples(path: str) -> None:
    samples = [s.model_dump() for s in demo_samples()]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(samples, f, ensure_ascii=False, indent=2)


def seed_mock_agent(workspace_root: str, agent_id: str = "support-agent") -> None:
    """在 workspace 中 seed mock agent。"""
    from promptops.adapters.mock import MockAdapter
    adapter = MockAdapter(workspace_root)
    adapter.seed(
        agent_id=agent_id,
        system_prompt="You are a helpful customer support agent.",
    )
    write_demo_samples(os.path.join(workspace_root, "demo-samples.json"))
