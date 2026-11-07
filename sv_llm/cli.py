from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from sv_llm.config import get_settings
from sv_llm.graph import run_verification
from sv_llm.report import build_report, render_markdown
from sv_llm.retrieval.loader import load_design

app = typer.Typer(help="SV-LLM: agentic SoC security verification.", no_args_is_help=True)
console = Console()


@app.command()
def inspect(design: Path = typer.Argument(..., help="Design directory (spec.md + RTL).")):
    """Show how a design will be chunked before spending any tokens."""
    settings = get_settings()
    loaded = load_design(design, budget=settings.chunk_chars)
    table = Table(title=f"{loaded.name}: {len(loaded.documents)} chunks")
    table.add_column("kind")
    table.add_column("source")
    table.add_column("scope")
    table.add_column("chars", justify="right")
    for doc in loaded.documents:
        meta = doc.metadata
        scope = meta.get("module") if meta["kind"] == "rtl" else meta.get("section")
        table.add_row(meta["kind"], meta["source"], scope or "-", str(len(doc.page_content)))
    console.print(table)


@app.command()
def run(
    design: Path = typer.Argument(..., help="Design directory (spec.md + RTL)."),
    out: Path = typer.Option(Path("report.md"), help="Markdown report path."),
    json_out: Path | None = typer.Option(None, help="Also dump the raw report as JSON."),
    no_retrieval: bool = typer.Option(
        False, help="Pass full documents to agents instead of retrieved chunks."
    ),
):
    """Run the supervisor / threat-model / detection / validation loop on a design."""
    from sv_llm.llm import get_chat_model, get_embeddings

    settings = get_settings()
    loaded = load_design(design, budget=settings.chunk_chars)
    llm = get_chat_model(settings)
    embeddings = None if no_retrieval else get_embeddings(settings)

    with console.status(f"verifying {loaded.name} with {settings.model}..."):
        state = run_verification(loaded, llm, embeddings, settings)

    report = build_report(state)
    out.write_text(render_markdown(report))
    if json_out:
        json_out.write_text(json.dumps(report.model_dump(mode="json"), indent=2))

    for step in report.trace:
        console.print(f"[dim]{step}[/dim]")
    console.print(
        f"[bold green]{len(report.findings)} findings[/bold green] across "
        f"{len(report.threats)} threats -> {out}"
    )


if __name__ == "__main__":
    app()
