# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx", "python-dotenv", "pydantic>=2", "typer", "rich"]
# ///
"""O*NET CLI — query occupations, KSAOs, RIASEC, and database tables.

Usage:
    uv run onet/cli.py search "teacher"
    uv run onet/cli.py profile "25-2057.00"
    uv run onet/cli.py profile --keyword "marine biologist"
    uv run onet/cli.py tasks "25-2057.00"
    uv run onet/cli.py tables
    uv run onet/cli.py table "Skills"

Or, after `pip install -e .`, just `onet search "teacher"`.
"""

from __future__ import annotations

import sys
from pathlib import Path

_repo_root = str(Path(__file__).resolve().parents[1])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import typer  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from onet.client import OnetClient  # noqa: E402
from onet.models import ScoredElement  # noqa: E402

app = typer.Typer(name="onet", help="O*NET Web Services CLI", no_args_is_help=True)
console = Console()


def _bar(value: float, max_val: float = 100, width: int = 25) -> str:
    filled = int(value / max_val * width)
    return "█" * filled + "░" * (width - filled)


@app.command()
def search(keyword: str, limit: int = typer.Option(10, help="Max results")) -> None:
    """Search occupations by keyword."""
    with OnetClient() as onet:
        results = onet.search(keyword, end=limit)

    table = Table(title=f"Search: {keyword}")
    table.add_column("SOC Code", style="cyan")
    table.add_column("Title")
    for r in results:
        table.add_row(r.code, r.title)
    console.print(table)


@app.command()
def profile(
    code: str = typer.Argument(None, help="SOC code (e.g. 25-2057.00)"),
    keyword: str = typer.Option(None, "--keyword", "-k", help="Search keyword (uses first result)"),
    top: int = typer.Option(10, help="Show top N items per category"),
) -> None:
    """Full KSAO + RIASEC profile for an occupation."""
    with OnetClient() as onet:
        if keyword and not code:
            results = onet.search(keyword, end=5)
            if not results:
                console.print(f"[red]No results for '{keyword}'[/red]")
                raise typer.Exit(1)
            console.print(f"[dim]Search results for '{keyword}':[/dim]")
            for i, r in enumerate(results):
                console.print(f"  [{i}] {r.code} — {r.title}")
            code = results[0].code
            console.print(f"[dim]Using: {code}[/dim]\n")
        elif not code:
            console.print("[red]Provide a SOC code or --keyword[/red]")
            raise typer.Exit(1)

        prof = onet.occupation_profile(code)

    console.print(f"[bold]{prof.title}[/bold]  ({prof.code})")
    if prof.description:
        console.print(
            f"[dim]{prof.description[:200]}{'...' if len(prof.description) > 200 else ''}[/dim]\n"
        )

    # RIASEC
    riasec_table = Table(title="RIASEC (Holland Codes)")
    riasec_table.add_column("Type", style="cyan")
    riasec_table.add_column("Score", justify="right")
    riasec_table.add_column("", width=25)
    for item in sorted(prof.interests, key=lambda x: x.occupational_interest, reverse=True):
        riasec_table.add_row(
            item.name, str(int(item.occupational_interest)), _bar(item.occupational_interest)
        )
    console.print(riasec_table)

    # KSAO sections
    ksao_sections: list[tuple[str, list[ScoredElement]]] = [
        ("Knowledge", prof.knowledge),
        ("Skills", prof.skills),
        ("Abilities", prof.abilities),
        ("Work Styles", prof.work_styles),
    ]
    for title, items in ksao_sections:
        sorted_items = sorted(items, key=lambda x: x.importance, reverse=True)[:top]
        t = Table(title=title)
        t.add_column("Name", min_width=30)
        t.add_column("Score", justify="right")
        t.add_column("", width=25)
        for el in sorted_items:
            t.add_row(el.name, str(int(el.importance)), _bar(el.importance))
        console.print(t)


@app.command()
def interests(code: str) -> None:
    """RIASEC/Holland codes for an occupation."""
    with OnetClient() as onet:
        items = onet.interests(code)

    table = Table(title=f"RIASEC — {code}")
    table.add_column("Type", style="cyan")
    table.add_column("Score", justify="right")
    table.add_column("", width=25)
    for item in sorted(items, key=lambda x: x.occupational_interest, reverse=True):
        table.add_row(
            item.name, str(int(item.occupational_interest)), _bar(item.occupational_interest)
        )
    console.print(table)


@app.command()
def tasks(code: str) -> None:
    """Task statements for an occupation."""
    with OnetClient() as onet:
        items = onet.tasks(code)

    table = Table(title=f"Tasks — {code}")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Task")
    table.add_column("Importance", justify="right")
    for i, t in enumerate(sorted(items, key=lambda x: x.importance, reverse=True), 1):
        table.add_row(str(i), t.title, str(int(t.importance)))
    console.print(table)


@app.command()
def tech(code: str) -> None:
    """Technology skills and hot technologies."""
    with OnetClient() as onet:
        hot = onet.hot_technology(code)

    table = Table(title=f"Hot Technologies — {code}")
    table.add_column("Technology")
    table.add_column("Hot", justify="center")
    table.add_column("In Demand", justify="center")
    for t in hot:
        table.add_row(
            t.title,
            "🔥" if t.hot_technology else "",
            "✓" if t.in_demand else "",
        )
    console.print(table)


@app.command()
def related(code: str) -> None:
    """Related occupations."""
    with OnetClient() as onet:
        items = onet.related_occupations(code)

    table = Table(title=f"Related — {code}")
    table.add_column("SOC Code", style="cyan")
    table.add_column("Title")
    for r in items:
        table.add_row(r.code, r.title)
    console.print(table)


@app.command()
def tables() -> None:
    """List all O*NET database tables."""
    with OnetClient() as onet:
        items = onet.tables()

    table = Table(title="O*NET Database Tables")
    table.add_column("ID", style="cyan")
    table.add_column("Title")
    for t in items:
        table.add_row(t.id, t.title)
    console.print(table)


@app.command()
def table(
    table_id: str,
    limit: int = typer.Option(20, help="Max rows to display"),
) -> None:
    """Fetch rows from a database table."""
    with OnetClient() as onet:
        cols = onet.table_info(table_id)
        rows = onet.table_rows(table_id)

    col_names = [c.name for c in cols]
    t = Table(title=f"Table: {table_id} ({len(rows)} rows)")
    for name in col_names:
        t.add_column(name)
    for row in rows[:limit]:
        t.add_row(*(str(row.get(c, "")) for c in col_names))
    if len(rows) > limit:
        console.print(f"[dim]Showing {limit} of {len(rows)} rows[/dim]")
    console.print(t)


@app.command()
def crosswalk(keyword: str) -> None:
    """Military-to-civilian occupation crosswalk."""
    with OnetClient() as onet:
        items = onet.crosswalk_military(keyword)

    table = Table(title=f"Military Crosswalk: {keyword}")
    table.add_column("SOC Code", style="cyan")
    table.add_column("Title")
    for r in items:
        table.add_row(r.code, r.title)
    console.print(table)


if __name__ == "__main__":
    app()
