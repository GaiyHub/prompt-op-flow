"""大对象存储，按 kind 分目录。"""
from __future__ import annotations

import json
import os
from typing import Any

from promptops.util import ensure_dir


class ArtifactStore:
    def __init__(self, root: str) -> None:
        self._root = root
        ensure_dir(root)

    def _dir(self, kind: str) -> str:
        return ensure_dir(os.path.join(self._root, kind))

    def put_json(self, kind: str, data: Any, filename: str | None = None) -> str:
        """存储 JSON 大对象，返回相对路径。"""
        if filename is None:
            import secrets
            filename = secrets.token_hex(8) + ".json"
        path = os.path.join(self._dir(kind), filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        return os.path.relpath(path, self._root)

    def get_json(self, rel_path: str) -> Any:
        path = os.path.join(self._root, rel_path)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
