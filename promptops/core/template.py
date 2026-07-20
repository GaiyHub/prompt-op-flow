"""模板模型、配置加载、DAG 校验。"""
from __future__ import annotations

import os
import re
from typing import Any, Optional

import yaml

from promptops.domain.models import PipelineTemplate, StepDef, StepType


# ---------------------------------------------------------------------------
# DAG 校验
# ---------------------------------------------------------------------------

def validate_dag(template: PipelineTemplate) -> None:
    """检查 id 唯一、依赖存在、无环。"""
    ids = {s.id for s in template.steps}
    if len(ids) != len(template.steps):
        raise ValueError(f"Duplicate step ids in template '{template.id}'.")
    for step in template.steps:
        for dep in step.depends:
            if dep not in ids:
                raise ValueError(
                    f"Step '{step.id}' depends on unknown step '{dep}'."
                )
    # 检测环
    visited: set[str] = set()
    in_stack: set[str] = set()

    def dfs(sid: str) -> None:
        if sid in in_stack:
            raise ValueError(f"Cycle detected at step '{sid}'.")
        if sid in visited:
            return
        in_stack.add(sid)
        step = next(s for s in template.steps if s.id == sid)
        for dep in step.depends:
            dfs(dep)
        in_stack.discard(sid)
        visited.add(sid)

    for s in template.steps:
        dfs(s.id)


def topo_order(template: PipelineTemplate) -> list[str]:
    """拓扑排序，返回步骤执行顺序。"""
    validate_dag(template)
    order: list[str] = []
    visited: set[str] = set()

    def dfs(sid: str) -> None:
        if sid in visited:
            return
        step = next(s for s in template.steps if s.id == sid)
        for dep in step.depends:
            dfs(dep)
        visited.add(sid)
        order.append(sid)

    for s in template.steps:
        dfs(s.id)
    return order


# ---------------------------------------------------------------------------
# 配置加载
# ---------------------------------------------------------------------------

_ENV_RE = re.compile(r"\$\{(\w+)(?::-(.*?))?\}")


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        def _replace(m: re.Match) -> str:
            var, default = m.group(1), m.group(2) or ""
            return os.environ.get(var, default)
        return _ENV_RE.sub(_replace, value)
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


def load_config(config_path: str | None = None) -> dict[str, Any]:
    """加载 promptops.config.yaml，支持 ${ENV_VAR:-default} 展开。"""
    if config_path is None:
        config_path = "promptops.config.yaml"
    if not os.path.exists(config_path):
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return _expand_env(raw)


# ---------------------------------------------------------------------------
# 模板加载
# ---------------------------------------------------------------------------

def load_template(template_id: str, config: dict[str, Any] | None = None) -> Optional[PipelineTemplate]:
    """从内置或配置文件加载模板。"""
    # 内置模板
    from promptops.core.builtins import BUILTIN_TEMPLATES
    if template_id in BUILTIN_TEMPLATES:
        return BUILTIN_TEMPLATES[template_id]

    # 配置文件中引用
    if config and "templates" in config:
        for tdef in config["templates"]:
            if tdef.get("id") == template_id:
                return PipelineTemplate.model_validate(tdef)
    return None


# ---------------------------------------------------------------------------
# Template Resolver
# ---------------------------------------------------------------------------

class TemplateResolver:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}

    def resolve(
        self,
        platform: str,
        agent_id: str,
        template_id: str | None = None,
    ) -> PipelineTemplate:
        tid = template_id
        if tid is None:
            # 从 bindings 查找
            bindings = self._config.get("bindings", {})
            key = f"{platform}:{agent_id}"
            tid = bindings.get(key, bindings.get(platform, "interactive-release"))
        tpl = load_template(tid, self._config)
        if tpl is None:
            raise ValueError(f"Template '{tid}' not found.")
        validate_dag(tpl)
        return tpl


def required_evidence(template: PipelineTemplate) -> list[str]:
    """根据模板步骤计算发布前必需证据字段列表。"""
    evidence: list[str] = []
    for step in template.steps:
        if step.type == StepType.connect:
            continue
        elif step.type == StepType.eval:
            if "baseline" in step.id:
                evidence.append("baseline_eval")
            else:
                evidence.append("candidate_eval")
        elif step.type == StepType.patch:
            evidence.append("candidate_eval")  # patch 产生 candidate
        elif step.type == StepType.diff:
            evidence.append("diff")
        elif step.type == StepType.gate:
            evidence.append("gate_report")
        elif step.type == StepType.review:
            evidence.append("review_decision")
    # 去重并保持顺序
    seen: set[str] = set()
    result: list[str] = []
    for e in evidence:
        if e not in seen:
            seen.add(e)
            result.append(e)
    return result
