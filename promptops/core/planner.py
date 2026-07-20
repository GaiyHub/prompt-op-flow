"""步骤计划：done/ready/blocked。"""
from __future__ import annotations

from typing import Any

from promptops.core.steps import is_interactive
from promptops.domain.models import (
    PipelineTemplate,
    StepDef,
    StepStatus,
    StepType,
)
from promptops.storage.workspace import Workspace


def _step_done(ws: Workspace, change_id: str, step: StepDef) -> bool:
    """判断某个步骤是否已完成（根据已存在的证据）。"""
    db = ws.db
    if step.type == StepType.connect:
        change = db.get_change(change_id)
        return change.sourceVersionId is not None
    elif step.type == StepType.eval:
        role = step.config.get("role", "baseline")
        return db.latest_eval_run(change_id, role) is not None
    elif step.type == StepType.feedback:
        return len(db.all_feedback(change_id)) > 0
    elif step.type == StepType.patch:
        return db.latest_patch(change_id) is not None
    elif step.type == StepType.diff:
        return db.latest_semantic_diff(change_id) is not None
    elif step.type == StepType.gate:
        return db.latest_gate_report(change_id) is not None
    elif step.type == StepType.review:
        return db.latest_review_decision(change_id) is not None
    elif step.type == StepType.publish:
        return db.latest_publish_result(change_id) is not None
    return False


def plan_steps(
    template: PipelineTemplate,
    ws: Workspace,
    change_id: str,
) -> list[dict[str, Any]]:
    """根据模板依赖与已存在证据，计算每个步骤当前状态。"""
    plan: list[dict[str, Any]] = []
    done_ids: set[str] = set()

    for step in template.steps:
        if _step_done(ws, change_id, step):
            done_ids.add(step.id)
            plan.append({
                "id": step.id,
                "type": step.type,
                "status": StepStatus.done,
                "interactive": is_interactive(step.type),
                "depends": step.depends,
                "blocked_by": [],
            })

    # 第二轮：计算 ready/blocked
    for entry in plan:
        if entry["status"] == StepStatus.done:
            continue

    result: list[dict[str, Any]] = []
    for entry in plan:
        if entry["status"] == StepStatus.done:
            result.append(entry)
            continue

        blocked_by = [d for d in entry["depends"] if d not in done_ids]
        if blocked_by:
            status = StepStatus.blocked
        else:
            status = StepStatus.ready

        result.append({
            "id": entry["id"],
            "type": entry["type"],
            "status": status,
            "interactive": entry["interactive"],
            "depends": entry["depends"],
            "blocked_by": blocked_by,
        })
    return result


def auto_runnable(plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """返回可自动执行（ready 且非 interactive）的步骤列表。"""
    return [
        e for e in plan
        if e["status"] == StepStatus.ready and not e["interactive"]
    ]
