# assetout/commands/cmd_rm.py

from __future__ import annotations

from typing import Any
from pathlib import Path
from rich.console import Console

from assetout.utils.paths import (
    find_repo_root,
    get_data_path,
    resolve_rel
)
from assetout.utils.configs import (
    load_manifest,
    save_manifest,
)
from assetout.utils.helpers import (
    sync_gitignore_tracked
)


console = Console()

# public
def run_rm(paths: list[str], delete_project: bool = False) -> None:
    root = find_repo_root(after_init=True)
    manifest = load_manifest(root)

    removed = 0
    for raw in paths:
        rel = resolve_rel(raw, root, manifest)

        if rel is None:
            console.print(f"[yellow]Skip:[/yellow] {raw} - outside repository")
            continue

        if _rm_one(rel, root, manifest, delete_project):
            removed += 1

    if removed:
        save_manifest(root, manifest)
        console.print(f"\nRemoved: {removed}")

    sync_gitignore_tracked(root, manifest)


# private
def _cleanup_empty_dirs(start: Path, stop: Path) -> None:
    current = start
    while current != stop and current.exists():
        try: 
            current.rmdir() # only if empty
            current = current.parent
        except OSError:
            break


def _rm_one(rel: str, root: Path, manifest: dict[str, Any], delete_project: bool) -> bool:
    files = manifest.get("files", {})
    if rel not in files:
        console.print(f"[yellow]Not tracked {rel}[/yellow]")
        return False

    del files[rel]

    mirror_path = get_data_path(root, rel)
    if mirror_path.is_file():
        mirror_path.unlink()
        _cleanup_empty_dirs(mirror_path.parent, get_data_path(root))

    if delete_project:
        project_path = root / rel

        if project_path.is_file():
            project_path.unlink()
            console.print(f"[green]✓[/green] Removed {rel} (mirror + project)")
        else:
            console.print(f"[green]✓[/green] Removed {rel} (mirror; project file absent)")
    else:
        console.print(f"[green]✓[/green] Removed {rel}")

    return True
