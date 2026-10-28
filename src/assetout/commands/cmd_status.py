# assetout/commands/cmd_status.py

from __future__ import annotations

from typing import Any
from pathlib import Path
from rich.console import Console
from rich.table import Table

from assetout.utils.paths import (
    find_repo_root,
    get_project_path,
    get_data_path,
)
from assetout.utils.configs import (
    load_config,
    load_manifest,
    get_github_settings,
)
from assetout.utils.helpers import (
    human_size,
    parse_size,
    file_hash,
    run_process,
)

console = Console()


def run_status() -> None:
    root = find_repo_root(after_init=True)
    config = load_config(root)
    manifest = load_manifest(root)
    files = manifest.get("files", {})

    if not files:
        console.print("[dim]No large files tracked yet.[/dim]")
        _print_release_tag_info(root, config)
        return

    table = Table(title="assetout status")
    table.add_column("Path", style="cyan")
    table.add_column("Size", justify="right")
    table.add_column("State")

    for rel, entry in sorted(files.items()):
        size = entry.get("size", 0)
        state = _state_for_file(root, rel, entry)
        table.add_row(rel, human_size(size), state)

    console.print(table)

    max_size = parse_size(config.get("max_git_file_size", "10MB"))
    console.print(f"\nTracked: {len(files)} file(s)")
    console.print(f"Max git size: {human_size(max_size)}")

    _print_release_tag_info(root, config)


def _print_release_tag_info(root: Path, config: dict[str, Any]) -> None:
    """Shows where the release tag points relative to HEAD."""
    tag, _ = get_github_settings(config)

    # local tag
    tag_res = run_process(["git", "rev-parse", "--short", f"{tag}^{{}}"], cwd=root)
    if tag_res.returncode != 0:
        console.print(f"\nRelease tag: [cyan]{tag}[/cyan] — [yellow]not found locally[/yellow]")
        return

    tag_sha = tag_res.stdout.strip()

    # HEAD
    head_res = run_process(["git", "rev-parse", "--short", "HEAD"], cwd=root)
    head_sha = head_res.stdout.strip() if head_res.returncode == 0 else "?"

    # how much commits behind
    behind = 0
    count_res = run_process(
        ["git", "rev-list", "--count", f"{tag}..HEAD"],
        cwd=root,
    )
    if count_res.returncode == 0 and count_res.stdout.strip().isdigit():
        behind = int(count_res.stdout.strip())

    if tag_sha == head_sha:
        status = "[green]same as HEAD[/green]"
    elif behind > 0:
        commits = "commit" if behind == 1 else "commits"
        status = f"[yellow]{behind} {commits} behind HEAD[/yellow]"
    else:
        status = "[dim]different from HEAD[/dim]"

    console.print(
        f"\nRelease tag: [cyan]{tag}[/cyan] → [bold]{tag_sha}[/bold]  ({status})"
    )


def _state_for_file(
    root: Path,
    rel: str,
    entry: dict[str, Any],
) -> str:
    project = get_project_path(root, rel)
    mirror = get_data_path(root, rel)

    proj_exists = project.is_file()
    mirror_exists = mirror.is_file()

    if not proj_exists and not mirror_exists:
        return "[red]missing both[/red]"

    if not proj_exists:
        return "[red]missing in project[/red]"

    if not mirror_exists:
        return "[yellow]missing in mirror[/yellow]"

    proj_hash = file_hash(root, project)
    mirror_hash = file_hash(root, mirror)
    expected = entry.get("hash")

    if proj_hash != expected:
        return "[yellow]project modified[/yellow]"

    if mirror_hash != expected:
        return "[yellow]mirror modified[/yellow]"

    if proj_hash != mirror_hash:
        return "[yellow]project ≠ mirror[/yellow]"

    return "[green]ok[/green]"
