"""Rollback applied SEO changes from SQLite history. Dry-run by default."""

import sqlite3
import time
from typing import Any

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from scripts._paths import DB_PATH as _DB_PATH
from scripts.apply.update_alt_text import ShopifyUserError as AltUserError
from scripts.apply.update_alt_text import update_image_alt
from scripts.apply.update_meta import ShopifyUserError as MetaUserError
from scripts.apply.update_meta import update_collection_seo, update_product_seo

load_dotenv()

console = Console()


_SKIP_INSTRUCTIONS: dict[str, str] = {
    "url_redirect": (
        "URL redirects must be removed manually: Shopify Admin > Navigation > URL Redirects."
    ),
    "metafield.custom.json_ld": (
        "JSON-LD metafields must be removed manually: "
        "Shopify Admin > Products > [product] > Metafields > custom.json_ld."
    ),
}


class RollbackError(Exception):
    """Raised when a revert cannot be performed automatically."""


def load_changes(
    db_path: str,
    ids: list[int] | None = None,
    since: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch applied seo_changes rows from SQLite.

    Args:
        db_path: Path to the SQLite database.
        ids: Specific row IDs to load (status='applied' only).
        since: ISO datetime string — load rows applied at or after this timestamp.

    Returns:
        List of row dicts ordered by id (descending when since is provided,
        so the most recent changes are reverted first).
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    if ids is not None:
        placeholders = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT * FROM seo_changes WHERE id IN ({placeholders}) AND status = 'applied'",
            ids,
        ).fetchall()
    elif since is not None:
        rows = conn.execute(
            "SELECT * FROM seo_changes WHERE applied_at >= ? AND status = 'applied' ORDER BY id DESC",
            (since,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM seo_changes WHERE status = 'applied' ORDER BY id"
        ).fetchall()

    conn.close()
    return [dict(row) for row in rows]


def mark_reverted(db_path: str, row_id: int) -> None:
    """Set a seo_changes row status to 'reverted'.

    Args:
        db_path: Path to the SQLite database.
        row_id: Row ID to update.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE seo_changes SET status = 'reverted' WHERE id = ?", (row_id,))
    conn.commit()
    conn.close()


def revert_row(
    row: dict[str, Any],
    endpoint: str | None = None,
    headers: dict[str, str] | None = None,
) -> None:
    """Revert a single seo_changes row by restoring old_value via Shopify API.

    Args:
        row: Dict from seo_changes table.
        endpoint: GraphQL endpoint (resolved from .env if omitted).
        headers: Request headers (resolved from .env if omitted).

    Raises:
        RollbackError: If the field is non-revertible or the mutation fails.
    """
    field: str = row["field"]
    resource_id: str = row["resource_id"]
    resource_type: str = row["resource_type"]
    old_value: str | None = row["old_value"]

    # Fields that require manual action
    base_field = field.split(":")[0] if ":" in field else field
    if base_field in _SKIP_INSTRUCTIONS:
        raise RollbackError(
            f"Field '{field}' cannot be reverted automatically. " + _SKIP_INSTRUCTIONS[base_field]
        )

    try:
        if field == "seo.title":
            if resource_type == "collection":
                update_collection_seo(
                    resource_id,
                    seo_title=old_value,
                    seo_description=None,
                    endpoint=endpoint,
                    headers=headers,
                )
            else:
                update_product_seo(
                    resource_id,
                    seo_title=old_value,
                    seo_description=None,
                    endpoint=endpoint,
                    headers=headers,
                )

        elif field == "seo.description":
            if resource_type == "collection":
                update_collection_seo(
                    resource_id,
                    seo_title=None,
                    seo_description=old_value,
                    endpoint=endpoint,
                    headers=headers,
                )
            else:
                update_product_seo(
                    resource_id,
                    seo_title=None,
                    seo_description=old_value,
                    endpoint=endpoint,
                    headers=headers,
                )

        elif field.startswith("image.altText:"):
            image_id = field.split(":", 1)[1]
            update_image_alt(
                resource_id,
                image_id,
                old_value or "",
                endpoint=endpoint,
                headers=headers,
            )

        else:
            raise RollbackError(f"Unknown field type '{field}' — cannot revert automatically.")

    except (MetaUserError, AltUserError) as exc:
        raise RollbackError(str(exc)) from exc


def _changes_table(rows: list[dict[str, Any]], title: str = "Applied SEO Changes") -> Table:
    table = Table(title=title, show_lines=True)
    table.add_column("ID", style="dim", width=5)
    table.add_column("Applied at", width=20)
    table.add_column("Type", width=10)
    table.add_column("Resource ID", style="dim", max_width=35)
    table.add_column("Field", width=25)
    table.add_column("Old value", max_width=30)
    table.add_column("New value", style="green", max_width=30)

    for row in rows:
        table.add_row(
            str(row["id"]),
            str(row["applied_at"])[:19],
            row["resource_type"],
            str(row["resource_id"]).split("/")[-1],
            row["field"],
            str(row["old_value"] or "—")[:30],
            str(row["new_value"] or "—")[:30],
        )
    return table


@click.command()
@click.option("--list", "do_list", is_flag=True, help="List all applied changes")
@click.option(
    "--revert-ids",
    help="Comma-separated IDs to revert (e.g. 1,2,3)",
)
@click.option(
    "--revert-since",
    help="Revert all changes since this datetime (ISO, e.g. 2026-05-05T00:00:00)",
)
@click.option(
    "--dry-run/--apply",
    default=True,
    show_default=True,
    help="Dry-run by default. Pass --apply to write to Shopify.",
)
@click.option("--delay", default=0.5, show_default=True, help="Seconds between mutations")
@click.option("--db-path", default=_DB_PATH, show_default=True)
def main(
    do_list: bool,
    revert_ids: str | None,
    revert_since: str | None,
    dry_run: bool,
    delay: float,
    db_path: str,
) -> None:
    """Rollback applied SEO changes from SQLite history.

    Examples:

        python -m scripts.apply.rollback --list

        python -m scripts.apply.rollback --revert-ids 3,5 --dry-run

        python -m scripts.apply.rollback --revert-ids 3,5 --apply

        python -m scripts.apply.rollback --revert-since 2026-05-05T10:00:00 --apply
    """
    if do_list:
        rows = load_changes(db_path)
        if not rows:
            console.print("[yellow]No applied changes found in history.[/yellow]")
            return
        console.print(_changes_table(rows))
        console.print(f"\n[bold]{len(rows)}[/bold] change(s) applied total")
        return

    if revert_ids and revert_since:
        console.print("[red]Use either --revert-ids or --revert-since, not both.[/red]")
        raise SystemExit(1)

    if not revert_ids and not revert_since:
        console.print("[red]Specify --list, --revert-ids, or --revert-since.[/red]")
        raise SystemExit(1)

    # Resolve rows to revert
    if revert_ids:
        parsed_ids = [int(i.strip()) for i in revert_ids.split(",")]
        rows = load_changes(db_path, ids=parsed_ids)
        if not rows:
            console.print("[yellow]No applied changes found for the given IDs.[/yellow]")
            return
    else:
        rows = load_changes(db_path, since=revert_since)
        if not rows:
            console.print(f"[yellow]No applied changes found since {revert_since}.[/yellow]")
            return

    console.print(_changes_table(rows, title="Changes to Revert"))
    console.print(f"\n  [bold]{len(rows)}[/bold] change(s) to revert\n")

    if dry_run:
        console.print("[yellow]Dry-run — no writes to Shopify.[/yellow]")
        console.print("[dim]Re-run with --apply to revert these changes.[/dim]")
        return

    # Human confirmation gate (CLAUDE.md rule #3)
    console.print("[bold red]⚠  You are about to revert changes on Shopify.[/bold red]")
    confirm = click.prompt("Type 'yes' to confirm")
    if confirm.strip().lower() != "yes":
        console.print("[yellow]Aborted.[/yellow]")
        return

    reverted = errors = skipped = 0

    for row in rows:
        label = f"[dim]{row['id']}[/dim] {row['resource_type']} / {row['field']}"
        try:
            revert_row(row)
            mark_reverted(db_path, row["id"])
            console.print(f"  [green]✓[/green] {label}")
            reverted += 1
        except RollbackError as exc:
            if "cannot be reverted automatically" in str(exc):
                console.print(f"  [yellow]⊘[/yellow] {label} — skipped: {exc}")
                skipped += 1
            else:
                console.print(f"  [red]✗[/red] {label}: {exc}")
                errors += 1

        time.sleep(delay)

    console.print(
        f"\n[bold]Done:[/bold] {reverted} reverted, {skipped} skipped (manual), {errors} errors"
    )


if __name__ == "__main__":
    main()
