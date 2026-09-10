"""Self-correction controller orchestrating iterative agent turns and feedback."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from harness.agents import get_agent_mode
from harness.config import HarnessConfig
from harness.context.task_context import TaskContextBuilder
from harness.feedback.analyzer import FeedbackAnalyzer
from harness.feedback.collector import FeedbackCollector
from harness.logging_config import logger
from harness.models import (
    EvaluationStatus,
    FailureCategory,
    IterationRecord,
    RunRecord,
    Task,
    TimingBreakdown,
    TokenUsage,
)
from harness.opencode.base import AgentBackend
from harness.tools.git import GitTracker


class FeedbackLoopController:
    """Orchestrates agent execution, test verification, and iterative remediation."""

    def __init__(
        self,
        task: Task,
        workspace: Path,
        config: HarnessConfig,
        backend: AgentBackend,
        run_id: Optional[str] = None,
    ):
        self.task = task
        self.workspace = workspace.resolve()
        self.config = config
        self.backend = backend
        self.run_id = run_id or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.git_tracker = GitTracker(self.workspace)
        self.collector = FeedbackCollector(self.workspace)

    def execute(self) -> RunRecord:
        """Run the complete adaptive feedback loop."""
        start_time_iso = datetime.now().isoformat()
        t0 = time.time()

        logger.info(f"Task started: '{self.task.title}' [{self.run_id}]")
        logger.info(f"Repository: {self.workspace.name} | Difficulty: {self.task.difficulty} | Mode: {self.config.agent.mode.value} | Max iterations: {self.config.max_iterations}")

        # Record initial Git state
        initial_status = self.git_tracker.get_status()
        initial_commit = self.git_tracker.get_commit_hash()

        iterations_history: List[IterationRecord] = []
        overall_tool_calls: Dict[str, int] = {}
        total_input_tokens = 0
        total_output_tokens = 0
        total_reasoning_tokens = 0
        total_cost = 0.0
        tokens_available = False

        total_agent_time = 0.0
        total_test_time = 0.0
        total_feedback_time = 0.0

        test_passed = False
        hidden_test_passed: Optional[bool] = None
        failure_cat: Optional[FailureCategory] = None
        failure_msg: Optional[str] = None

        mode_handler = get_agent_mode(self.config.agent.mode)
        session_id: Optional[str] = None
        last_test_result = None
        last_lint_result = None

        for iter_num in range(1, self.config.max_iterations + 1):
            iter_start = time.time()
            logger.info(f"[{iter_num}/{self.config.max_iterations}] Starting iteration")

            # 1. Prepare Prompt (Feedback time)
            t_fb_start = time.time()
            if iter_num == 1:
                prompt = TaskContextBuilder.build_initial_prompt(
                    task=self.task,
                    workspace=self.workspace,
                    config=self.config,
                    mode_instruction=mode_handler.get_system_instructions(),
                )
            else:
                prompt = FeedbackAnalyzer.format_remediation_prompt(
                    test_result=last_test_result,
                    lint_result=last_lint_result if self.config.feedback.linter else None,
                )
                logger.info("Agent correction attempt based on feedback")
            fb_dur = time.time() - t_fb_start
            total_feedback_time += fb_dur

            # 2. Execute Agent Turn (Agent time)
            t_agent_start = time.time()
            agent_resp = self.backend.execute_turn(
                prompt=prompt,
                workspace=self.workspace,
                mode=self.config.agent.mode,
                permissions=self.config.tools,
                session_id=session_id,
            )
            agent_dur = time.time() - t_agent_start
            total_agent_time += agent_dur

            if agent_resp.session_id:
                session_id = agent_resp.session_id

            # Accumulate tool calls and tokens
            for tool, cnt in agent_resp.tool_calls.items():
                overall_tool_calls[tool] = overall_tool_calls.get(tool, 0) + cnt

            if agent_resp.token_usage.is_available and agent_resp.token_usage.total_tokens is not None:
                tokens_available = True
                total_input_tokens += (agent_resp.token_usage.input_tokens or 0)
                total_output_tokens += (agent_resp.token_usage.output_tokens or 0)
                total_reasoning_tokens += (agent_resp.token_usage.reasoning_tokens or 0)
                total_cost += (agent_resp.token_usage.cost or 0.0)

            files_changed = self.git_tracker.get_changed_files() or agent_resp.files_modified

            # 3. Check Baseline / No Feedback configuration
            if not self.config.feedback.tests:
                logger.info("Test feedback disabled in configuration (Baseline mode). Running tests once for final evaluation.")
                t_test_start = time.time()
                test_res, lint_res = self.collector.collect(
                    test_command=self.task.test_command,
                    run_linter=self.config.feedback.linter,
                    custom_lint_command=self.task.lint_command,
                )
                test_dur = time.time() - t_test_start
                total_test_time += test_dur

                test_passed = test_res.passed
                if not test_passed:
                    failure_cat = FeedbackAnalyzer.classify_failure(test_res, lint_res)
                    failure_msg = test_res.summary

                iter_dur = time.time() - iter_start
                iterations_history.append(
                    IterationRecord(
                        iteration=iter_num,
                        prompt=prompt[:500],
                        response_summary=agent_resp.text[:500],
                        files_changed=files_changed,
                        test_result=test_res,
                        lint_result=lint_res,
                        tool_calls=agent_resp.tool_calls,
                        duration_seconds=round(iter_dur, 2),
                        timing=TimingBreakdown(
                            total_time_seconds=round(iter_dur, 2),
                            agent_time_seconds=round(agent_dur, 2),
                            test_time_seconds=round(test_dur, 2),
                            feedback_time_seconds=round(fb_dur, 2),
                        ),
                    )
                )
                break

            # 4. Feedback Mode: Run Tests & Linters
            logger.info("Executing tests")
            t_test_start = time.time()
            test_res, lint_res = self.collector.collect(
                test_command=self.task.test_command,
                run_linter=self.config.feedback.linter,
                custom_lint_command=self.task.lint_command,
            )
            test_dur = time.time() - t_test_start
            total_test_time += test_dur

            last_test_result = test_res
            last_lint_result = lint_res

            iter_dur = time.time() - iter_start
            iterations_history.append(
                IterationRecord(
                    iteration=iter_num,
                    prompt=prompt[:500],
                    response_summary=agent_resp.text[:500],
                    files_changed=files_changed,
                    test_result=test_res,
                    lint_result=lint_res,
                    tool_calls=agent_resp.tool_calls,
                    duration_seconds=round(iter_dur, 2),
                    timing=TimingBreakdown(
                        total_time_seconds=round(iter_dur, 2),
                        agent_time_seconds=round(agent_dur, 2),
                        test_time_seconds=round(test_dur, 2),
                        feedback_time_seconds=round(fb_dur, 2),
                    ),
                )
            )

            if test_res.passed:
                logger.info(f"Public tests passed! ({test_res.passed_count} passed, 0 failed)")
                test_passed = True
                break
            else:
                logger.warning(f"{test_res.failed_count} tests failed ({test_res.summary})")
                if iter_num == self.config.max_iterations:
                    failure_cat = FeedbackAnalyzer.classify_failure(test_res, lint_res)
                    failure_msg = f"Maximum iterations ({self.config.max_iterations}) reached without passing tests."

        # 5. Hidden Validation Phase (Post-loop)
        final_status = EvaluationStatus.FAILURE
        success = False

        if test_passed:
            if self.task.hidden_test_command:
                logger.info(f"Executing hidden validation tests: '{self.task.hidden_test_command}'")
                t_hid_start = time.time()
                raw_hid = self.collector.test_runner.run(self.task.hidden_test_command)
                hid_dur = time.time() - t_hid_start
                total_test_time += hid_dur

                hidden_test_passed = raw_hid.passed
                if hidden_test_passed:
                    logger.info("Hidden validation tests PASSED!")
                    final_status = EvaluationStatus.SUCCESS
                    success = True
                else:
                    logger.warning("Public tests passed but hidden validation tests FAILED!")
                    final_status = EvaluationStatus.PARTIAL
                    success = False
                    failure_cat = FailureCategory.TEST_FAILURE
                    failure_msg = "Failed hidden validation tests"
            else:
                final_status = EvaluationStatus.SUCCESS
                success = True
        else:
            final_status = EvaluationStatus.FAILURE
            success = False

        total_duration = time.time() - t0
        final_diff = self.git_tracker.get_diff()
        diff_stat = self.git_tracker.get_diff_stat()

        logger.info(f"Task completed. STATUS: {final_status.value} (Duration: {total_duration:.1f}s, Iterations: {len(iterations_history)})")

        final_tokens = TokenUsage(
            input_tokens=total_input_tokens if tokens_available else None,
            output_tokens=total_output_tokens if tokens_available else None,
            reasoning_tokens=total_reasoning_tokens if tokens_available else None,
            total_tokens=(total_input_tokens + total_output_tokens) if tokens_available else None,
            cost=round(total_cost, 6) if tokens_available else 0.0,
            is_available=tokens_available,
        )

        timing_summary = TimingBreakdown(
            total_time_seconds=round(total_duration, 2),
            agent_time_seconds=round(total_agent_time, 2),
            test_time_seconds=round(total_test_time, 2),
            feedback_time_seconds=round(total_feedback_time, 2),
        )

        return RunRecord(
            run_id=self.run_id,
            task_id=self.task.id,
            task_title=self.task.title,
            repository=self.workspace.name,
            agent_mode=self.config.agent.mode.value,
            model=self.config.model or getattr(self.backend, "model", "mock"),
            config_name=self.config.name,
            start_time=start_time_iso,
            end_time=datetime.now().isoformat(),
            duration_seconds=round(total_duration, 2),
            iteration_count=len(iterations_history),
            success=success,
            status=final_status,
            test_passed=test_passed,
            hidden_test_passed=hidden_test_passed,
            token_usage=final_tokens,
            tool_calls=overall_tool_calls,
            timing=timing_summary,
            failure_category=failure_cat,
            failure_reason=failure_msg,
            git_diff_summary=diff_stat or f"{len(iterations_history[-1].files_changed if iterations_history else [])} files changed",
            history=iterations_history,
            metadata={
                "initial_commit": initial_commit,
                "initial_status": initial_status,
                "full_git_diff": final_diff[:2000] if final_diff else None,
            },
        )
