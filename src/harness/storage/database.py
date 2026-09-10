"""SQLite and JSON persistence layer for benchmark and task run history."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from harness.logging_config import logger
from harness.models import EvaluationStatus, FailureCategory, RunRecord, TimingBreakdown, TokenUsage


class RunDatabase:
    """SQLite-backed persistent repository for task execution runs."""

    def __init__(self, db_path: str | Path = "./runs.db"):
        self.db_path = Path(db_path).resolve()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create runs table and indices if they do not exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    task_title TEXT,
                    repository TEXT,
                    agent_mode TEXT,
                    model TEXT,
                    config_name TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    duration_seconds REAL,
                    iteration_count INTEGER,
                    success INTEGER,
                    status TEXT,
                    test_passed INTEGER,
                    hidden_test_passed INTEGER,
                    token_usage_json TEXT,
                    tool_calls_json TEXT,
                    timing_json TEXT,
                    failure_category TEXT,
                    failure_reason TEXT,
                    git_diff_summary TEXT,
                    history_json TEXT,
                    metadata_json TEXT
                )
            """)
            # Ensure new columns exist for existing databases
            for col, col_type in [
                ("status", "TEXT"),
                ("hidden_test_passed", "INTEGER"),
                ("timing_json", "TEXT"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE runs ADD COLUMN {col} {col_type}")
                except sqlite3.OperationalError:
                    pass  # Column already exists

            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_task_id ON runs(task_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_config ON runs(config_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_success ON runs(success)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status)")
            conn.commit()

    def save_run(self, run: RunRecord) -> None:
        """Insert or replace a run record in the database."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO runs (
                    run_id, task_id, task_title, repository, agent_mode, model,
                    config_name, start_time, end_time, duration_seconds,
                    iteration_count, success, status, test_passed, hidden_test_passed,
                    token_usage_json, tool_calls_json, timing_json, failure_category,
                    failure_reason, git_diff_summary, history_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.task_id,
                    run.task_title,
                    run.repository,
                    run.agent_mode,
                    run.model,
                    run.config_name,
                    run.start_time,
                    run.end_time,
                    run.duration_seconds,
                    run.iteration_count,
                    1 if run.success else 0,
                    run.status.value,
                    1 if run.test_passed else 0,
                    1 if run.hidden_test_passed else (0 if run.hidden_test_passed is False else None),
                    json.dumps(run.token_usage.model_dump()),
                    json.dumps(run.tool_calls),
                    json.dumps(run.timing.model_dump()),
                    run.failure_category.value if run.failure_category else None,
                    run.failure_reason,
                    run.git_diff_summary,
                    json.dumps([h.model_dump() for h in run.history]),
                    json.dumps(run.metadata),
                ),
            )
            conn.commit()
        logger.info(f"Saved run {run.run_id} to database ({self.db_path.name})")

    def get_run(self, run_id: str) -> Optional[RunRecord]:
        """Fetch a specific run by ID."""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_record(row)

    def list_runs(
        self,
        config_name: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[RunRecord]:
        """Retrieve recent runs with optional config filter."""
        query = "SELECT * FROM runs"
        params: List[Any] = []
        if config_name:
            query += " WHERE config_name = ?"
            params.append(config_name)
        query += " ORDER BY start_time DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._get_connection() as conn:
            cur = conn.execute(query, params)
            return [self._row_to_record(row) for row in cur.fetchall()]

    def get_stats(self, config_name: Optional[str] = None) -> Dict[str, Any]:
        """Calculate aggregate performance metrics."""
        runs = self.list_runs(config_name=config_name, limit=1000)
        total = len(runs)
        if total == 0:
            return {
                "total_runs": 0,
                "successful_runs": 0,
                "partial_runs": 0,
                "failed_runs": 0,
                "success_rate": 0.0,
                "avg_duration": 0.0,
                "avg_iterations": 0.0,
                "avg_tokens": 0,
            }

        successful = sum(1 for r in runs if r.success)
        partial = sum(1 for r in runs if r.status == EvaluationStatus.PARTIAL)
        failed = sum(1 for r in runs if r.status == EvaluationStatus.FAILURE)
        durations = [r.duration_seconds for r in runs]
        iterations = [r.iteration_count for r in runs]
        tokens = [r.token_usage.total_tokens for r in runs if r.token_usage.total_tokens]

        return {
            "total_runs": total,
            "successful_runs": successful,
            "partial_runs": partial,
            "failed_runs": failed,
            "success_rate": round((successful / total) * 100, 1),
            "avg_duration": round(sum(durations) / total, 1),
            "avg_iterations": round(sum(iterations) / total, 2),
            "avg_tokens": int(sum(tokens) / len(tokens)) if tokens else 0,
        }

    def _row_to_record(self, row: sqlite3.Row) -> RunRecord:
        """Convert a database row into a Pydantic RunRecord."""
        token_data = json.loads(row["token_usage_json"]) if row["token_usage_json"] else {}
        token_usage = TokenUsage(**token_data)

        tool_calls = json.loads(row["tool_calls_json"]) if row["tool_calls_json"] else {}
        timing_data = json.loads(row["timing_json"]) if "timing_json" in row.keys() and row["timing_json"] else {}
        timing = TimingBreakdown(**timing_data)
        history = json.loads(row["history_json"]) if row["history_json"] else []
        metadata = json.loads(row["metadata_json"]) if row["metadata_json"] else {}

        fail_cat = None
        if row["failure_category"]:
            try:
                fail_cat = FailureCategory(row["failure_category"])
            except ValueError:
                pass

        status_str = row["status"] if "status" in row.keys() and row["status"] else None
        if status_str:
            try:
                eval_status = EvaluationStatus(status_str)
            except ValueError:
                eval_status = EvaluationStatus.SUCCESS if row["success"] else EvaluationStatus.FAILURE
        else:
            eval_status = EvaluationStatus.SUCCESS if row["success"] else EvaluationStatus.FAILURE

        hidden_passed = None
        if "hidden_test_passed" in row.keys() and row["hidden_test_passed"] is not None:
            hidden_passed = bool(row["hidden_test_passed"])

        return RunRecord(
            run_id=row["run_id"],
            task_id=row["task_id"],
            task_title=row["task_title"] or "",
            repository=row["repository"] or "",
            agent_mode=row["agent_mode"] or "developer",
            model=row["model"] or "unknown",
            config_name=row["config_name"] or "default",
            start_time=row["start_time"],
            end_time=row["end_time"],
            duration_seconds=row["duration_seconds"],
            iteration_count=row["iteration_count"],
            success=bool(row["success"]),
            status=eval_status,
            test_passed=bool(row["test_passed"]),
            hidden_test_passed=hidden_passed,
            token_usage=token_usage,
            tool_calls=tool_calls,
            timing=timing,
            failure_category=fail_cat,
            failure_reason=row["failure_reason"],
            git_diff_summary=row["git_diff_summary"],
            history=history,
            metadata=metadata,
        )
