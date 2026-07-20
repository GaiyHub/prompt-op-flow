"""Git-backed 证据文件管理。"""
from __future__ import annotations

import json
import os
from typing import Any

from promptops.storage.git import Git
from promptops.storage.yaml import to_yaml
from promptops.util import ensure_dir


class Registry:
    def __init__(self, root: str) -> None:
        self._root = root
        self._git = Git(root)
        self._git.ensure_repo()

    def _full(self, rel_path: str) -> str:
        return os.path.join(self._root, rel_path)

    def write_yaml(self, rel_path: str, data: Any) -> str:
        path = self._full(rel_path)
        ensure_dir(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as f:
            if hasattr(data, "model_dump"):
                data = data.model_dump()
            f.write(to_yaml(data))
        return path

    def write_json(self, rel_path: str, data: Any) -> str:
        path = self._full(rel_path)
        ensure_dir(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        return path

    def write_text(self, rel_path: str, text: str) -> str:
        path = self._full(rel_path)
        ensure_dir(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def commit(self, message: str) -> str | None:
        return self._git.commit(message)
