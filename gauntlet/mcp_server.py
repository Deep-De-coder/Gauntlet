"""
gauntlet/mcp_server.py

Gauntlet MCP Server — exposes Gauntlet as a tool inside Cursor and Antigravity.

Two tools:
  1. gauntlet_eval_prompt  — evaluate any model+system prompt combo
  2. gauntlet_eval_file    — paste agent code; Gauntlet extracts the prompt and evaluates it

Usage:
  python -m gauntlet.mcp_server
"""

import asyncio
import json
import re

import mcp.server.stdio
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import (
    Tool,
    TextContent,
    ServerCapabilities,
    ToolsCapability,
)

from gauntlet.core.models import EvalRequest, EvalMode, AgentProvider
from gauntlet.core.runner import run_eval

# --------------------------------------------------------------------------- #
# Server setup
# --------------------------------------------------------------------------- #

server = Server("gauntlet")


# --------------------------------------------------------------------------- #
# Tool definitions — these are what the IDE sees and can call
# --------------------------------------------------------------------------- #

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="gauntlet_eval_prompt",
            description=(
                "Run an adversarial eval on any LLM agent defined by a model name and system prompt. "
                "Use this when you want to test how reliable an agent is before shipping it. "
                "Returns pass rate, per-scenario verdicts, and actionable recommendations."
            ),
            inputSchema={
                "type": "object",
                "required": ["goal", "agent_description", "agent_api_key", "agent_system_prompt"],
                "properties": {
                    "goal": {
                        "type": "string",
                        "description": "What the agent is supposed to do. Be specific.",
                        "example": "Classify a support ticket as billing, technical, or general.",
                    },
                    "agent_description": {
                        "type": "string",
                        "description": "One sentence describing the agent pipeline.",
                        "example": "Single Claude call with a classification system prompt.",
                    },
                    "agent_api_key": {
                        "type": "string",
                        "description": "API key for the agent under test (Anthropic or OpenAI).",
                    },
                    "agent_system_prompt": {
                        "type": "string",
                        "description": "The system prompt that defines the agent's behaviour.",
                        "example": "You are a support ticket classifier. Reply with only one word: billing, technical, or general.",
                    },
                    "agent_model": {
                        "type": "string",
                        "description": "Model name. Default: claude-sonnet-4-20250514",
                        "default": "claude-sonnet-4-20250514",
                    },
                    "agent_provider": {
                        "type": "string",
                        "enum": ["anthropic", "openai"],
                        "description": "LLM provider. Default: anthropic",
                        "default": "anthropic",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["standard", "adversarial", "full"],
                        "description": "Eval mode. 'full' runs both realistic and adversarial scenarios.",
                        "default": "full",
                    },
                    "runs": {
                        "type": "integer",
                        "description": "Number of scenarios to generate. Default: 3",
                        "default": 3,
                        "minimum": 1,
                        "maximum": 20,
                    },
                    "success_criteria": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional custom pass/fail rules for the judge.",
                        "example": ["Response must be exactly one word", "Response must be one of: billing, technical, general"],
                    },
                },
            },
        ),
        Tool(
            name="gauntlet_eval_file",
            description=(
                "Paste Python agent code and Gauntlet will extract the system prompt, "
                "then run an adversarial eval automatically. "
                "Use this when you have an agent.py open in your editor and want to test it instantly."
            ),
            inputSchema={
                "type": "object",
                "required": ["goal", "agent_code", "agent_api_key"],
                "properties": {
                    "goal": {
                        "type": "string",
                        "description": "What the agent is supposed to do.",
                        "example": "Summarise a news article in three bullet points.",
                    },
                    "agent_code": {
                        "type": "string",
                        "description": "The full Python source code of the agent file.",
                    },
                    "agent_api_key": {
                        "type": "string",
                        "description": "API key for the agent under test.",
                    },
                    "agent_model": {
                        "type": "string",
                        "description": "Model name used by the agent. Default: claude-sonnet-4-20250514",
                        "default": "claude-sonnet-4-20250514",
                    },
                    "agent_provider": {
                        "type": "string",
                        "enum": ["anthropic", "openai"],
                        "default": "anthropic",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["standard", "adversarial", "full"],
                        "default": "full",
                    },
                    "runs": {
                        "type": "integer",
                        "default": 3,
                        "minimum": 1,
                        "maximum": 20,
                    },
                    "success_criteria": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional custom pass/fail rules.",
                    },
                },
            },
        ),
    ]


