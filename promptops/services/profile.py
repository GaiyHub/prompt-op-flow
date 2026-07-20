"""patch 应用服务。"""
from __future__ import annotations

from typing import Any

from promptops.domain.models import PROFILE_SECTIONS, AgentProfile, PatchProposal


def section_value(profile: AgentProfile, section: str) -> Any:
    if section not in PROFILE_SECTIONS:
        raise ValueError(f"Unknown section '{section}'. Must be one of {PROFILE_SECTIONS}")
    return getattr(profile, section)


def clone_profile(profile: AgentProfile) -> AgentProfile:
    return AgentProfile.model_validate(profile.model_dump())


def apply_patch(profile: AgentProfile, patch: PatchProposal) -> AgentProfile:
    """直接替换目标 section，不校验 beforeValue。"""
    data = profile.model_dump()
    data[patch.targetSection] = patch.afterValue
    return AgentProfile.model_validate(data)


def apply_patches(profile: AgentProfile, patches: list[PatchProposal]) -> AgentProfile:
    result = profile
    for p in patches:
        result = apply_patch(result, p)
    return result
