"""PromptOps 工具函数。"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone


def gen_id(prefix: str, hex_len: int = 12) -> str:
    """生成 {prefix}_{hex_len位hex} 格式 ID。"""
    return f"{prefix}_{secrets.token_hex(hex_len // 2)}"


def now() -> str:
    """返回当前 UTC ISO-8601 时间字符串。"""
    return datetime.now(timezone.utc).isoformat()


def ensure_dir(path: str) -> str:
    """确保目录存在，返回路径。"""
    os.makedirs(path, exist_ok=True)
    return path
