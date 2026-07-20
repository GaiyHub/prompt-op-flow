"""内容哈希，用于 drift 检测与版本比较。"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def _canonical(obj: Any) -> bytes:
    """将对象转为 canonical JSON bytes（键排序、无多余空格）。"""
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump()
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")


def content_hash(obj: Any) -> str:
    """对对象做 canonical JSON 后取 SHA-256 前 32 位 hex。"""
    return hashlib.sha256(_canonical(obj)).hexdigest()[:32]
