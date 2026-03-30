"""
gauntlet/mcp_server.py

Gauntlet MCP Server — exposes Gauntlet as a tool inside Cursor and Antigravity.

Three tools:
  1. gauntlet_find_agents  — scan workspace, find agent files, show numbered list
  2. gauntlet_eval_prompt  — evaluate any model+system prompt combo
  3. gauntlet_eval_file    — paste agent code; Gauntlet extracts prompt and evaluates

Usage:
  python -m gauntlet.mcp_server
"""

import asyncio
import json
import os
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
from gauntlet.reporting import format_report

server = Server("gauntlet")


# --------------------------------------------------------------------------- #
# Tool definitions
# --------------------------------------------------------------------------- #

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="gauntlet_find_agents",
            description=(
                "Scan the current workspace recursively for Python agent files. "
                "Detects system prompts, goals, model names, and providers automatically. "
                "Returns a numbered list — user just replies with the number to run eval. "
                "Trigger this when the user says 'find', 'find agents', 'find gauntlet', "
                "'scan', or 'what agents do I have'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "workspace_path": {
                        "type": "string",
                        "description": "Root path to scan. Defaults to current directory.",
                        "default": ".",
                    },
                },
            },
        ),
        Tool(
            name="gauntlet_eval_prompt",
            description=(
                "Run an adversarial eval on any LLM agent defined by a model name "
                "and system prompt. Returns pass rate, per-scenario verdicts, and recommendations."
            ),
            inputSchema={
                "type": "object",
                "required": ["goal", "agent_description", "agent_system_prompt"],
                "properties": {
                    "goal": {"type": "string"},
                    "agent_description": {"type": "string"},
                    "agent_system_prompt": {"type": "string"},
                    "agent_api_key": {
                        "type": "string",
                        "description": "API key for the agent. Falls back to ANTHROPIC_API_KEY env var if not provided.",
                    },
                    "agent_model": {"type": "string", "default": "claude-sonnet-4-20250514"},
                    "agent_provider": {"type": "string", "enum": ["anthropic", "openai"], "default": "anthropic"},
                    "mode": {"type": "string", "enum": ["standard", "adversarial", "full"], "default": "full"},
                    "runs": {"type": "integer", "default": 3, "minimum": 1, "maximum": 20},
                    "success_criteria": {"type": "array", "items": {"type": "string"}},
                },
            },
        ),
        Tool(
            name="gauntlet_eval_file",
            description=(
                "Paste Python agent code and Gauntlet will extract the system prompt "
                "then run an adversarial eval automatically."
            ),
            inputSchema={
                "type": "object",
                "required": ["goal", "agent_code"],
                "properties": {
                    "goal": {"type": "string"},
                    "agent_code": {"type": "string"},
                    "agent_api_key": {
                        "type": "string",
                        "description": "API key for the agent. Falls back to ANTHROPIC_API_KEY env var if not provided.",
                    },
                    "agent_model": {"type": "string", "default": "claude-sonnet-4-20250514"},
                    "agent_provider": {"type": "string", "enum": ["anthropic", "openai"], "default": "anthropic"},
                    "mode": {"type": "string", "enum": ["standard", "adversarial", "full"], "default": "full"},
                    "runs": {"type": "integer", "default": 3, "minimum": 1, "maximum": 20},
                    "success_criteria": {"type": "array", "items": {"type": "string"}},
                },
            },
        ),
    ]


# --------------------------------------------------------------------------- #
# Tool handlers
# --------------------------------------------------------------------------- #

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "gauntlet_find_agents":
        return await _handle_find_agents(arguments)
    elif name == "gauntlet_eval_prompt":
        return await _handle_eval_prompt(arguments)
    elif name == "gauntlet_eval_file":
        return await _handle_eval_file(arguments)
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


# --------------------------------------------------------------------------- #
# gauntlet_find_agents
# --------------------------------------------------------------------------- #

