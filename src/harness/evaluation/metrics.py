"""Evaluation metrics calculation and statistical aggregation."""

from __future__ import annotations

import math
import statistics
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from harness.models import EvaluationStatus, FailureCategory, RunRecord


class ImprovementMetrics(BaseModel):
    """Calculated delta improvements between baseline and candidate configurations."""

    absolute_success_improvement: float = 0.0   # in percentage points
    relative_success_improvement: float = 0.0   # in percent
    test_pass_improvement: float = 0.0
    runtime_change_seconds: float = 0.0
    iteration_change: float = 0.0
    token_change: Optional[int] = None


class BenchmarkMetrics(BaseModel):
    """Aggregated evaluation metrics across a suite of runs."""

    config_name: str
    total_tasks: int = 0
    successful_tasks: int = 0
    partial_tasks: int = 0
    failed_tasks: int = 0
    success_rate: float = 0.0
    test_pass_rate: float = 0.0

    avg_duration_seconds: float = 0.0
    median_duration_seconds: float = 0.0
    stddev_duration: float = 0.0

    avg_iterations: float = 0.0
    median_iterations: float = 0.0

    avg_agent_time: float = 0.0
    avg_test_time: float = 0.0
    avg_feedback_time: float = 0.0

    total_input_tokens: Optional[int] = None
    total_output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    avg_tokens_per_task: Optional[int] = None
    median_tokens_per_task: Optional[int] = None
    tokens_available: bool = False

    total_tool_calls: Dict[str, int] = Field(default_factory=dict)
    failure_breakdown: Dict[str, int] = Field(default_factory=dict)
    iteration_distribution: Dict[int, int] = Field(default_factory=dict)
    difficulty_breakdown: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    category_breakdown: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class MetricsCalculator:
    """Calculates rigorous benchmark metrics and statistical comparisons."""

    @staticmethod
    def compute(runs: List[RunRecord], config_name: str = "default") -> BenchmarkMetrics:
        if not runs:
            return BenchmarkMetrics(config_name=config_name)

        total = len(runs)
        successful = sum(1 for r in runs if r.status == EvaluationStatus.SUCCESS or r.success)
        partial = sum(1 for r in runs if r.status == EvaluationStatus.PARTIAL)
        failed = sum(1 for r in runs if r.status == EvaluationStatus.FAILURE or (not r.success and r.status != EvaluationStatus.PARTIAL))
        test_passed = sum(1 for r in runs if r.test_passed)

        durations = [r.duration_seconds for r in runs]
        iterations = [r.iteration_count for r in runs]

        med_duration = statistics.median(durations) if durations else 0.0
        med_iter = statistics.median(iterations) if iterations else 0.0
        std_dur = statistics.stdev(durations) if len(durations) > 1 else 0.0

        agent_times = [r.timing.agent_time_seconds for r in runs if r.timing]
        test_times = [r.timing.test_time_seconds for r in runs if r.timing]
        fb_times = [r.timing.feedback_time_seconds for r in runs if r.timing]

        avg_agent = round(sum(agent_times) / total, 2) if agent_times else 0.0
        avg_test = round(sum(test_times) / total, 2) if test_times else 0.0
        avg_fb = round(sum(fb_times) / total, 2) if fb_times else 0.0

        # Iteration distribution
        iter_dist: Dict[int, int] = {}
        for r in runs:
            iter_dist[r.iteration_count] = iter_dist.get(r.iteration_count, 0) + 1

        # Tool calls aggregation
        total_tools: Dict[str, int] = {}
        for r in runs:
            for tool, count in r.tool_calls.items():
                total_tools[tool] = total_tools.get(tool, 0) + count

        # Failure classification
        failure_dist: Dict[str, int] = {}
        for r in runs:
            if not r.success:
                cat = r.failure_category.value if r.failure_category else "unknown"
                failure_dist[cat] = failure_dist.get(cat, 0) + 1

        # Token aggregation
        runs_with_tokens = [r for r in runs if r.token_usage.is_available and r.token_usage.total_tokens is not None]
        tokens_available = len(runs_with_tokens) > 0
        total_inp = sum(r.token_usage.input_tokens or 0 for r in runs_with_tokens) if tokens_available else None
        total_out = sum(r.token_usage.output_tokens or 0 for r in runs_with_tokens) if tokens_available else None
        total_tok = sum(r.token_usage.total_tokens or 0 for r in runs_with_tokens) if tokens_available else None
        avg_tok = int(total_tok / len(runs_with_tokens)) if (tokens_available and runs_with_tokens) else None
        med_tok = int(statistics.median([r.token_usage.total_tokens for r in runs_with_tokens])) if (tokens_available and runs_with_tokens) else None

        # Difficulty Breakdown
        diff_runs: Dict[str, List[RunRecord]] = {"easy": [], "medium": [], "hard": []}
        for r in runs:
            # Check difficulty from metadata or task_id
            diff = r.metadata.get("difficulty")
            if not diff:
                if any(x in r.task_id for x in ("01", "02", "05", "12", "14", "18", "19", "23", "24", "27")):
                    diff = "easy"
                elif any(x in r.task_id for x in ("09", "10", "17", "20", "25", "30")):
                    diff = "hard"
                else:
                    diff = "medium"
            diff_runs.setdefault(diff, []).append(r)

        difficulty_stats = {}
        for d_name, d_list in diff_runs.items():
            if d_list:
                d_succ = sum(1 for x in d_list if x.success)
                difficulty_stats[d_name] = {
                    "total": len(d_list),
                    "success": d_succ,
                    "rate": round((d_succ / len(d_list)) * 100, 1),
                }

        # Category Breakdown
        cat_runs: Dict[str, List[RunRecord]] = {}
        for r in runs:
            cat = "bug_fix" if "bug" in r.task_id else ("feature" if "feat" in r.task_id else ("testing" if "test" in r.task_id else "migration"))
            cat_runs.setdefault(cat, []).append(r)

        category_stats = {}
        for c_name, c_list in cat_runs.items():
            c_succ = sum(1 for x in c_list if x.success)
            category_stats[c_name] = {
                "total": len(c_list),
                "success": c_succ,
                "rate": round((c_succ / len(c_list)) * 100, 1),
            }

        return BenchmarkMetrics(
            config_name=config_name,
            total_tasks=total,
            successful_tasks=successful,
            partial_tasks=partial,
            failed_tasks=failed,
            success_rate=round((successful / total) * 100, 1),
            test_pass_rate=round((test_passed / total) * 100, 1),
            avg_duration_seconds=round(sum(durations) / total, 2),
            median_duration_seconds=round(med_duration, 2),
            stddev_duration=round(std_dur, 2),
            avg_iterations=round(sum(iterations) / total, 2),
            median_iterations=round(med_iter, 2),
            avg_agent_time=avg_agent,
            avg_test_time=avg_test,
            avg_feedback_time=avg_fb,
            total_input_tokens=total_inp,
            total_output_tokens=total_out,
            total_tokens=total_tok,
            avg_tokens_per_task=avg_tok,
            median_tokens_per_task=med_tok,
            tokens_available=tokens_available,
            total_tool_calls=total_tools,
            failure_breakdown=failure_dist,
            iteration_distribution=dict(sorted(iter_dist.items())),
            difficulty_breakdown=difficulty_stats,
            category_breakdown=category_stats,
        )

    @staticmethod
    def calculate_improvements(base: BenchmarkMetrics, cand: BenchmarkMetrics) -> ImprovementMetrics:
        """Calculate relative and absolute deltas between two configurations."""
        abs_succ = round(cand.success_rate - base.success_rate, 1)
        rel_succ = round(((cand.success_rate - base.success_rate) / base.success_rate * 100), 1) if base.success_rate > 0 else 0.0
        test_pass_imp = round(cand.test_pass_rate - base.test_pass_rate, 1)
        run_change = round(cand.avg_duration_seconds - base.avg_duration_seconds, 2)
        iter_change = round(cand.avg_iterations - base.avg_iterations, 2)

        tok_change = None
        if base.avg_tokens_per_task is not None and cand.avg_tokens_per_task is not None:
            tok_change = cand.avg_tokens_per_task - base.avg_tokens_per_task

        return ImprovementMetrics(
            absolute_success_improvement=abs_succ,
            relative_success_improvement=rel_succ,
            test_pass_improvement=test_pass_imp,
            runtime_change_seconds=run_change,
            iteration_change=iter_change,
            token_change=tok_change,
        )
