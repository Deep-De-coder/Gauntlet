"""
gauntlet/reporting.py

Shared report formatter used by the CLI, REST API, and MCP server.

Produces a human-readable report that explains:
  1. What Gauntlet did (the evaluation pipeline)
  2. What the user's agent/workflow did (the traced steps)
  3. Where failures occurred (per-agent pass rates for multi-agent)
  4. What to fix (recommendations)
"""
from __future__ import annotations
from gauntlet.core.models import EvalReport, EvalMode


def format_report(report: EvalReport, use_markdown: bool = True) -> str:
    """
    Format an EvalReport into a readable string.

    Parameters
    ----------
    report:
        The eval report to format.
    use_markdown:
        True for MCP/API output (markdown rendered in IDE).
        False for CLI output (Rich handles formatting separately).
    """
    b = "**" if use_markdown else ""  # bold marker
    lines: list[str] = []

    # ------------------------------------------------------------------ #
    # Header
    # ------------------------------------------------------------------ #
    lines += [
        f"## Gauntlet Eval Report — `{report.eval_id}`",
        f"",
        f"{b}Goal:{b} {report.goal}",
        f"{b}Mode:{b} {report.mode.value}",
        f"{b}Type:{b} {'Multi-agent workflow' if report.is_multi_agent else 'Single agent'}",
        f"",
    ]

    # Pass rate with colour signal
    rate_pct = f"{report.pass_rate:.0%}"
    if report.pass_rate >= 0.8:
        signal = "✅ Good"
    elif report.pass_rate >= 0.5:
        signal = "⚠️ Needs work"
    else:
        signal = "❌ Needs significant hardening"

    lines += [
        f"{b}Pass rate:{b} {rate_pct} ({report.passed}/{report.total_runs}) — {signal}",
        f"{b}Avg cost:{b} ${report.avg_cost_usd:.4f} per eval run",
        f"{b}Avg latency:{b} {report.avg_latency_ms:.0f}ms",
        f"",
        "---",
        "",
    ]

    # ------------------------------------------------------------------ #
    # Evaluation pipeline — what Gauntlet did
    # ------------------------------------------------------------------ #
    lines += [
        "### How This Eval Ran",
        "",
        "Gauntlet evaluated your agent through this pipeline:",
        "",
    ]

    # Count standard vs adversarial scenarios
    adv_count = len(report.adversarial_findings)
    std_count = report.total_runs - adv_count if report.mode == EvalMode.full else report.total_runs

    pipeline_steps = [
        ("ScenarioAgent",    f"generated {std_count} realistic test inputs from your goal"),
    ]
    if report.mode in (EvalMode.adversarial, EvalMode.full):
        pipeline_steps.append(
            ("AdversarialAgent", f"generated {adv_count} hostile inputs — prompt injection, edge cases, hallucination traps")
        )
    pipeline_steps += [
        ("→ YOUR AGENT",     f"called {report.total_runs} times, once per scenario"),
        ("JudgeAgent",       "scored each output pass/fail with reasoning"),
        ("ReportAgent",      "synthesised failures into prioritised recommendations"),
    ]

    for step, description in pipeline_steps:
        if step == "→ YOUR AGENT":
            lines.append(f"  **{step}** ← *{description}*")
        else:
            lines.append(f"  **{step}** → {description}")

    lines += ["", "---", ""]

    # ------------------------------------------------------------------ #
    # Multi-agent workflow section
    # ------------------------------------------------------------------ #
    if report.is_multi_agent and report.agent_pass_rates:
        lines += [
            "### Your Workflow",
            "",
        ]

        # Show the agent chain in order
        agent_names = [a.agent_name for a in sorted(
            report.agent_pass_rates, key=lambda x: x.pass_rate, reverse=True
        )]
        # Re-sort by order they appeared (use pass_rate list order as proxy)
        flow = " → ".join(a.agent_name for a in report.agent_pass_rates)
        lines += [
            f"Traced execution flow: **{flow}**",
            "",
        ]

        if report.bottleneck_agent:
            lines += [
                f"⚠️ **Bottleneck detected: {report.bottleneck_agent}**",
                f"This agent had the lowest pass rate and is most likely "
                f"the root cause of end-to-end failures.",
                "",
            ]

        # Per-agent pass rate table
        lines += [
            "#### Per-Agent Pass Rates",
            "",
            "| Agent | Passed | Total | Pass Rate | Status |",
            "|-------|--------|-------|-----------|--------|",
        ]

        for agent in report.agent_pass_rates:
            rate = f"{agent.pass_rate:.0%}"
            if agent.pass_rate >= 0.8:
                status = "✅"
            elif agent.pass_rate >= 0.5:
                status = "⚠️"
            else:
                status = "❌ bottleneck"
            lines.append(
                f"| {agent.agent_name} | {agent.passed} | {agent.total} | {rate} | {status} |"
            )

        lines += [""]

        # Common failure per agent
        failures_to_show = [a for a in report.agent_pass_rates if a.common_failure]
        if failures_to_show:
            lines += ["#### Most Common Failure Per Agent", ""]
            for agent in failures_to_show:
                if agent.pass_rate < 1.0:
                    lines.append(f"**{agent.agent_name}:** {agent.common_failure}")
            lines += [""]

        lines += ["---", ""]

    # ------------------------------------------------------------------ #
    # Scenario results
    # ------------------------------------------------------------------ #
    lines += ["### Scenario Results", ""]

    for r in report.scenarios:
        status = "✅ PASS" if r.passed else "❌ FAIL"
        lines += [
            f"**{r.scenario_id}** {status}",
            f"- Input: {r.scenario_input[:120]}{'...' if len(r.scenario_input) > 120 else ''}",
            f"- Output: {r.agent_output[:120]}{'...' if len(r.agent_output) > 120 else ''}",
            f"- Judge: {r.judge_reasoning}",
        ]

        # Show per-step breakdown for multi-agent scenarios
        if r.is_multi_agent and r.step_results:
            lines.append(f"- Workflow steps:")
            for step in r.step_results:
                step_status = "✅" if step.passed else "❌"
                lines.append(
                    f"  - {step_status} **{step.agent_name}**: {step.reasoning}"
                )
            if r.first_failure_agent:
                lines.append(
                    f"  - ⚠️ First failure introduced by: **{r.first_failure_agent}**"
                )

        lines.append("")

    # ------------------------------------------------------------------ #
    # Adversarial findings
    # ------------------------------------------------------------------ #
    if report.adversarial_findings:
        lines += ["---", "", "### Adversarial Findings", ""]
        for finding in report.adversarial_findings:
            lines.append(f"- {finding}")
        lines += [""]

    # ------------------------------------------------------------------ #
    # Recommendations
    # ------------------------------------------------------------------ #
    if report.recommendations:
        lines += ["---", "", "### Recommendations", ""]
        for i, rec in enumerate(report.recommendations, 1):
            lines.append(f"{i}. {rec}")
        lines += [""]

    # ------------------------------------------------------------------ #
    # Footer
    # ------------------------------------------------------------------ #
    lines += [
        "---",
        "",
        f"*Eval ID: `{report.eval_id}` — retrieve with `gauntlet show {report.eval_id}`*",
    ]

    return "\n".join(lines)