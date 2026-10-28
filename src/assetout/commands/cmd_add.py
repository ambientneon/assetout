# assetout/commands/cmd_add.py

from __future__ import annotations

from typing import Any
from pathlib import Path
from rich.console import Console

from assetout.constants import SKIP_DIR_NAMES
from assetout.utils.paths import (
    find_repo_root,
    get_data_path,
    get_rel_path
)
from assetout.utils.configs import (
    load_config,
    load_manifest,
    save_manifest,
)
from assetout.utils.helpers import (
    human_size,
    parse_size,
    safe_copy,
    make_manifest_entry,
    sync_gitignore_tracked,
    run_process
)


console = Console()

# public 
def run_add(paths: list[str]) -> None:
    root = find_repo_root(after_init=True)
    config = load_config(root)
    manifest = load_manifest(root)

    max_size = parse_size(config.get("max_git_file_size", "10MB"))
    use_only_git_files = bool(config.get("use_only_git_files", True))

    files = _collect_files(paths, root)
    if not files:
        console.print("[dim]No files to process.[/dim]")
        return

    added = skipped = errors = 0
    for path in files:
        result = _add_one(path, root, max_size, use_only_git_files, manifest)

        if result == "added":
            added += 1
        elif result == "skipped":
            skipped += 1
        else:
            errors += 1

    if added:
        save_manifest(root, manifest)
        
    sync_gitignore_tracked(root, manifest)

    console.print(f"\n[green]Added: {added},[/green] [yellow]skipped: {skipped},[/yellow] [red]errors: {errors}[/red]")


# private 
def _is_git_ignored(root: Path, rel: str) -> bool:
    """True, усли Git игнорирует файл."""
    result = run_process(
        ["git", "check-ignore", "-q", rel],
        cwd=root
    )

    # exit 0 = ignored, 1 = not ignored, 128 = error (not git и e.g.)
    return result.returncode == 0

def _collect_files(raw_paths: list[str], root: Path) -> list[Path]:
    """Разворачивает файлы и директории в плоский список файлов."""
    collected: list[Path] = []

    for raw in raw_paths:
        path = Path(raw).resolve()

        if path.is_file():
            collected.append(path)
            continue

        if path.is_dir():
            for child in path.rglob("*"):
                if not child.is_file():
                    continue

                # skip service directories
                try: 
                    rel_parts = child.relative_to(root).parts
                except ValueError:
                    continue

                if any(part in SKIP_DIR_NAMES for part in rel_parts):
                    continue

                collected.append(child)

            continue

        console.print(f"[yellow]Skip[/yellow] {raw} - path not found")

    # unique paths, stable order
    unique = sorted(set(collected), key=lambda p: str(p).lower())
    return unique


def _add_one(path: Path, root: Path, max_size: int, use_only_git_files: bool, manifest: dict[str, Any]) -> str:
    """Возвращает: 'added' | 'skipped' | 'error'."""
    rel = get_rel_path(path, root)

    if rel is None:
        console.print(f"[yellow]Skip[/yellow] {path} - outside repository")
        return "error"

    if not path.is_file():
        console.print(f"[yellow]Skip[/yellow] {rel} - not a file")
        return "error"

    if use_only_git_files and _is_git_ignored(root, rel):
        # dimMsg(f"Skip {rel} - ignored by Git")
        return "skipped"

    size = path.stat().st_size
    if size <= max_size:
        # warningMsg(f"Skip {rel} - {human_size(size)} ≤ max ({human_size(max_size)}). Use git add .")
        return "skipped"

    dest = get_data_path(root, rel)
    safe_copy(path, dest)

    manifest["files"][rel] = make_manifest_entry(root, path)
    console.print(f"[green]✓[/green] Added {rel} ({human_size(size)})")
    return "added"
