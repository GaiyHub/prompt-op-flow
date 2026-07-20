"""发布证据完整性校验。"""
from __future__ import annotations

from typing import Any, List

from pydantic import BaseModel

from promptops.domain.models import GateOutcome


class PublishEvidence(BaseModel):
    baseline_eval: Any
    candidate_eval: Any
    diff: Any
    gate_report: Any
    review_decision: Any


class PublishEvidenceCheck(BaseModel):
    ok: bool
    missing: List[str]


def check_publish_evidence(
    evidence: dict[str, Any],
    required_keys: List[str],
) -> PublishEvidenceCheck:
    """检查发布前必需证据是否齐全。"""
    missing = [k for k in required_keys if evidence.get(k) is None]
    return PublishEvidenceCheck(ok=len(missing) == 0, missing=missing)
