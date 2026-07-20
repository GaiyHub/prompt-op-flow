"""PromptOps 全部 Pydantic 领域模型。"""
from __future__ import annotations

from enum import Enum
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 枚举
# ---------------------------------------------------------------------------

class ProfileStatus(str, Enum):
    baseline = "baseline"
    candidate = "candidate"
    production = "production"
    archived = "archived"


class ChangeStatus(str, Enum):
    open = "open"
    in_review = "in_review"
    published = "published"
    rejected = "rejected"
    closed = "closed"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class GateRuleSeverity(str, Enum):
    blocker = "blocker"
    critical = "critical"
    major = "major"
    minor = "minor"
    info = "info"


class GateOutcome(str, Enum):
    pass_ = "pass"
    blocked = "blocked"
    needs_review = "needs_review"


class ReviewDecisionType(str, Enum):
    approve = "approve"
    reject = "reject"
    request_changes = "request_changes"
    approve_with_waiver = "approve_with_waiver"


class StepType(str, Enum):
    connect = "connect"
    eval = "eval"
    feedback = "feedback"
    patch = "patch"
    diff = "diff"
    gate = "gate"
    review = "review"
    publish = "publish"


class StepStatus(str, Enum):
    done = "done"
    ready = "ready"
    blocked = "blocked"


# ---------------------------------------------------------------------------
# Profile 相关
# ---------------------------------------------------------------------------

PROFILE_SECTIONS = [
    "systemPrompt", "userPrompt", "model",
    "tools", "safety", "outputFormat", "metadata",
]


class AgentProfile(BaseModel):
    model_config = {"extra": "ignore"}

    systemPrompt: str = ""
    userPrompt: Optional[str] = None
    model: dict[str, Any] = Field(default_factory=dict)
    tools: dict[str, Any] = Field(default_factory=dict)
    safety: dict[str, Any] = Field(default_factory=dict)
    outputFormat: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RemoteProfile(BaseModel):
    platform: str
    platformAgentId: str
    raw: dict[str, Any]
    platformVersionId: Optional[str] = None
    fetchedAt: str


class AgentProfileVersion(BaseModel):
    id: str
    agentId: str
    status: ProfileStatus
    normalized: AgentProfile
    remote: RemoteProfile
    normalizedHash: str
    remoteHash: str
    platformVersionId: Optional[str] = None
    createdBy: str
    createdAt: str
    changeId: Optional[str] = None


# ---------------------------------------------------------------------------
# Change & Patch
# ---------------------------------------------------------------------------

class PromptProfileChange(BaseModel):
    id: str
    agentId: str
    reason: str
    status: ChangeStatus = ChangeStatus.open
    sourceVersionId: Optional[str] = None
    targetVersionId: Optional[str] = None
    createdBy: str
    createdAt: str
    updatedAt: str


class PatchProposal(BaseModel):
    id: str
    changeId: str
    targetSection: str  # PROFILE_SECTIONS 之一
    beforeValue: Any
    afterValue: Any
    reason: str
    linkedFailures: List[str] = Field(default_factory=list)
    expectedImprovement: str = ""
    potentialRisks: List[str] = Field(default_factory=list)
    suggestedNextScope: List[str] = Field(default_factory=list)
    source: Literal["human_feedback", "optimizer"] = "human_feedback"
    createdBy: str
    createdAt: str


# ---------------------------------------------------------------------------
# Eval
# ---------------------------------------------------------------------------

class EvalSampleResult(BaseModel):
    sampleId: str
    input: Any
    output: Any
    passed: bool
    scores: dict[str, float] = Field(default_factory=dict)
    scoringReason: Optional[str] = None
    traceRef: Optional[str] = None
    toolCallRef: Optional[str] = None
    costUsd: Optional[float] = None
    latencyMs: Optional[float] = None


class EvalRun(BaseModel):
    id: str
    changeId: str
    profileRef: str
    suite: str
    role: Literal["baseline", "candidate"]
    passRate: float
    dimensionScores: dict[str, float] = Field(default_factory=dict)
    samples: List[EvalSampleResult] = Field(default_factory=list)
    totalCostUsd: Optional[float] = None
    avgLatencyMs: Optional[float] = None
    createdAt: str


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