async def _handle_find_agents(args: dict) -> list[TextContent]:
    workspace = args.get("workspace_path", ".")
    found: list[dict] = []

    for root, dirs, files in os.walk(workspace):
        dirs[:] = [
            d for d in dirs
            if not d.startswith(".")
            and d not in {"__pycache__", ".venv", "venv", "env", "node_modules", "dist", "build"}
        ]
        for filename in files:
            if not filename.endswith(".py"):
                continue
            filepath = os.path.join(root, filename)
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    code = f.read()
            except Exception:
                continue
            agent_info = _detect_agent(code, filepath)
            if agent_info:
                found.append(agent_info)

    if not found:
        return [TextContent(
            type="text",
            text=(
                "No agent files found in this workspace.\n\n"
                "Gauntlet looks for Python files that contain:\n"
                "- A `system_prompt` or `SYSTEM_PROMPT` variable\n"
                "- A `system=` argument in an Anthropic or OpenAI API call\n"
                "- A dict with `{'role': 'system', 'content': '...'}`\n\n"
                "Make sure your agent file is in the current workspace."
            ),
        )]

    # Build table header
    lines = [
        f"Gauntlet found **{len(found)} agent file{'s' if len(found) > 1 else ''}** in your workspace:\n",
        "| # | File | Goal | Provider | Model |",
        "|---|------|------|----------|-------|",
    ]

    for i, agent in enumerate(found, 1):
        lines.append(
            f"| {i} | `{agent['relative_path']}` | {agent['goal_preview']} | {agent['provider']} | {agent['model']} |"
        )

    lines += [
        "",
        "---",
        "",
        "**To run Gauntlet on one of them, just say:**",
        "```",
        "Run Gauntlet on file [NUMBER]",
        "```",
        "",
        "No API key needed — using the key from your MCP config.",
    ]

    return [TextContent(type="text", text="\n".join(lines))]


def _detect_agent(code: str, filepath: str) -> dict | None:
    agent_signals = [
        r'system_prompt\s*=',
        r'SYSTEM_PROMPT\s*=',
        r'system\s*=\s*["\']',
        r'"role"\s*:\s*"system"',
        r"'role'\s*:\s*'system'",
        r'messages\.create\(',
        r'chat\.completions\.create\(',
    ]
    if not any(re.search(sig, code, re.IGNORECASE) for sig in agent_signals):
        return None

    system_prompt = _extract_system_prompt(code)
    prompt_preview = (
        (system_prompt[:80] + "...") if system_prompt and len(system_prompt) > 80
        else (system_prompt or "not detected")
    )

    # Detect goal from module docstring, function docstrings, or comments
    goal_preview = _extract_goal(code, filepath)

    provider = "openai" if re.search(r'openai|OpenAI|gpt-', code) else "anthropic"

    model = "claude-sonnet-4-20250514"
    for pattern in [r'claude-[a-z0-9\-\.]+', r'gpt-[a-z0-9\-\.]+', r'o[1-9]-[a-z0-9\-]+']:
        match = re.search(pattern, code)
        if match:
            model = match.group(0)
            break

    try:
        relative_path = os.path.relpath(filepath)
    except ValueError:
        relative_path = filepath

    return {
        "filepath": filepath,
        "relative_path": relative_path,
        "provider": provider,
        "model": model,
        "prompt_preview": prompt_preview,
        "goal_preview": goal_preview,
        "code": code,
        "system_prompt": system_prompt or "",
    }


def _extract_goal(code: str, filepath: str) -> str:
    """
    Try to infer what this agent does from:
    1. Module-level docstring
    2. First function/class docstring
    3. Comments at the top of the file
    4. Filename as a last resort
    """
    # Module docstring
    match = re.match(r'^\s*["\'{3}](.*?)["\'{3}]', code, re.DOTALL)
    if match:
        doc = match.group(1).strip().splitlines()[0].strip()
        if len(doc) > 10:
            return doc[:100]

    # First def or class docstring
    match = re.search(r'def \w+[^:]*:\s*["\'{3}](.*?)["\'{3}]', code, re.DOTALL)
    if match:
        doc = match.group(1).strip().splitlines()[0].strip()
        if len(doc) > 10:
            return doc[:100]

    # Top-of-file comment
    for line in code.splitlines()[:10]:
        line = line.strip().lstrip("#").strip()
        if len(line) > 15:
            return line[:100]

    # Fall back to filename
    name = os.path.basename(filepath).replace("_", " ").replace(".py", "")
    return f"Agent: {name}"


# --------------------------------------------------------------------------- #
# gauntlet_eval_prompt
# --------------------------------------------------------------------------- #

def _resolve_api_key(args: dict) -> str:
    """
    Get API key from args first, then fall back to environment.
    This means the user never needs to type their key if it's
    already set in the MCP config env block.
    """
    key = args.get("agent_api_key") or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise ValueError(
            "No API key found. Add ANTHROPIC_API_KEY to your MCP config env block "
            "or pass agent_api_key explicitly."
        )
    return key


