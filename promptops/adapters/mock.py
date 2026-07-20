"""Mock 适配器（离线测试用）。"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from promptops.adapters.contract import (
    BatchRunResult,
    ConnectionStatus,
    EvalSample,
    FetchedProfile,
    PublishOutcome,
    PublishRequest,
    TargetPlatformAdapter,
)
from promptops.domain.models import AgentProfile, RemoteProfile
from promptops.util import now


class MockAdapter(TargetPlatformAdapter):
    """内存 mock 平台适配器。

    run_batch 通过关键词是否在 profile 文本中判定是否通过。
    持久化到 mock-agents.json。
    """

    def __init__(self, workspace_root: str = ".promptops") -> None:
        self._root = workspace_root
        self._agents: Dict[str, Dict[str, Any]] = {}
        self._load()

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------

    def _state_path(self) -> str:
        return os.path.join(self._root, "mock-agents.json")

    def _load(self) -> None:
        path = self._state_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self._agents = json.load(f)

    def _save(self) -> None:
        os.makedirs(self._root, exist_ok=True)
        with open(self._state_path(), "w", encoding="utf-8") as f:
            json.dump(self._agents, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # Seed
    # ------------------------------------------------------------------

    def seed(
        self,
        agent_id: str,
        system_prompt: str = "You are a helpful assistant.",
        user_prompt: Optional[str] = None,
    ) -> None:
        self._agents[agent_id] = {
            "systemPrompt": system_prompt,
            "userPrompt": user_prompt,
            "version": 1,
            "model": {"name": "mock-model"},
            "tools": {},
            "safety": {},
            "outputFormat": {},
        }
        self._save()

    # ------------------------------------------------------------------
    # TargetPlatformAdapter 实现
    # ------------------------------------------------------------------

    def connect(self, platform_agent_id: str) -> ConnectionStatus:
        exists = platform_agent_id in self._agents
        return ConnectionStatus(
            connected=exists,
            platform="mock",
            platformAgentId=platform_agent_id,
            message="OK" if exists else f"Agent '{platform_agent_id}' not seeded.",
        )

    def fetch_profile(self, platform_agent_id: str) -> FetchedProfile:
        data = self._agents.get(platform_agent_id)
        if data is None:
            raise ValueError(f"Mock agent '{platform_agent_id}' not found.")
        normalized = AgentProfile(
            systemPrompt=data["systemPrompt"],
            userPrompt=data.get("userPrompt"),
            model=data.get("model", {}),
            tools=data.get("tools", {}),
            safety=data.get("safety", {}),
            outputFormat=data.get("outputFormat", {}),
        )
        remote = RemoteProfile(
            platform="mock",
            platformAgentId=platform_agent_id,
            raw=data,
            platformVersionId=str(data.get("version", 1)),
            fetchedAt=now(),
        )
        return FetchedProfile(
            normalized=normalized,
            remote=remote,
            platformVersionId=str(data.get("version", 1)),
        )

    def run_batch(
        self,
        platform_agent_id: str,
        samples: List[EvalSample],
        profile_override: Optional[AgentProfile] = None,
    ) -> List[BatchRunResult]:
        data = self._agents.get(platform_agent_id, {})
        profile_text = data.get("systemPrompt", "")
        if data.get("userPrompt"):
            profile_text += " " + data["userPrompt"]

        if profile_override is not None:
            profile_text = profile_override.systemPrompt or ""
            if profile_override.userPrompt:
                profile_text += " " + profile_override.userPrompt

        results: List[BatchRunResult] = []
        for sample in samples:
            ok = True
            missing: List[str] = []
            input_text = str(sample.input).lower()
            profile_lower = profile_text.lower()

            # 判定逻辑：assertions 中的关键词是否出现在 profile 文本
            for assertion in sample.assertions:
                keyword = assertion.lower()
                if keyword not in profile_lower:
                    ok = False
                    missing.append(assertion)

            results.append(
                BatchRunResult(
                    sampleId=sample.id,
                    output={"ok": ok, "missing": missing, "input": input_text},
                    ok=ok,
                    missing=missing,
                )
            )
        return results

    def publish(
        self,
        platform_agent_id: str,
        request: PublishRequest,
    ) -> PublishOutcome:
        if platform_agent_id not in self._agents:
            return PublishOutcome(success=False, error="Agent not found.")
        data = self._agents[platform_agent_id]
        data["systemPrompt"] = request.normalized.systemPrompt
        if request.normalized.userPrompt is not None:
            data["userPrompt"] = request.normalized.userPrompt
        data["version"] = data.get("version", 1) + 1
        self._agents[platform_agent_id] = data
        self._save()
        return PublishOutcome(
            success=True,
            platformVersionId=str(data["version"]),
            platformResponse={"version": data["version"]},
        )
