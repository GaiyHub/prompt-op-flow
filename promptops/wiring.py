"""构建 Workspace + AdapterRegistry + Engine。"""
from __future__ import annotations

from promptops.adapters.mock import MockAdapter
from promptops.adapters.registry import AdapterRegistry
from promptops.core.engine import Engine
from promptops.core.template import TemplateResolver, load_config
from promptops.storage.workspace import Workspace


def build_engine(
    workspace_root: str,
    config_path: str | None = None,
) -> Engine:
    """组装 PromptOps Engine。"""
    config = load_config(config_path)
    ws = Workspace(workspace_root)
    adapters = AdapterRegistry()

    # 注册 Mock 适配器
    mock = MockAdapter(workspace_root)
    adapters.register("mock", mock)

    # TODO: 在此处注册 http / shenji 等其他适配器

    resolver = TemplateResolver(config)

    # qodercli 配置：优先环境变量，其次配置文件
    qodercli_binary = config.get("qodercli", {}).get("binary") if config else None

    return Engine(
        ws,
        adapters,
        resolver,
        qodercli_binary=qodercli_binary,
    )
