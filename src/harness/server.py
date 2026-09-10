"""FastAPI web server and comprehensive evaluation dashboard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from harness.config import get_settings
from harness.evaluation.benchmark import BenchmarkRunner
from harness.evaluation.metrics import MetricsCalculator
from harness.models import EvaluationStatus, RunRecord
from harness.storage.database import RunDatabase

app = FastAPI(title="Adaptive Coding Agent Harness Dashboard", version="0.2.0")
db = RunDatabase(get_settings().db_path)


@app.get("/api/runs", response_model=List[Dict[str, Any]])
def api_list_runs(limit: int = 100, config: Optional[str] = None):
    runs = db.list_runs(config_name=config, limit=limit)
    return [r.model_dump() for r in runs]


@app.get("/api/runs/{run_id}")
def api_get_run(run_id: str):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run.model_dump()


@app.get("/api/metrics")
def api_get_metrics(config: Optional[str] = None):
    runs = db.list_runs(config_name=config, limit=1000)
    metrics = MetricsCalculator.compute(runs, config_name=config or "all")
    return metrics.model_dump()


@app.get("/api/benchmarks")
def api_list_benchmarks(category: Optional[str] = None):
    runner = BenchmarkRunner()
    tasks = runner.load_tasks(category=category)
    return [t.model_dump() for t in tasks]


@app.get("/", response_class=HTMLResponse)
def dashboard_home():
    runs = db.list_runs(limit=250)
    metrics = MetricsCalculator.compute(runs, config_name="All Runs")

    # Group runs by configuration
    configs = {}
    for r in runs:
        cfg = r.config_name.lower()
        if "baseline" in cfg:
            configs.setdefault("Baseline", []).append(r)
        elif "context" in cfg:
            configs.setdefault("Repo Context", []).append(r)
        elif "tests" in cfg or "test-feedback" in cfg:
            configs.setdefault("Test Feedback", []).append(r)
        elif "mode" in cfg or "specialized" in cfg:
            configs.setdefault("Specialized Agent", []).append(r)
        elif "harness" in cfg or "developer" in cfg:
            configs.setdefault("Full Harness", []).append(r)
        else:
            configs.setdefault(r.config_name, []).append(r)

    # Calculate config-specific metrics
    config_metrics = {name: MetricsCalculator.compute(c_runs, name) for name, c_runs in configs.items()}

    # Baseline vs Full Harness
    base_m = config_metrics.get("Baseline")
    harn_m = config_metrics.get("Full Harness")

    # Difficulty breakdown
    diff_stats = {"easy": {"pass": 0, "total": 0}, "medium": {"pass": 0, "total": 0}, "hard": {"pass": 0, "total": 0}}
    cat_stats = {"bug_fix": {"pass": 0, "total": 0}, "feature": {"pass": 0, "total": 0}, "testing": {"pass": 0, "total": 0}, "migration": {"pass": 0, "total": 0}}
    iter_dist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

    for r in runs:
        # Determine category & difficulty from task_id or metadata
        t_id = r.task_id.lower()
        diff = "medium"
        if "easy" in t_id or "_01" in t_id or "_02" in t_id:
            diff = "easy"
        elif "hard" in t_id or "_09" in t_id or "_10" in t_id or "_05" in t_id:
            diff = "hard"
        
        diff_stats[diff]["total"] += 1
        if r.status == EvaluationStatus.SUCCESS:
            diff_stats[diff]["pass"] += 1

        cat = "feature"
        if "bug" in t_id:
            cat = "bug_fix"
        elif "test" in t_id:
            cat = "testing"
        elif "mig" in t_id:
            cat = "migration"
        
        cat_stats[cat]["total"] += 1
        if r.status == EvaluationStatus.SUCCESS:
            cat_stats[cat]["pass"] += 1

        it = min(r.iteration_count, 5)
        iter_dist[it] = iter_dist.get(it, 0) + 1

    # Render Ablation Table Rows
    ablation_rows = []
    canonical_order = ["Baseline", "Repo Context", "Test Feedback", "Specialized Agent", "Full Harness"]
    for c_name in canonical_order:
        cm = config_metrics.get(c_name)
        if cm:
            ablation_rows.append(f"""
            <tr>
                <td><strong>{c_name}</strong></td>
                <td>{cm.total_tasks}</td>
                <td><strong style="color: {'#10b981' if cm.success_rate >= 70 else ('#f59e0b' if cm.success_rate >= 40 else '#ef4444')};">{cm.success_rate:.1f}%</strong></td>
                <td>{cm.test_pass_rate:.1f}%</td>
                <td>{cm.avg_duration_seconds:.1f}s</td>
                <td>{cm.avg_tokens_per_task:,.0f}</td>
                <td>{cm.avg_iterations:.2f}</td>
            </tr>
            """)
        else:
            ablation_rows.append(f"""
            <tr style="opacity: 0.5;">
                <td><strong>{c_name}</strong></td>
                <td colspan="6" style="text-align: center;"><em>Not executed yet (run benchmark with this preset)</em></td>
            </tr>
            """)
    ablation_table_html = "".join(ablation_rows)

    # HTML table rows with expandable details
    table_rows = []
    for idx, r in enumerate(runs[:50]):
        status_badge = (
            '<span class="badge success">SUCCESS</span>'
            if r.status == EvaluationStatus.SUCCESS
            else ('<span class="badge partial">PARTIAL</span>' if r.status == EvaluationStatus.PARTIAL else '<span class="badge failed">FAILURE</span>')
        )
        fail_badge = f'<span class="cat-badge">{r.failure_category.value}</span>' if r.failure_category else '<span style="color:var(--muted);">-</span>'
        hidden_badge = (
            '<span style="color:var(--success);">PASSED</span>'
            if r.hidden_test_passed is True
            else ('<span style="color:var(--danger);">FAILED</span>' if r.hidden_test_passed is False else '<span style="color:var(--muted);">N/A</span>')
        )
        
        detail_id = f"detail_{idx}"
        # Extract last test output from history
        test_out_raw = "No test output captured."
        if r.history:
            for h in reversed(r.history):
                if h.test_result and h.test_result.raw_output:
                    test_out_raw = h.test_result.raw_output
                    break
        safe_output = test_out_raw.replace("<", "&lt;").replace(">", "&gt;")

        # Extract feedback history
        feedback_items = [h.prompt for h in r.history if h.iteration > 1]
        safe_feedback = ("\n\n---\n\n".join(feedback_items) if feedback_items else "No feedback iterations.").replace("<", "&lt;").replace(">", "&gt;")

        # Extract git diff
        git_diff_text = r.metadata.get("git_diff") or r.git_diff_summary or "No modifications recorded."
        safe_diff = git_diff_text.replace("<", "&lt;").replace(">", "&gt;")

        tot_tokens = r.token_usage.total_tokens or 0
        inp_tokens = r.token_usage.input_tokens or 0
        out_tokens = r.token_usage.output_tokens or 0

        table_rows.append(f"""
        <tr class="main-row" onclick="toggleDetail('{detail_id}')" style="cursor: pointer;">
            <td><code>{r.run_id}</code></td>
            <td><strong>{r.task_id}</strong>: {r.task_title}</td>
            <td><span class="mode-tag">{r.config_name}</span></td>
            <td>{status_badge}</td>
            <td>{r.iteration_count}</td>
            <td>{r.duration_seconds:.2f}s</td>
            <td>{tot_tokens:,}</td>
            <td>{fail_badge}</td>
            <td>{hidden_badge}</td>
            <td><button class="expand-btn">View Details</button></td>
        </tr>
        <tr id="{detail_id}" class="detail-row" style="display: none;">
            <td colspan="10">
                <div class="detail-panel">
                    <div class="grid grid-3">
                        <div>
                            <h4>Execution Timing</h4>
                            <p class="muted">Agent Time: <strong>{r.timing.agent_time_seconds:.2f}s</strong></p>
                            <p class="muted">Test Time: <strong>{r.timing.test_time_seconds:.2f}s</strong></p>
                            <p class="muted">Feedback Time: <strong>{r.timing.feedback_time_seconds:.2f}s</strong></p>
                            <p class="muted">Total Wall Clock: <strong>{r.timing.total_time_seconds:.2f}s</strong></p>
                        </div>
                        <div>
                            <h4>Tokens & Cost</h4>
                            <p class="muted">Input Tokens: <strong>{inp_tokens:,}</strong></p>
                            <p class="muted">Output Tokens: <strong>{out_tokens:,}</strong></p>
                            <p class="muted">Total Tokens: <strong>{tot_tokens:,}</strong></p>
                            <p class="muted">Mode: <strong>{r.agent_mode}</strong></p>
                        </div>
                        <div>
                            <h4>Diagnostics</h4>
                            <p class="muted">Failure Category: <strong>{r.failure_category.value if r.failure_category else 'None'}</strong></p>
                            <p class="muted">Failure Reason: <strong>{r.failure_reason or 'None'}</strong></p>
                            <p class="muted">Hidden Validation: <strong>{hidden_badge}</strong></p>
                            <p class="muted">Git Diff Summary: <strong>{r.git_diff_summary or 'None'}</strong></p>
                        </div>
                    </div>
                    
                    <h4 style="margin-top:12px;">Test Runner Output</h4>
                    <pre class="code-block">{safe_output}</pre>

                    <h4 style="margin-top:12px;">Agent Feedback Provided</h4>
                    <pre class="code-block">{safe_feedback}</pre>

                    <h4 style="margin-top:12px;">Git Worktree Diff</h4>
                    <pre class="code-block">{safe_diff}</pre>
                </div>
            </td>
        </tr>
        """)

    rows_html = "".join(table_rows) if table_rows else "<tr><td colspan='10' style='text-align:center;'>No execution runs recorded yet. Run benchmark suite or a task to populate.</td></tr>"

    # Comparison delta header
    comp_header = ""
    if base_m and harn_m:
        delta_succ = harn_m.success_rate - base_m.success_rate
        rel_succ = (delta_succ / base_m.success_rate * 100) if base_m.success_rate > 0 else 0
        comp_header = f"""
        <div class="card comparison-banner">
            <div class="grid grid-2">
                <div class="comp-box">
                    <h4>Baseline (Minimal Scaffolding)</h4>
                    <div class="large-num">{base_m.success_rate:.1f}%</div>
                    <div class="muted">Pass Rate: {base_m.test_pass_rate:.1f}% | Avg Iterations: {base_m.avg_iterations:.2f} | Avg Tokens: {base_m.avg_tokens_per_task:,.0f}</div>
                </div>
                <div class="comp-box highlight">
                    <h4>Full Adaptive Harness</h4>
                    <div class="large-num" style="color: #10b981;">{harn_m.success_rate:.1f}%</div>
                    <div class="muted">
                        Absolute Improvement: <strong style="color:#10b981;">{delta_succ:+.1f} pts</strong> | 
                        Relative Gain: <strong style="color:#10b981;">{rel_succ:+.1f}%</strong> | 
                        Avg Iterations: {harn_m.avg_iterations:.2f}
                    </div>
                </div>
            </div>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Adaptive Coding Agent Harness Dashboard</title>
    <style>
        :root {{
            --bg: #0b0f19;
            --surface: #151d30;
            --surface-hover: #1e2942;
            --border: #263352;
            --text: #f8fafc;
            --muted: #94a3b8;
            --primary: #38bdf8;
            --success: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 24px;
        }}
        .container {{ max-width: 1300px; margin: 0 auto; }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border);
            padding-bottom: 16px;
            margin-bottom: 24px;
        }}
        h1 {{ margin: 0; font-size: 24px; color: var(--primary); }}
        h3 {{ margin-top: 0; color: #e2e8f0; font-size: 16px; }}
        h4 {{ margin: 0 0 6px 0; font-size: 13px; color: #cbd5e1; }}
        .badge {{
            padding: 3px 8px;
            border-radius: 9999px;
            font-size: 11px;
            font-weight: 700;
        }}
        .badge.success {{ background: rgba(16, 185, 129, 0.2); color: var(--success); border: 1px solid var(--success); }}
        .badge.partial {{ background: rgba(245, 158, 11, 0.2); color: var(--warning); border: 1px solid var(--warning); }}
        .badge.failed {{ background: rgba(239, 68, 68, 0.2); color: var(--danger); border: 1px solid var(--danger); }}
        .cat-badge {{ background: rgba(245, 158, 11, 0.15); color: var(--warning); padding: 2px 6px; border-radius: 4px; font-size: 11px; font-family: monospace; }}
        .mode-tag {{ background: #263352; padding: 2px 8px; border-radius: 4px; font-size: 11px; color: #94a3b8; font-family: monospace; }}
        .grid {{ display: grid; gap: 16px; }}
        .grid-6 {{ grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }}
        .grid-4 {{ grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }}
        .grid-3 {{ grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }}
        .grid-2 {{ grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); }}
        .card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 20px;
        }}
        .metric-card h4 {{ margin: 0 0 6px 0; color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }}
        .metric-card .value {{ font-size: 26px; font-weight: bold; margin: 0; color: #fff; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }}
        th, td {{
            text-align: left;
            padding: 10px 10px;
            border-bottom: 1px solid var(--border);
        }}
        th {{ color: var(--muted); font-weight: 600; text-transform: uppercase; font-size: 11px; }}
        tr.main-row:hover {{ background: var(--surface-hover); }}
        code {{ font-family: monospace; color: var(--primary); }}
        .comp-box {{ background: #0b0f19; padding: 18px; border-radius: 6px; border: 1px solid var(--border); }}
        .comp-box.highlight {{ border-color: var(--primary); }}
        .large-num {{ font-size: 36px; font-weight: 800; margin: 8px 0; }}
        .muted {{ color: var(--muted); font-size: 12px; }}
        .expand-btn {{
            background: #263352;
            color: #cbd5e1;
            border: none;
            padding: 4px 8px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 11px;
        }}
        .expand-btn:hover {{ background: var(--primary); color: #0b0f19; }}
        .detail-panel {{
            background: #0b0f19;
            padding: 16px;
            border-radius: 6px;
            border: 1px solid var(--border);
            margin: 8px 0;
        }}
        .code-block {{
            background: #060911;
            color: #a5b4fc;
            padding: 12px;
            border-radius: 6px;
            font-family: monospace;
            font-size: 11px;
            overflow-x: auto;
            max-height: 250px;
            border: 1px solid #1e2942;
        }}
        .bar-container {{
            background: #060911;
            border-radius: 4px;
            height: 18px;
            width: 100%;
            overflow: hidden;
            margin: 4px 0 10px 0;
        }}
        .bar-fill {{
            height: 100%;
            background: var(--primary);
            border-radius: 4px;
            transition: width 0.3s ease;
        }}
    </style>
    <script>
        function toggleDetail(id) {{
            const el = document.getElementById(id);
            if (el.style.display === 'none' || el.style.display === '') {{
                el.style.display = 'table-row';
            }} else {{
                el.style.display = 'none';
            }}
        }}
    </script>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>Adaptive Coding Agent Harness</h1>
                <p class="muted">Experimental Benchmark & Scaffolding Evaluation Dashboard (OpenCode + Gemini)</p>
            </div>
            <div>
                <span class="badge success">Active SQLite: runs.db</span>
            </div>
        </header>

        <!-- 6 KPI Metric Cards -->
        <div class="grid grid-6" style="margin-bottom: 20px;">
            <div class="card metric-card">
                <h4>Total Runs</h4>
                <p class="value">{metrics.total_tasks}</p>
            </div>
            <div class="card metric-card">
                <h4>Success Rate</h4>
                <p class="value" style="color: var(--success);">{metrics.success_rate:.1f}%</p>
            </div>
            <div class="card metric-card">
                <h4>Test Pass Rate</h4>
                <p class="value" style="color: var(--primary);">{metrics.test_pass_rate:.1f}%</p>
            </div>
            <div class="card metric-card">
                <h4>Avg Runtime</h4>
                <p class="value">{metrics.avg_duration_seconds:.2f}s</p>
            </div>
            <div class="card metric-card">
                <h4>Avg Tokens</h4>
                <p class="value">{metrics.avg_tokens_per_task:,.0f}</p>
            </div>
            <div class="card metric-card">
                <h4>Avg Iterations</h4>
                <p class="value">{metrics.avg_iterations:.2f}</p>
            </div>
        </div>

        {comp_header}

        <!-- Ablation Study Summary Table -->
        <div class="card">
            <h3>Ablation Configurations Matrix</h3>
            <table>
                <thead>
                    <tr>
                        <th>Configuration</th>
                        <th>Runs</th>
                        <th>Success Rate</th>
                        <th>Test Pass Rate</th>
                        <th>Avg Runtime</th>
                        <th>Avg Tokens</th>
                        <th>Avg Iterations</th>
                    </tr>
                </thead>
                <tbody>
                    {ablation_table_html}
                </tbody>
            </table>
        </div>

        <!-- Analytical Charts & Distributions -->
        <div class="grid grid-4">
            <div class="card">
                <h4>Success by Difficulty</h4>
                <div style="margin-top: 8px;">
                    <div><span class="muted">Easy ({diff_stats['easy']['pass']}/{diff_stats['easy']['total']}):</span></div>
                    <div class="bar-container">
                        <div class="bar-fill" style="width: {(diff_stats['easy']['pass'] / diff_stats['easy']['total'] * 100) if diff_stats['easy']['total'] else 0}%; background: #10b981;"></div>
                    </div>
                    <div><span class="muted">Medium ({diff_stats['medium']['pass']}/{diff_stats['medium']['total']}):</span></div>
                    <div class="bar-container">
                        <div class="bar-fill" style="width: {(diff_stats['medium']['pass'] / diff_stats['medium']['total'] * 100) if diff_stats['medium']['total'] else 0}%; background: #38bdf8;"></div>
                    </div>
                    <div><span class="muted">Hard ({diff_stats['hard']['pass']}/{diff_stats['hard']['total']}):</span></div>
                    <div class="bar-container">
                        <div class="bar-fill" style="width: {(diff_stats['hard']['pass'] / diff_stats['hard']['total'] * 100) if diff_stats['hard']['total'] else 0}%; background: #f59e0b;"></div>
                    </div>
                </div>
            </div>

            <div class="card">
                <h4>Success by Category</h4>
                <div style="margin-top: 8px;">
                    <div><span class="muted">Bug Fixes ({cat_stats['bug_fix']['pass']}/{cat_stats['bug_fix']['total']}):</span></div>
                    <div class="bar-container">
                        <div class="bar-fill" style="width: {(cat_stats['bug_fix']['pass'] / cat_stats['bug_fix']['total'] * 100) if cat_stats['bug_fix']['total'] else 0}%;"></div>
                    </div>
                    <div><span class="muted">Features ({cat_stats['feature']['pass']}/{cat_stats['feature']['total']}):</span></div>
                    <div class="bar-container">
                        <div class="bar-fill" style="width: {(cat_stats['feature']['pass'] / cat_stats['feature']['total'] * 100) if cat_stats['feature']['total'] else 0}%;"></div>
                    </div>
                    <div><span class="muted">Testing ({cat_stats['testing']['pass']}/{cat_stats['testing']['total']}):</span></div>
                    <div class="bar-container">
                        <div class="bar-fill" style="width: {(cat_stats['testing']['pass'] / cat_stats['testing']['total'] * 100) if cat_stats['testing']['total'] else 0}%;"></div>
                    </div>
                    <div><span class="muted">Migration ({cat_stats['migration']['pass']}/{cat_stats['migration']['total']}):</span></div>
                    <div class="bar-container">
                        <div class="bar-fill" style="width: {(cat_stats['migration']['pass'] / cat_stats['migration']['total'] * 100) if cat_stats['migration']['total'] else 0}%;"></div>
                    </div>
                </div>
            </div>

            <div class="card">
                <h4>Failure Taxonomy</h4>
                <ul style="list-style:none; padding:0; margin:8px 0 0 0; font-size:11px;">
                    {''.join(f"<li style='display:flex; justify-content:space-between; padding:4px 0; border-bottom:1px solid #1e2942;'><code>{cat}</code><strong>{cnt}</strong></li>" for cat, cnt in metrics.failure_breakdown.items()) if metrics.failure_breakdown else "<p class='muted'>No failures recorded.</p>"}
                </ul>
            </div>

            <div class="card">
                <h4>Iterations Distribution</h4>
                <div style="margin-top: 8px; font-size: 11px;">
                    {''.join(f"<div>Iter {it}: <strong>{cnt} runs</strong></div><div class='bar-container'><div class='bar-fill' style='width: {(cnt / metrics.total_tasks * 100) if metrics.total_tasks else 0}%;'></div></div>" for it, cnt in sorted(iter_dist.items()))}
                </div>
            </div>
        </div>

        <!-- Task Run Details Table -->
        <div class="card">
            <h3>Recent Executions & Task Diagnostics (Click Row to Expand)</h3>
            <div style="overflow-x: auto;">
                <table>
                    <thead>
                        <tr>
                            <th>Run ID</th>
                            <th>Task</th>
                            <th>Configuration</th>
                            <th>Status</th>
                            <th>Iterations</th>
                            <th>Duration</th>
                            <th>Tokens</th>
                            <th>Failure Category</th>
                            <th>Hidden Test</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
"""
    return HTMLResponse(content=html)
