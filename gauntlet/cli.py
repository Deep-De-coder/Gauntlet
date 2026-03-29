"""
Gauntlet CLI (Typer + Rich).

Commands:
  gauntlet run   --goal "..." --agent-description "..." --agent-api-key "sk-ant-..." [options]
  gauntlet list
  gauntlet show  <eval_id>
  gauntlet serve [--port 8000]
"""
import asyncio
import typer
from rich.console import Console
from rich.table   import Table
from rich         import print as rprint

app     = typer.Typer(help="Gauntlet — adversarial eval harness for Claude agents.")
console = Console()


@app.command()
def run(
    goal: str              = typer.Option(..., help="Plain-English success criterion."),
    agent_description: str = typer.Option(..., "--agent-description", help="What your agent does."),
    agent_api_key: str     = typer.Option(..., "--agent-api-key", help="API key for the agent under test."),
    agent_model: str       = typer.Option("claude-sonnet-4-20250514", "--agent-model", help="Model name."),
    agent_provider: str    = typer.Option("anthropic", "--agent-provider", help="anthropic or openai"),
    agent_system_prompt: str = typer.Option("You are a helpful assistant.", "--system-prompt", help="System prompt for the agent."),
    mode: str              = typer.Option("standard", help="standard | adversarial | full"),
    runs: int              = typer.Option(5, help="Number of scenarios."),
):
    """Run an eval against a real agent (Claude or OpenAI)."""
    from gauntlet.core.models import EvalMode, EvalRequest, AgentProvider
    from gauntlet.core.runner import run_eval

    console.print(f"\n[bold]Gauntlet[/bold] — [cyan]{mode}[/cyan] mode, {runs} runs\n")

    req = EvalRequest(
        goal=goal,
        agent_description=agent_description,
        agent_api_key=agent_api_key,
        agent_model=agent_model,
        agent_provider=AgentProvider(agent_provider),
        agent_system_prompt=agent_system_prompt,
        mode=EvalMode(mode),
        runs=runs,
    )

    with console.status("Running eval...", spinner="dots"):
        report = asyncio.run(run_eval(req))

    color = "green" if report.pass_rate >= 0.8 else "yellow" if report.pass_rate >= 0.5 else "red"
    t = Table(title=f"Results — {report.eval_id}")
    t.add_column("Metric")
    t.add_column("Value", style="cyan")
    t.add_row("Pass rate",   f"[{color}]{report.pass_rate:.0%}[/{color}] ({report.passed}/{report.total_runs})")
    t.add_row("Avg cost",    f"${report.avg_cost_usd:.6f}")
    t.add_row("Avg latency", f"{report.avg_latency_ms:.0f} ms")
    t.add_row("Eval ID",     report.eval_id)
    console.print(t)

    if report.recommendations:
        console.print("\n[bold]Recommendations:[/bold]")
        for i, r in enumerate(report.recommendations, 1):
            console.print(f"  {i}. {r}")

    if report.adversarial_findings:
        console.print("\n[bold red]Adversarial findings:[/bold red]")
        for f in report.adversarial_findings:
            console.print(f"  • {f}")

    console.print(f"\n[dim]gauntlet show {report.eval_id}[/dim]\n")


@app.command()
def show(eval_id: str):
    """Print a full eval report as JSON."""
    from gauntlet.storage.db import get_report
    report = asyncio.run(get_report(eval_id))
    if not report:
        rprint(f"[red]Not found: {eval_id}[/red]")
        raise typer.Exit(1)
    console.print_json(report.model_dump_json(indent=2))


@app.command("list")
def list_evals(limit: int = typer.Option(10, help="How many recent evals to show.")):
    """List recent eval runs."""
    import datetime
    from gauntlet.storage.db import list_reports
    evals = asyncio.run(list_reports(limit=limit))
    if not evals:
        rprint("[dim]No evals yet. Run [bold]gauntlet run[/bold] to start.[/dim]")
        return
    t = Table(title="Recent Evals")
    t.add_column("Eval ID", style="cyan")
    t.add_column("Goal")
    t.add_column("Pass Rate", style="cyan")
    t.add_column("Created", style="dim")
    for e in evals:
        dt = datetime.datetime.fromtimestamp(e["created_at"]).strftime("%Y-%m-%d %H:%M")
        t.add_row(e["eval_id"], dt)
    console.print(t)


@app.command()
def serve(port: int = typer.Option(8000, help="API port.")):
    """Start the REST API server."""
    import uvicorn
    console.print(f"\n[bold]Gauntlet API[/bold] → [cyan]http://localhost:{port}[/cyan]")
    console.print(f"Docs → [cyan]http://localhost:{port}/docs[/cyan]\n")
    uvicorn.run("gauntlet.api.app:app", host="0.0.0.0", port=port, reload=True)


if __name__ == "__main__":
    app()