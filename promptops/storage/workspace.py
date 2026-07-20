"""Workspace 聚合 db + registry + artifacts。"""
from __future__ import annotations

import os

from promptops.storage.artifacts import ArtifactStore
from promptops.storage.db import SQLiteDB
from promptops.storage.registry import Registry
from promptops.util import ensure_dir


class Workspace:
    def __init__(self, root: str) -> None:
        self.root = os.path.abspath(root)
        ensure_dir(self.root)
        self.db = SQLiteDB(os.path.join(self.root, "state.db"))
        self.registry = Registry(os.path.join(self.root, "registry"))
        self.artifacts = ArtifactStore(os.path.join(self.root, "artifacts"))

    def close(self) -> None:
        self.db.close()