async def _handle_eval_prompt(args: dict) -> list[TextContent]:
    try:
        api_key = _resolve_api_key(args)
        request = EvalRequest(
            goal=args["goal"],
            agent_description=args.get("agent_description", args["goal"]),
            agent_api_key=api_key,
            agent_system_prompt=args["agent_system_prompt"],
            agent_model=args.get("agent_model", "claude-sonnet-4-20250514"),
            agent_provider=AgentProvider(args.get("agent_provider", "anthropic")),
            mode=EvalMode(args.get("mode", "full")),
            runs=args.get("runs", 3),
            success_criteria=args.get("success_criteria", []),
        )
        report = await run_eval(request)
        return [TextContent(type="text", text=format_report(report, use_markdown=True))]
    except Exception as exc:
        return [TextContent(type="text", text=f"Gauntlet error: {exc}")]


# --------------------------------------------------------------------------- #
# gauntlet_eval_file
# --------------------------------------------------------------------------- #

async def _handle_eval_file(args: dict) -> list[TextContent]:
    code = args["agent_code"]
    system_prompt = _extract_system_prompt(code)

    if not system_prompt:
        return [TextContent(
            type="text",
            text=(
                "Gauntlet could not find a system prompt in the provided code.\n"
                "Make sure your code contains a string assigned to `system_prompt`, "
                "`SYSTEM_PROMPT`, or passed as `system=` in an API call.\n\n"
                "Alternatively use `gauntlet_eval_prompt` and paste your system prompt directly."
            ),
        )]

    try:
        api_key = _resolve_api_key(args)
        goal = args.get("goal") or _extract_goal(code, "agent.py")
        request = EvalRequest(
            goal=goal,
            agent_description=f"Agent extracted from file. Prompt: {system_prompt[:80]}...",
            agent_api_key=api_key,
            agent_system_prompt=system_prompt,
            agent_model=args.get("agent_model", "claude-sonnet-4-20250514"),
            agent_provider=AgentProvider(args.get("agent_provider", "anthropic")),
            mode=EvalMode(args.get("mode", "full")),
            runs=args.get("runs", 3),
            success_criteria=args.get("success_criteria", []),
        )
        report = await run_eval(request)
        return [TextContent(type="text", text=format_report(report, use_markdown=True))]
    except Exception as exc:
        return [TextContent(type="text", text=f"Gauntlet error: {exc}")]


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #

def _extract_system_prompt(code: str) -> str | None:
    import re as _re
    # Triple-quoted — must come before single/double quoted patterns
    for var in ["system_prompt", "SYSTEM_PROMPT", "system"]:
        for q in ['"""', "'''"]:
            eq = _re.escape(q)
            pat = rf'{var}\s*=\s*{eq}(.*?){eq}'
            m = _re.search(pat, code, _re.DOTALL | _re.IGNORECASE)
            if m and len(m.group(1).strip()) > 10:
                return m.group(1).strip()
    # Single/double quoted
    for var in ["system_prompt", "SYSTEM_PROMPT", "system"]:
        for q in ['"', "'"]:
            eq = _re.escape(q)
            pat = rf'{var}\s*=\s*{eq}(.*?){eq}'
            m = _re.search(pat, code, _re.DOTALL | _re.IGNORECASE)
            if m and len(m.group(1).strip()) > 10:
                return m.group(1).strip()
    # Dict-style messages array
    for pat in [
        r'"role"\s*:\s*"system"\s*,\s*"content"\s*:\s*"(.*?)"',
        r"'role'\s*:\s*'system'\s*,\s*'content'\s*:\s*'(.*?)'",
    ]:
        m = _re.search(pat, code, _re.DOTALL | _re.IGNORECASE)
        if m and len(m.group(1).strip()) > 10:
            return m.group(1).strip()
    return None


def _format_report(report) -> str:
    lines = [
        f"## Gauntlet Eval Report — {report.eval_id}",
        f"",
        f"**Goal:** {report.goal}",
        f"**Mode:** {report.mode}",
        f"**Pass rate:** {report.pass_rate:.0%} ({report.passed}/{report.total_runs})",
        f"**Avg cost:** ${report.avg_cost_usd:.4f}",
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
        lines += ["", "---", "", "### Adversarial Findings"]
        for finding in report.adversarial_findings:
            lines.append(f"- {finding}")

    if report.recommendations:
        lines += ["", "---", "", "### Recommendations"]
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