# --------------------------------------------------------------------------- #
# Tool handlers
# --------------------------------------------------------------------------- #

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:

    if name == "gauntlet_eval_prompt":
        return await _handle_eval_prompt(arguments)

    elif name == "gauntlet_eval_file":
        return await _handle_eval_file(arguments)

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _handle_eval_prompt(args: dict) -> list[TextContent]:
    """Handle gauntlet_eval_prompt tool call."""
    try:
        request = EvalRequest(
            goal=args["goal"],
            agent_description=args["agent_description"],
            agent_api_key=args["agent_api_key"],
            agent_system_prompt=args["agent_system_prompt"],
            agent_model=args.get("agent_model", "claude-sonnet-4-20250514"),
            agent_provider=AgentProvider(args.get("agent_provider", "anthropic")),
            mode=EvalMode(args.get("mode", "full")),
            runs=args.get("runs", 3),
            success_criteria=args.get("success_criteria", []),
        )
        report = await run_eval(request)
        return [TextContent(type="text", text=_format_report(report))]

    except Exception as exc:
        return [TextContent(type="text", text=f"Gauntlet error: {exc}")]


async def _handle_eval_file(args: dict) -> list[TextContent]:
    """
    Handle gauntlet_eval_file tool call.
    Extracts the system prompt from the agent code automatically.
    """
    code = args["agent_code"]

    # Extract system prompt from common patterns in agent code
    system_prompt = _extract_system_prompt(code)

    if not system_prompt:
        return [TextContent(
            type="text",
            text=(
                "Gauntlet could not find a system prompt in the provided code.\n"
                "Make sure your code contains a string assigned to a variable named "
                "`system_prompt`, `SYSTEM_PROMPT`, or passed as `system=` in an API call.\n\n"
                "Alternatively use `gauntlet_eval_prompt` and paste your system prompt directly."
            ),
        )]

    try:
        request = EvalRequest(
            goal=args["goal"],
            agent_description=f"Agent extracted from code file. System prompt: {system_prompt[:100]}...",
            agent_api_key=args["agent_api_key"],
            agent_system_prompt=system_prompt,
            agent_model=args.get("agent_model", "claude-sonnet-4-20250514"),
            agent_provider=AgentProvider(args.get("agent_provider", "anthropic")),
            mode=EvalMode(args.get("mode", "full")),
            runs=args.get("runs", 3),
            success_criteria=args.get("success_criteria", []),
        )
        report = await run_eval(request)
        return [TextContent(type="text", text=_format_report(report))]

    except Exception as exc:
        return [TextContent(type="text", text=f"Gauntlet error: {exc}")]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _extract_system_prompt(code: str) -> str | None:
    """
    Try to extract a system prompt from Python agent code.
    Handles the most common patterns developers use.
    """
    patterns = [
        # system_prompt = "..." or system_prompt = """..."""
        r'system_prompt\s*=\s*["\'{3}](.*?)["\'{3}]',
        r'SYSTEM_PROMPT\s*=\s*["\'{3}](.*?)["\'{3}]',
        # system="..." in API calls
        r'system\s*=\s*["\'{3}](.*?)["\'{3}]',
        # {"role": "system", "content": "..."}
        r'"role"\s*:\s*"system"\s*,\s*"content"\s*:\s*"(.*?)"',
        r"'role'\s*:\s*'system'\s*,\s*'content'\s*:\s*'(.*?)'",
    ]

    for pattern in patterns:
        match = re.search(pattern, code, re.DOTALL | re.IGNORECASE)
        if match:
            prompt = match.group(1).strip()
            if len(prompt) > 10:  # ignore empty or trivial matches
                return prompt

    return None


def _format_report(report) -> str:
    """Format the EvalReport into a clean, readable summary for the IDE."""
    lines = [
        f"## Gauntlet Eval Report — {report.eval_id}",
        f"",
        f"**Goal:** {report.goal}",
        f"**Mode:** {report.mode}",
        f"**Pass rate:** {report.pass_rate:.0%} ({report.passed}/{report.total_runs})",
        f"**Avg cost:** ${report.avg_cost_usd:.4f}",
        f"**Avg latency:** {report.avg_latency_ms:.0f}ms",
        f"",
        f"---",
        f"",
        f"### Scenario Results",
    ]

    for r in report.scenarios:
        status = "✅ PASS" if r.passed else "❌ FAIL"
        lines += [
            f"",
            f"**{r.scenario_id}** {status}",
            f"- Input: {r.scenario_input[:120]}...",
            f"- Output: {r.agent_output[:120]}...",
            f"- Reasoning: {r.judge_reasoning}",
        ]

    if report.adversarial_findings:
        lines += [
            f"",
            f"---",
            f"",
            f"### Adversarial Findings",
        ]
        for finding in report.adversarial_findings:
            lines.append(f"- {finding}")

    if report.recommendations:
        lines += [
            f"",
            f"---",
            f"",
            f"### Recommendations",
        ]
        for i, rec in enumerate(report.recommendations, 1):
            lines.append(f"{i}. {rec}")

    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="gauntlet",
                server_version="0.1.0",
                capabilities=ServerCapabilities(
                    tools=ToolsCapability(listChanged=False),
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())