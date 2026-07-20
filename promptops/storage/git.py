"""Git CLI 封装（subprocess）。"""
from __future__ import annotations

import os
import subprocess
from typing import Optional


class Git:
    def __init__(self, repo_path: str) -> None:
        self._path = repo_path

    def _run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args],
            cwd=self._path,
            capture_output=True,
            text=True,
            check=check,
        )

    def ensure_repo(self) -> None:
        if not os.path.isdir(os.path.join(self._path, ".git")):
            os.makedirs(self._path, exist_ok=True)
            self._run("init", "-b", "main")
            # 配置 user 以免 commit 失败
            self._run("config", "user.email", "promptops@local", check=False)
            self._run("config", "user.name", "PromptOps", check=False)

    def add_all(self) -> None:
        self._run("add", "-A")

    def commit(self, message: str) -> Optional[str]:
        self.add_all()
        result = self._run("status", "--porcelain")
        if not result.stdout.strip():
            return None  # 没有变更
        result = self._run("commit", "-m", message, check=False)
        if result.returncode != 0:
            return None
        # 获取 commit hash
        rev = self._run("rev-parse", "--short", "HEAD")
        return rev.stdout.strip()
