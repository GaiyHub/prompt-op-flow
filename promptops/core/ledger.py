"""append-only ledger。"""
from __future__ import annotations

from typing import Any

from promptops.domain.models import PipelineRecord
from promptops.storage.workspace import Workspace
from promptops.util import now


class Ledger:
    def __init__(self, ws: Workspace) -> None:
        self._ws = ws

    def append(
        self,
        change_id: str,
        event: str,
        data: dict[str, Any],
    ) -> None:
        record = PipelineRecord(
            seq=0,  # 由 DB 自增
            changeId=change_id,
            timestamp=now(),
            event=event,
            data=data,
        )
        self._ws.db.append_record(record)

    def history(self, change_id: str) -> list[PipelineRecord]:
        return self._ws.db.all_records(change_id)
