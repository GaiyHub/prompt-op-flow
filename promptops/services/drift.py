"""drift 检测。"""
from __future__ import annotations

from typing import Optional

from promptops.domain.hashing import content_hash
from promptops.domain.models import AgentProfileVersion, DriftEvent, RemoteProfile
from promptops.util import gen_id, now


def detect_drift(
    *,
    remote: RemoteProfile,
    latest_production: Optional[AgentProfileVersion],
) -> bool:
    """对比远端 profile 与最近一次发布版本的差异。"""
    if latest_production is None:
        return False
    remote_hash = content_hash(remote.raw)
    prod_hash = latest_production.remoteHash
    return remote_hash != prod_hash


def build_drift_event(
    *,
    change_id: str,
    agent_id: str,
    baseline_hash: str,
    remote_hash: str,
) -> DriftEvent:
    return DriftEvent(
        id=gen_id("drift"),
        changeId=change_id,
        agentId=agent_id,
        detectedAt=now(),
        baselineHash=baseline_hash,
        remoteHash=remote_hash,
    )
