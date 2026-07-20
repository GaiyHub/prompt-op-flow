"""SQLite 持久化（WAL 模式，upsert 语义，JSON 序列化）。"""
from __future__ import annotations

import json
import os
import sqlite3
from typing import Any, Optional

from promptops.domain.models import (
    AgentProfileVersion,
    ChangeStatus,
    DriftEvent,
    EvalRun,
    GateReport,
    HumanFeedback,
    PatchProposal,
    PipelineRecord,
    PipelineRun,
    PipelineStep,
    PromptProfileChange,
    PublishResult,
    ReviewDecision,
    SemanticDiff,
)
from promptops.util import ensure_dir


class SQLiteDB:
    def __init__(self, db_path: str) -> None:
        ensure_dir(os.path.dirname(db_path))
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                platform TEXT,
                platform_agent_id TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS agent_profile_versions (
                id TEXT PRIMARY KEY,
                agent_id TEXT,
                status TEXT,
                data TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS prompt_profile_changes (
                id TEXT PRIMARY KEY,
                agent_id TEXT,
                status TEXT,
                data TEXT,
                created_at TEXT,
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS eval_runs (
                id TEXT PRIMARY KEY,
                change_id TEXT,
                role TEXT,
                data TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS patch_proposals (
                id TEXT PRIMARY KEY,
                change_id TEXT,
                data TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS feedback_items (
                id TEXT PRIMARY KEY,
                change_id TEXT,
                data TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS semantic_diffs (
                id TEXT PRIMARY KEY,
                change_id TEXT,
                data TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS gate_reports (
                id TEXT PRIMARY KEY,
                change_id TEXT,
                data TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS review_decisions (
                id TEXT PRIMARY KEY,
                change_id TEXT,
                data TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS publish_results (
                id TEXT PRIMARY KEY,
                change_id TEXT,
                data TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS drift_events (
                id TEXT PRIMARY KEY,
                change_id TEXT,
                agent_id TEXT,
                accepted INTEGER DEFAULT 0,
                data TEXT,
                detected_at TEXT
            );
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id TEXT PRIMARY KEY,
                change_id TEXT,
                data TEXT,
                started_at TEXT
            );
            CREATE TABLE IF NOT EXISTS pipeline_steps (
                id TEXT PRIMARY KEY,
                run_id TEXT,
                change_id TEXT,
                step_id TEXT,
                status TEXT,
                data TEXT
            );
            CREATE TABLE IF NOT EXISTS pipeline_records (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                change_id TEXT,
                event TEXT,
                data TEXT,
                timestamp TEXT
            );
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # 通用 JSON upsert
    # ------------------------------------------------------------------

    def _upsert(self, table: str, id_val: str, obj: Any, extra: dict[str, Any] | None = None) -> None:
        data = obj.model_dump() if hasattr(obj, "model_dump") else obj
        cols = ["id", "data"]
        vals = [id_val, json.dumps(data, default=str)]
        if extra:
            for k, v in extra.items():
                cols.append(k)
                vals.append(v)
        placeholders = ",".join(["?"] * len(cols))
        col_names = ",".join(cols)
        updates = ",".join([f"{c}=excluded.{c}" for c in cols if c != "id"])
        self._conn.execute(
            f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}",
            vals,
        )
        self._conn.commit()

    def _get(self, table: str, id_val: str, model_cls: type) -> Optional[Any]:
        row = self._conn.execute(f"SELECT data FROM {table} WHERE id=?", (id_val,)).fetchone()
        if row is None:
            return None
        return model_cls.model_validate(json.loads(row["data"]))

    def _latest(self, table: str, change_id: str, model_cls: type, order_col: str = "created_at") -> Optional[Any]:
        row = self._conn.execute(
            f"SELECT data FROM {table} WHERE change_id=? ORDER BY {order_col} DESC LIMIT 1",
            (change_id,),
        ).fetchone()
        if row is None:
            return None
        return model_cls.model_validate(json.loads(row["data"]))

    def _all(self, table: str, change_id: str, model_cls: type) -> list:
        rows = self._conn.execute(
            f"SELECT data FROM {table} WHERE change_id=?", (change_id,)
        ).fetchall()
        return [model_cls.model_validate(json.loads(r["data"])) for r in rows]

    # ------------------------------------------------------------------
    # Versions
    # ------------------------------------------------------------------

    def save_version(self, v: AgentProfileVersion) -> None:
        self._upsert("agent_profile_versions", v.id, v, {
            "agent_id": v.agentId, "status": v.status.value, "created_at": v.createdAt,
        })

    def get_version(self, version_id: str) -> Optional[AgentProfileVersion]:
        return self._get("agent_profile_versions", version_id, AgentProfileVersion)

    def latest_production_version(self, agent_id: str) -> Optional[AgentProfileVersion]:
        row = self._conn.execute(
            "SELECT data FROM agent_profile_versions WHERE agent_id=? AND status='production' ORDER BY created_at DESC LIMIT 1",
            (agent_id,),
        ).fetchone()
        if row is None:
            return None
        return AgentProfileVersion.model_validate(json.loads(row["data"]))

    def all_versions(self, agent_id: str) -> list[AgentProfileVersion]:
        rows = self._conn.execute(
            "SELECT data FROM agent_profile_versions WHERE agent_id=?", (agent_id,)
        ).fetchall()
        return [AgentProfileVersion.model_validate(json.loads(r["data"])) for r in rows]

    # ------------------------------------------------------------------
    # Changes
    # ------------------------------------------------------------------

    def save_change(self, c: PromptProfileChange) -> None:
        self._upsert("prompt_profile_changes", c.id, c, {
            "agent_id": c.agentId, "status": c.status.value,
            "created_at": c.createdAt, "updated_at": c.updatedAt,
        })

    def get_change(self, change_id: str) -> PromptProfileChange:
        row = self._conn.execute(
            "SELECT data FROM prompt_profile_changes WHERE id=?", (change_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"Change '{change_id}' not found.")
        return PromptProfileChange.model_validate(json.loads(row["data"]))

    def update_change_status(self, change_id: str, status: ChangeStatus) -> None:
        from promptops.util import now as _now
        c = self.get_change(change_id)
        c.status = status
        c.updatedAt = _now()
        self.save_change(c)

    def list_open_changes(self, agent_id: str | None = None) -> list[PromptProfileChange]:
        q = "SELECT data FROM prompt_profile_changes WHERE status IN ('open', 'in_review')"
        params: list = []
        if agent_id:
            q += " AND agent_id=?"
            params.append(agent_id)
        rows = self._conn.execute(q, params).fetchall()
        return [PromptProfileChange.model_validate(json.loads(r["data"])) for r in rows]

    # ------------------------------------------------------------------
    # Eval runs
    # ------------------------------------------------------------------

    def save_eval_run(self, r: EvalRun) -> None:
        self._upsert("eval_runs", r.id, r, {
            "change_id": r.changeId, "role": r.role, "created_at": r.createdAt,
        })

    def latest_eval_run(self, change_id: str, role: str) -> Optional[EvalRun]:
        row = self._conn.execute(
            "SELECT data FROM eval_runs WHERE change_id=? AND role=? ORDER BY created_at DESC LIMIT 1",
            (change_id, role),
        ).fetchone()
        if row is None:
            return None
        return EvalRun.model_validate(json.loads(row["data"]))

    # ------------------------------------------------------------------
    # Patches
    # ------------------------------------------------------------------

    def save_patch(self, p: PatchProposal) -> None:
        self._upsert("patch_proposals", p.id, p, {
            "change_id": p.changeId, "created_at": p.createdAt,
        })

    def all_patches(self, change_id: str) -> list[PatchProposal]:
        return self._all("patch_proposals", change_id, PatchProposal)

    def latest_patch(self, change_id: str) -> Optional[PatchProposal]:
        return self._latest("patch_proposals", change_id, PatchProposal)

    # ------------------------------------------------------------------
    # Feedback
    # ------------------------------------------------------------------

    def save_feedback(self, f: HumanFeedback) -> None:
        self._upsert("feedback_items", f.id, f, {
            "change_id": f.changeId, "created_at": f.createdAt,
        })

    def all_feedback(self, change_id: str) -> list[HumanFeedback]:
        return self._all("feedback_items", change_id, HumanFeedback)

    # ------------------------------------------------------------------
    # Semantic diffs
    # ------------------------------------------------------------------

    def save_semantic_diff(self, d: SemanticDiff) -> None:
        self._upsert("semantic_diffs", d.id, d, {
            "change_id": d.changeId, "created_at": d.createdAt,
        })

    def latest_semantic_diff(self, change_id: str) -> Optional[SemanticDiff]:
        return self._latest("semantic_diffs", change_id, SemanticDiff)

    # ------------------------------------------------------------------
    # Gate reports
    # ------------------------------------------------------------------

    def save_gate_report(self, r: GateReport) -> None:
        self._upsert("gate_reports", r.id, r, {
            "change_id": r.changeId, "created_at": r.createdAt,
        })

    def latest_gate_report(self, change_id: str) -> Optional[GateReport]:
        return self._latest("gate_reports", change_id, GateReport)

    # ------------------------------------------------------------------
    # Review decisions
    # ------------------------------------------------------------------

    def save_review_decision(self, d: ReviewDecision) -> None:
        self._upsert("review_decisions", d.id, d, {
            "change_id": d.changeId, "created_at": d.createdAt,
        })

    def latest_review_decision(self, change_id: str) -> Optional[ReviewDecision]:
        return self._latest("review_decisions", change_id, ReviewDecision)

    # ------------------------------------------------------------------
    # Publish results
    # ------------------------------------------------------------------

    def save_publish_result(self, r: PublishResult) -> None:
        self._upsert("publish_results", r.id, r, {
            "change_id": r.changeId, "created_at": r.publishedAt,
        })

    def latest_publish_result(self, change_id: str) -> Optional[PublishResult]:
        return self._latest("publish_results", change_id, PublishResult)

    # ------------------------------------------------------------------
    # Drift events
    # ------------------------------------------------------------------

    def save_drift_event(self, e: DriftEvent) -> None:
        self._upsert("drift_events", e.id, e, {
            "change_id": e.changeId, "agent_id": e.agentId,
            "accepted": 1 if e.accepted else 0, "detected_at": e.detectedAt,
        })

    def unaccepted_drift(self, change_id: str) -> Optional[DriftEvent]:
        row = self._conn.execute(
            "SELECT data FROM drift_events WHERE change_id=? AND accepted=0 LIMIT 1",
            (change_id,),
        ).fetchone()
        if row is None:
            return None
        return DriftEvent.model_validate(json.loads(row["data"]))

    # ------------------------------------------------------------------
    # Pipeline records (append-only)
    # ------------------------------------------------------------------

    def append_record(self, r: PipelineRecord) -> None:
        self._conn.execute(
            "INSERT INTO pipeline_records (change_id, event, data, timestamp) VALUES (?, ?, ?, ?)",
            (r.changeId, r.event, json.dumps(r.data, default=str), r.timestamp),
        )
        self._conn.commit()

    def all_records(self, change_id: str) -> list[PipelineRecord]:
        rows = self._conn.execute(
            "SELECT * FROM pipeline_records WHERE change_id=? ORDER BY seq",
            (change_id,),
        ).fetchall()
        return [
            PipelineRecord(
                seq=r["seq"], changeId=r["change_id"], event=r["event"],
                data=json.loads(r["data"]), timestamp=r["timestamp"],
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Pipeline runs / steps
    # ------------------------------------------------------------------

    def save_pipeline_run(self, r: PipelineRun) -> None:
        self._upsert("pipeline_runs", r.id, r, {
            "change_id": r.changeId, "started_at": r.startedAt,
        })

    def get_pipeline_run(self, run_id: str) -> Optional[PipelineRun]:
        return self._get("pipeline_runs", run_id, PipelineRun)

    def latest_pipeline_run(self, change_id: str) -> Optional[PipelineRun]:
        row = self._conn.execute(
            "SELECT data FROM pipeline_runs WHERE change_id=? ORDER BY started_at DESC LIMIT 1",
            (change_id,),
        ).fetchone()
        if row is None:
            return None
        return PipelineRun.model_validate(json.loads(row["data"]))

    def save_pipeline_step(self, s: PipelineStep) -> None:
        self._upsert("pipeline_steps", s.id, s, {
            "run_id": s.runId, "change_id": s.changeId,
            "step_id": s.stepId, "status": s.status.value,
        })

    def all_pipeline_steps(self, run_id: str) -> list[PipelineStep]:
        rows = self._conn.execute(
            "SELECT data FROM pipeline_steps WHERE run_id=?", (run_id,)
        ).fetchall()
        return [PipelineStep.model_validate(json.loads(r["data"])) for r in rows]

    def close(self) -> None:
        self._conn.close()
