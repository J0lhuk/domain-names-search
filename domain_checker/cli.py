from __future__ import annotations

import asyncio
import csv
import json
from pathlib import Path
from typing import Annotated

import httpx
import typer

from .config import load_settings
from .normalization import DomainValidationError, expand_names
from .pipeline import Checker
from .storage import ResultStore

app = typer.Typer(help="Evidence-aware domain availability checker.", no_args_is_help=True)


def _names(path: Path) -> list[str]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            if not reader.fieldnames or "name" not in reader.fieldnames:
                raise typer.BadParameter("CSV must contain a 'name' column")
            return [row["name"] for row in reader if row.get("name")]
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _fixtures(path: Path | None) -> dict[str, dict[str, str]] | None:
    if path is None:
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise typer.BadParameter("offline fixtures must be a JSON object keyed by domain")
    return data


async def _run_check(input_path: Path, zones: str, output: Path, config: Path | None, offline_fixtures: Path | None, force_refresh: bool, dry_run: bool, concurrency: int | None) -> None:
    settings = load_settings(config)
    if concurrency is not None:
        settings.concurrency = concurrency
    try:
        items = expand_names(_names(input_path), zones.split(","))
    except DomainValidationError as error:
        raise typer.BadParameter(str(error)) from error
    if dry_run:
        typer.echo(f"Would check {len(items)} unique domain(s); no network or files will be changed.")
        return
    store = ResultStore(output)
    try:
        async with httpx.AsyncClient(headers={"User-Agent": settings.user_agent}, timeout=httpx.Timeout(20.0), follow_redirects=True) as client:
            checker = Checker(settings, store, client, _fixtures(offline_fixtures))
            results = await checker.check_all(items, force_refresh)
        csv_path, json_path = store.export()
    finally:
        store.close()
    summary: dict[str, int] = {}
    for result in results:
        summary[result.availability_status] = summary.get(result.availability_status, 0) + 1
    free_domains = sorted(
        result.domain_unicode
        for result in results
        if result.availability_status.value == "available"
    )
    result_file = Path("result.txt")
    result_file.write_text("\n".join(free_domains) + ("\n" if free_domains else ""), encoding="utf-8")
    typer.echo(json.dumps({"checked": len(results), "summary": summary, "csv": str(csv_path), "json": str(json_path)}, ensure_ascii=False))


@app.command()
def check(
    input_path: Annotated[Path, typer.Option("--input", exists=True, readable=True)] = Path("names.txt"),
    zones: Annotated[str, typer.Option("--zones", help="Comma-separated TLDs for base names")] = "ru",
    output: Annotated[Path, typer.Option("--output")] = Path("results"),
    config: Annotated[Path | None, typer.Option("--config", exists=True, readable=True)] = None,
    offline_fixtures: Annotated[Path | None, typer.Option("--offline-fixtures", exists=True, readable=True)] = None,
    force_refresh: Annotated[bool, typer.Option("--force-refresh")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    concurrency: Annotated[int | None, typer.Option("--concurrency", min=1, max=50)] = None,
) -> None:
    """Check base names or full domains and write SQLite, JSONL, CSV and JSON results."""
    asyncio.run(_run_check(input_path, zones, output, config, offline_fixtures, force_refresh, dry_run, concurrency))


@app.command()
def resume(
    input_path: Annotated[Path, typer.Option("--input", exists=True, readable=True)] = Path("names.txt"),
    zones: Annotated[str, typer.Option("--zones")] = "ru",
    output: Annotated[Path, typer.Option("--output")] = Path("results"),
    config: Annotated[Path | None, typer.Option("--config", exists=True, readable=True)] = None,
    offline_fixtures: Annotated[Path | None, typer.Option("--offline-fixtures", exists=True, readable=True)] = None,
) -> None:
    """Continue a previous run, reusing results already stored in SQLite."""
    asyncio.run(_run_check(input_path, zones, output, config, offline_fixtures, False, False, None))


@app.command()
def export(output: Annotated[Path, typer.Option("--output", exists=True, file_okay=False)]) -> None:
    """Regenerate CSV and JSON from a saved result database."""
    store = ResultStore(output)
    try:
        csv_path, json_path = store.export()
    finally:
        store.close()
    typer.echo(f"Exported {csv_path} and {json_path}")


@app.command("providers")
def providers_command(config: Annotated[Path | None, typer.Option("--config", exists=True, readable=True)] = None) -> None:
    """Show enabled providers without making network requests."""
    settings = load_settings(config)
    registrar_configured = bool(settings.registrar.token) and (settings.registrar.kind.lower() == "godaddy" or bool(settings.registrar.endpoint))
    typer.echo(json.dumps({"registry": ["IANA RDAP", "RU/RF official WHOIS fallback"], "registrar": settings.registrar.kind if registrar_configured else "not configured", "history": {"historical_whois": bool(settings.history.historical_whois_endpoint), "wayback": settings.history.wayback, "certificate_transparency": settings.history.certificate_transparency}}, ensure_ascii=False, indent=2))


@app.command("validate-config")
def validate_config(config: Annotated[Path, typer.Option("--config", exists=True, readable=True)]) -> None:
    """Validate YAML structure and report only safe configuration state."""
    settings = load_settings(config)
    registrar_configured = bool(settings.registrar.token) and (settings.registrar.kind.lower() == "godaddy" or bool(settings.registrar.endpoint))
    typer.echo(f"Configuration valid; concurrency={settings.concurrency}; registrar={settings.registrar.kind}; registrar_configured={registrar_configured}")


if __name__ == "__main__":
    app()