class HumanFeedback(BaseModel):
    id: str
    changeId: str
    source: str
    issueType: str
    severity: str
    expected: str
    section: Optional[str] = None
    sampleId: Optional[str] = None
    createdBy: str
    createdAt: str


# ---------------------------------------------------------------------------
# Semantic Diff
# ---------------------------------------------------------------------------

class SemanticDiffFinding(BaseModel):
    section: str
    kind: str
    description: str
    riskLevel: RiskLevel = RiskLevel.low
    affectedSamples: List[str] = Field(default_factory=list)
    beforeText: Optional[str] = None
    afterText: Optional[str] = None


class SemanticDiff(BaseModel):
    id: str
    changeId: str
    agentId: Optional[str] = None
    baselineRef: str
    candidateRef: str
    textDiff: str = ""
    structuredDiff: dict[str, dict[str, Any]] = Field(default_factory=dict)
    findings: List[SemanticDiffFinding] = Field(default_factory=list)
    maxRiskLevel: RiskLevel = RiskLevel.low
    createdAt: str


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------

class GateRule(BaseModel):
    id: str
    type: str
    executor: str = "default"
    severity: GateRuleSeverity = GateRuleSeverity.major
    stage: str = "candidate"  # candidate | publish | both
    params: dict[str, Any] = Field(default_factory=dict)
    condition: Optional[str] = None


class IssueEvidence(BaseModel):
    kind: str
    detail: str
    ref: Optional[str] = None


class GateIssue(BaseModel):
    ruleId: str
    severity: GateRuleSeverity
    status: Literal["open", "resolved"] = "open"
    message: str
    evidences: List[IssueEvidence] = Field(default_factory=list)


class PassedCheck(BaseModel):
    ruleId: str
    message: str


class GateReport(BaseModel):
    id: str
    changeId: str
    outcome: GateOutcome
    issues: List[GateIssue] = Field(default_factory=list)
    passedChecks: List[PassedCheck] = Field(default_factory=list)
    regressedSamples: List[str] = Field(default_factory=list)
    risksRequiringConfirmation: List[str] = Field(default_factory=list)
    recommendedNextAction: str = ""
    createdAt: str


# ---------------------------------------------------------------------------
# Review & Publish
# ---------------------------------------------------------------------------

class ReviewDecision(BaseModel):
    id: str
    changeId: str
    decision: ReviewDecisionType
    reviewer: str
    comment: str = ""
    waiver: Optional[str] = None
    createdAt: str


class PublishResult(BaseModel):
    id: str
    changeId: str
    publisher: str
    publishedAt: str
    productionVersionId: str
    platformResponse: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Drift
# ---------------------------------------------------------------------------

class DriftEvent(BaseModel):
    id: str
    changeId: str
    agentId: str
    detectedAt: str
    baselineHash: str
    remoteHash: str
    accepted: bool = False
    acceptedBy: Optional[str] = None
    acceptedAt: Optional[str] = None


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class StepDef(BaseModel):
    id: str
    type: StepType
    implementation: str = "default"
    depends: List[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: List[str] = Field(default_factory=list)


class PipelineTemplate(BaseModel):
    id: str
    version: int = 1
    description: str = ""
    steps: List[StepDef] = Field(default_factory=list)


class PipelineRun(BaseModel):
    id: str
    changeId: str
    templateId: str
    status: str = "running"  # running | completed | failed
    startedAt: str
    completedAt: Optional[str] = None


class PipelineStep(BaseModel):
    id: str
    runId: str
    changeId: str
    stepId: str
    stepType: StepType
    status: StepStatus = StepStatus.blocked
    implementation: str = "default"
    startedAt: Optional[str] = None
    completedAt: Optional[str] = None


class PipelineRecord(BaseModel):
    """append-only ledger 记录。"""
    seq: int
    changeId: str
    timestamp: str
    event: str  # step_started | step_completed | action | error
    data: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Engine 辅助返回值
# ---------------------------------------------------------------------------

class ConnectResult(BaseModel):
    changeId: str
    baselineVersionId: str
    driftDetected: bool = False
    driftEventId: Optional[str] = None


class PolicyVerdict(BaseModel):
    allowed: bool
    reason: str = ""
    requiresHuman: bool = False
