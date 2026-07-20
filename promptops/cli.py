"""Click CLI，命令入口。"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import click

from promptops.adapters.contract import EvalSample
from promptops.domain.models import ReviewDecisionType
from promptops.fixtures import seed_mock_agent
from promptops.skills_installer import install as install_skills
from promptops.wiring import build_engine


@click.group()
@click.option("-w", "--workspace", default=".promptops", help="Workspace 目录")
@click.option("-c", "--config", default=None, help="配置文件路径")
@click.pass_context
def cli(ctx: click.Context, workspace: str, config: str | None) -> None:
    ctx.ensure_object(dict)
    ctx.obj["workspace"] = workspace
    ctx.obj["config"] = config


# ---------------------------------------------------------------------------
# 工具：获取 engine 并解析样本
# ---------------------------------------------------------------------------

def _engine(ctx: click.Context) -> Any:
    return build_engine(ctx.obj["workspace"], ctx.obj["config"])


def _load_samples(path: str) -> list[EvalSample]:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [EvalSample.model_validate(s) for s in raw]


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# seed
# ---------------------------------------------------------------------------

@cli.command()
@click.option("-a", "--agent", required=True, help="Mock agent ID")
@click.pass_context
def seed(ctx: click.Context, agent: str) -> None:
    """初始化 workspace 并 seed mock agent。"""
    seed_mock_agent(ctx.obj["workspace"], agent)
    click.echo(f"Seeded mock agent '{agent}' in {ctx.obj['workspace']}")


# ---------------------------------------------------------------------------
# connect
# ---------------------------------------------------------------------------

@cli.command()
@click.option("-p", "--platform", required=True, help="平台名称")
@click.option("-a", "--agent", "agent_id", required=True, help="平台 agent ID")
@click.option("-r", "--reason", required=True, help="变更原因")
@click.option("-t", "--template", default=None, help="流水线模板 ID")
@click.pass_context
def connect(ctx: click.Context, platform: str, agent_id: str, reason: str, template: str | None) -> None:
    """连接平台，生成基线。"""
    engine = _engine(ctx)
    result = _run(engine.connect(
        platform=platform,
        platform_agent_id=agent_id,
        reason=reason,
        template=template,
    ))
    click.echo(f"change_id: {result.changeId}")
    click.echo(f"baseline_version_id: {result.baselineVersionId}")
    if result.driftDetected:
        click.echo("drift_detected: true")


# ---------------------------------------------------------------------------
# eval
# ---------------------------------------------------------------------------

@cli.command()
@click.option("-c", "--change", "change_id", required=True, help="Change ID")
@click.option("--role", default="baseline", type=click.Choice(["baseline", "candidate"]))
@click.option("-s", "--samples", required=True, help="评测样本 JSON 文件")
@click.option("--suite", default="default", help="评测 suite 名称")
@click.pass_context
def eval(ctx: click.Context, change_id: str, role: str, samples: str, suite: str) -> None:
    """执行 baseline / candidate 评测。"""
    engine = _engine(ctx)
    sample_list = _load_samples(samples)
    run = _run(engine.evaluate(change_id, sample_list, role=role, suite=suite))
    click.echo(f"eval_run_id: {run.id}")
    click.echo(f"pass_rate: {run.passRate:.2%}")
    click.echo(f"passed: {sum(1 for s in run.samples if s.passed)}/{len(run.samples)}")


# ---------------------------------------------------------------------------
# feedback
# ---------------------------------------------------------------------------

@cli.command()
@click.option("-c", "--change", "change_id", required=True, help="Change ID")
@click.option("--source", default="human", help="反馈来源")
@click.option("--issue-type", default="missing_instruction", help="问题类型")
@click.option("--severity", default="negative", help="严重程度")
@click.option("--expected", required=True, help="期望行为")
@click.option("--section", default=None, help="关联 section")
@click.option("--sample", "sample_id", default=None, help="关联样本 ID")
@click.pass_context
def feedback(
    ctx: click.Context,
    change_id: str,
    source: str,
    issue_type: str,
    severity: str,
    expected: str,
    section: str | None,
    sample_id: str | None,
) -> None:
    """提交结构化人工反馈。"""
    engine = _engine(ctx)
    item = _run(engine.submit_feedback(
        change_id,
        source=source,
        issue_type=issue_type,
        severity=severity,
        expected=expected,
        section=section,
        sample_id=sample_id,
    ))
    click.echo(f"feedback_id: {item.id}")


# ---------------------------------------------------------------------------
# patch
# ---------------------------------------------------------------------------

@cli.command()
@click.option("-c", "--change", "change_id", required=True, help="Change ID")
@click.option("--section", required=True, help="目标 section")
@click.option("--reason", required=True, help="修改原因")
@click.option("--after", required=True, help="修改后的值")
@click.option("--after-file", default=None, help="从文件读取 after")
@click.option("--resolves", default=None, help="解决的失败样本 ID，逗号分隔")
@click.pass_context
def patch(
    ctx: click.Context,
    change_id: str,
    section: str,
    reason: str,
    after: str,
    after_file: str | None,
    resolves: str | None,
) -> None:
    """手动提交 patch。"""
    if after_file:
        with open(after_file, "r", encoding="utf-8") as f:
            after = f.read()
    resolves_list = resolves.split(",") if resolves else []
    engine = _engine(ctx)
    p = _run(engine.propose_patch(
        change_id,
        section=section,
        after=after,
        reason=reason,
        resolves=resolves_list,
    ))
    click.echo(f"patch_id: {p.id}")
    click.echo(f"target_section: {p.targetSection}")


# ---------------------------------------------------------------------------
# optimize
# ---------------------------------------------------------------------------

@cli.command()
@click.option("-c", "--change", "change_id", required=True, help="Change ID")
@click.option("--section", default="systemPrompt", help="目标 section")
@click.option("--impl", default="rule-based", help="优化器实现：rule-based / qoder-cli")
@click.pass_context
def optimize(ctx: click.Context, change_id: str, section: str, impl: str) -> None:
    """用优化器自动生成 patch。"""
    engine = _engine(ctx)
    p = _run(engine.optimize_patch(change_id, section=section, implementation=impl))
    click.echo(f"patch_id: {p.id}")
    click.echo(f"reason: {p.reason}")
    click.echo(f"expected_improvement: {p.expectedImprovement}")


# ---------------------------------------------------------------------------
# diff
# ---------------------------------------------------------------------------

@cli.command()
@click.option("-c", "--change", "change_id", required=True, help="Change ID")
@click.option("--impl", default="heuristic", help="差异分析实现：heuristic / qoder-cli")
@click.pass_context
def diff(ctx: click.Context, change_id: str, impl: str) -> None:
    """生成语义差异报告。"""
    engine = _engine(ctx)
    d = _run(engine.diff(change_id, implementation=impl))
    click.echo(f"diff_id: {d.id}")
    click.echo(f"max_risk_level: {d.maxRiskLevel.value}")
    click.echo(f"findings: {len(d.findings)}")


# ---------------------------------------------------------------------------
# gate
# ---------------------------------------------------------------------------

@cli.command()
@click.option("-c", "--change", "change_id", required=True, help="Change ID")
@click.option("--stage", default="candidate", help="Gate stage")
@click.pass_context
def gate(ctx: click.Context, change_id: str, stage: str) -> None:
    """执行发布卡点。"""
    engine = _engine(ctx)
    report = _run(engine.gate(change_id, stage=stage))
    click.echo(f"gate_report_id: {report.id}")
    click.echo(f"outcome: {report.outcome.value}")
    click.echo(f"issues: {len(report.issues)}")
    click.echo(f"passed_checks: {len(report.passedChecks)}")


# ---------------------------------------------------------------------------
# review
# ---------------------------------------------------------------------------

@cli.command()
@click.option("-c", "--change", "change_id", required=True, help="Change ID")
@click.option("--decision", required=True, type=click.Choice([e.value for e in ReviewDecisionType]))
@click.option("--reviewer", required=True, help="审批人")
@click.option("--comment", default="", help="审批意见")
@click.option("--waiver", default=None, help="waiver 说明（approve_with_waiver 时必填）")
@click.pass_context
def review(ctx: click.Context, change_id: str, decision: str, reviewer: str, comment: str, waiver: str | None) -> None:
    """人工审批。"""
    engine = _engine(ctx)
    rd = _run(engine.review(
        change_id,
        decision=ReviewDecisionType(decision),
        reviewer=reviewer,
        comment=comment,
        waiver=waiver,
    ))
    click.echo(f"review_id: {rd.id}")
    click.echo(f"status: {rd.decision.value}")


# ---------------------------------------------------------------------------
# publish
# ---------------------------------------------------------------------------

@cli.command()
@click.option("-c", "--change", "change_id", required=True, help="Change ID")
@click.option("--publisher", default="human", help="发布人")
@click.pass_context
def publish(ctx: click.Context, change_id: str, publisher: str) -> None:
    """发布候选版本。"""
    engine = _engine(ctx)
    result = _run(engine.publish(change_id, publisher=publisher))
    click.echo(f"published_version_id: {result.productionVersionId}")
    click.echo(f"published_at: {result.publishedAt}")


# ---------------------------------------------------------------------------
# status / plan / advance
# ---------------------------------------------------------------------------

@cli.command()
@click.option("-c", "--change", "change_id", required=True, help="Change ID")
@click.pass_context
def status(ctx: click.Context, change_id: str) -> None:
    """查看变更状态。"""
    engine = _engine(ctx)
    s = engine.status(change_id)
    click.echo(f"change_status: {s['change']['status']}")
    click.echo(f"drift: {s['drift']}")
    click.echo("plan:")
    for p in s["plan"]:
        click.echo(f"  {p['id']:20} {p['status']:10} blocked_by={p['blocked_by']}")


@cli.command()
@click.option("-c", "--change", "change_id", required=True, help="Change ID")
@click.pass_context
def plan(ctx: click.Context, change_id: str) -> None:
    """查看步骤计划。"""
    engine = _engine(ctx)
    for p in engine.plan(change_id):
        click.echo(f"{p['id']:20} {p['status']:10} interactive={p['interactive']} blocked_by={p['blocked_by']}")


@cli.command()
@click.option("-c", "--change", "change_id", required=True, help="Change ID")
@click.pass_context
def advance(ctx: click.Context, change_id: str) -> None:
    """自动推进可执行步骤。"""
    engine = _engine(ctx)
    executed = _run(engine.advance(change_id))
    click.echo(f"executed: {executed}")


# ---------------------------------------------------------------------------
# accept-drift
# ---------------------------------------------------------------------------

@cli.command()
@click.option("-c", "--change", "change_id", required=True, help="Change ID")
@click.option("--actor", default="human", help="执行人")
@click.pass_context
def accept_drift(ctx: click.Context, change_id: str, actor: str) -> None:
    """接受外部漂移为新 baseline。"""
    engine = _engine(ctx)
    result = _run(engine.accept_drift_as_baseline(change_id, actor))
    click.echo(f"new_baseline_version_id: {result.baselineVersionId}")


# ---------------------------------------------------------------------------
# template
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("agent")
@click.option(
    "--skills-dir",
    default=None,
    help="通用 skills 目录，默认 ~/.agents/skills",
)
@click.option(
    "--agent-skills-dir",
    default=None,
    help="目标智能体专有 skills 目录，默认 ~/.<agent>/skills",
)
@click.pass_context
def init(
    ctx: click.Context,
    agent: str,
    skills_dir: str | None,
    agent_skills_dir: str | None,
) -> None:
    """将 resources/skills 下的 Skill 安装到指定智能体。"""
    from pathlib import Path

    result = install_skills(
        agent,
        common_dir=Path(skills_dir) if skills_dir else None,
        agent_dir=Path(agent_skills_dir) if agent_skills_dir else None,
    )

    click.echo(f"agent: {agent}")
    click.echo(f"common_skills_dir: {Path(skills_dir).expanduser().resolve() if skills_dir else '~/.agents/skills'}")
    click.echo(f"agent_skills_dir: {Path(agent_skills_dir).expanduser().resolve() if agent_skills_dir else f'~/.{agent}/skills'}")
    click.echo(f"copied: {len(result['copied'])}")
    for name in result["copied"]:
        click.echo(f"  + {name}")
    click.echo(f"skipped_copy: {len(result['skipped_copy'])}")
    for name in result["skipped_copy"]:
        click.echo(f"  = {name}")
    click.echo(f"linked: {len(result['linked'])}")
    for name in result["linked"]:
        click.echo(f"  + {name}")
    click.echo(f"skipped_link: {len(result['skipped_link'])}")
    for name in result["skipped_link"]:
        click.echo(f"  = {name}")


@cli.group()
def template() -> None:
    """模板管理。"""
    pass


@template.command("list")
@click.pass_context
def template_list(ctx: click.Context) -> None:
    """列出内置模板。"""
    from promptops.core.builtins import BUILTIN_TEMPLATES
    for tid in BUILTIN_TEMPLATES:
        click.echo(tid)


@template.command("show")
@click.option("-t", "--template-id", required=True, help="模板 ID")
@click.pass_context
def template_show(ctx: click.Context, template_id: str) -> None:
    """显示模板详情。"""
    from promptops.core.template import load_template
    tpl = load_template(template_id, load_config(ctx.obj["config"]))
    if tpl is None:
        raise click.UsageError(f"Template '{template_id}' not found.")
    click.echo(f"id: {tpl.id}")
    click.echo(f"description: {tpl.description}")
    click.echo("steps:")
    for s in tpl.steps:
        click.echo(f"  {s.id} ({s.type.value}) depends={s.depends}")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
