"""适配器协议与数据对象。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List, Optional

from pydantic import BaseModel, Field

from promptops.domain.models import AgentProfile, RemoteProfile


# ---------------------------------------------------------------------------
# 数据对象
# ---------------------------------------------------------------------------

class ConnectionStatus(BaseModel):
    connected: bool
    platform: str
    platformAgentId: str
    message: str = ""


class EvalSample(BaseModel):
    """评测样本。"""
    id: str
    input: Any
    expected: Optional[Any] = None
    assertions: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    critical: bool = False


class BatchRunResult(BaseModel):
    """单个样本的运行结果。"""
    sampleId: str
    output: Any
    ok: bool = True
    missing: List[str] = Field(default_factory=list)
    latencyMs: Optional[float] = None
    costUsd: Optional[float] = None
    error: Optional[str] = None


class FetchedProfile(BaseModel):
    """从平台拉取后的 profile。"""
    normalized: AgentProfile
    remote: RemoteProfile
    platformVersionId: Optional[str] = None


class PublishRequest(BaseModel):
    normalized: AgentProfile
    remote: RemoteProfile
    note: str = ""


class PublishOutcome(BaseModel):
    success: bool
    platformVersionId: Optional[str] = None
    platformResponse: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# 适配器抽象基类
# ---------------------------------------------------------------------------

class TargetPlatformAdapter(ABC):
    """目标平台适配器协议。"""

    @abstractmethod
    def connect(self, platform_agent_id: str) -> ConnectionStatus:
        """连接平台，验证可用性。"""
        ...

    def fetch_profile(self, platform_agent_id: str) -> FetchedProfile:
        """拉取平台上的 agent profile。"""
        raise NotImplementedError

    def run_batch(
        self,
        platform_agent_id: str,
        samples: List[EvalSample],
        profile_override: Optional[AgentProfile] = None,
    ) -> List[BatchRunResult]:
        """批量运行评测样本。"""
        raise NotImplementedError

    def publish(
        self,
        platform_agent_id: str,
        request: PublishRequest,
    ) -> PublishOutcome:
        """将 profile 发布回平台。"""
        raise NotImplementedError
