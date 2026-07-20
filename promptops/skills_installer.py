"""Agent Skill 安装器。

将项目 resources/skills 下的 Skill 复制到通用 skills 目录（~/.agents/skills），
再为目标智能体创建软链到其专有 skills 目录（~/.<agent>/skills）。
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path


DEFAULT_COMMON_SKILLS_DIR = Path.home() / ".agents" / "skills"

KNOWN_AGENT_SKILL_DIRS: dict[str, Path] = {
    "codex": Path.home() / ".codex" / "skills",
    "qoder": Path.home() / ".qoder" / "skills",
    "opencode": Path.home() / ".opencode" / "skills",
    "claude": Path.home() / ".claude" / "skills",
}


def default_agent_skills_dir(agent: str) -> Path:
    """返回智能体默认的 skills 目录。"""
    return KNOWN_AGENT_SKILL_DIRS.get(agent, Path.home() / f".{agent}" / "skills")


def project_skills_dir() -> Path:
    """返回项目内 resources/skills 目录的绝对路径。

    优先使用当前工作目录下的 resources/skills，方便在项目根目录执行命令；
    不存在时回退到安装包所在路径下的 resources/skills。
    """
    cwd_skills = (Path.cwd() / "resources" / "skills").resolve()
    if cwd_skills.exists():
        return cwd_skills
    return (Path(__file__).resolve().parent.parent / "resources" / "skills").resolve()


def discover_skills(source_dir: Path) -> list[str]:
    """发现 source_dir 下所有 Skill 目录（包含 SKILL.md 的子目录）。"""
    if not source_dir.exists():
        return []
    return sorted(
        p.name
        for p in source_dir.iterdir()
        if p.is_dir() and (p / "SKILL.md").exists()
    )


def copy_skill(source: Path, target: Path) -> bool:
    """复制单个 Skill 目录；target 已存在时跳过。返回是否执行了复制。"""
    if target.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
    return True


def link_skill(common_skill: Path, agent_skill: Path) -> bool:
    """为通用 skills 目录中的 Skill 创建软链；已存在时跳过。返回是否创建了软链。"""
    if agent_skill.exists() or agent_skill.is_symlink():
        return False
    agent_skill.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(common_skill, agent_skill)
    return True


def install(
    agent: str,
    *,
    source_dir: Path | None = None,
    common_dir: Path | None = None,
    agent_dir: Path | None = None,
) -> dict[str, list[str]]:
    """安装 Skill。

    参数：
        agent: 目标智能体名称，如 codex / qoder / opencode。
        source_dir: Skill 来源目录，默认项目内 resources/skills。
        common_dir: 通用 skills 目录，默认 ~/.agents/skills。
        agent_dir: 目标智能体 skills 目录，默认 ~/.<agent>/skills。

    返回：
        包含 copied / skipped_copy / linked / skipped_link 的字典。
    """
    source = (source_dir or project_skills_dir()).resolve()
    common = (common_dir or DEFAULT_COMMON_SKILLS_DIR).expanduser().resolve()
    agent_skills = (agent_dir or default_agent_skills_dir(agent)).expanduser().resolve()

    result: dict[str, list[str]] = {
        "copied": [],
        "skipped_copy": [],
        "linked": [],
        "skipped_link": [],
    }

    for name in discover_skills(source):
        src = source / name
        dst_common = common / name
        dst_agent = agent_skills / name

        if copy_skill(src, dst_common):
            result["copied"].append(name)
        else:
            result["skipped_copy"].append(name)

        if link_skill(dst_common, dst_agent):
            result["linked"].append(name)
        else:
            result["skipped_link"].append(name)

    return result
