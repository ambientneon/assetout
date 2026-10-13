# assetout/commands/cmd_sync.py

from __future__ import annotations

import json

from typing import Any
from pathlib import Path
from datetime import datetime, timezone

from rich.console import Console

from assetout.constants import (
    ASSETOUT_DIR_NAME,
    SYNC_ALLOWED_POLICIES,
    SYNC_UNRESOLVED_FILE
)
from assetout.utils.paths import (
    find_repo_root,
    get_data_path,
    get_project_path,
)
from assetout.utils.configs import (
    load_config,
    load_manifest,
    save_manifest,
)
from assetout.utils.helpers import (
    human_size,
    file_hash,
    safe_copy,
    make_manifest_entry,
    sync_gitignore_tracked,
)


console = Console()

# public
def run_sync(policy: str | None = None, force: bool = False) -> None:
    root = find_repo_root(after_init=True)
    config = load_config(root)
    manifest = load_manifest(root)
    files = manifest.get("files") or {}

    if not files:
        console.print("[dim]Manifest is empty — nothing to sync.[/dim]")
        return

    policy = _resolve_policy(policy, config)
    console.print(f"[bold]Sync[/bold] policy={policy}, force={force}")

    copied = skipped = unresolved_count = 0
    unresolved: dict = {}
    manifest_dirty = False

    for rel in sorted(files.keys()):
        was_copied, entry, dirty = _process_one(root, rel, policy, force, manifest)

        if was_copied:
            copied += 1
        elif entry is None:
            skipped += 1
        else:
            unresolved[rel] = entry
            unresolved_count += 1

        if dirty:
            manifest_dirty = True

    if manifest_dirty:
        save_manifest(root, manifest)
        sync_gitignore_tracked(root, manifest)
        console.print("[dim]manifest updated[/dim]")

    if unresolved:
        _save_unresolved(root, unresolved)
        console.print(f"[dim]wrote .assetout/{SYNC_UNRESOLVED_FILE}[/dim]")
    else:
        _clear_unresolved(root)

    console.print(f"\nCopied: {copied}, skipped: {skipped}, unresolved: {unresolved_count}")
    if unresolved_count and not force and policy != "manual":
        console.print("Tip: re-run with [bold]--force[/bold] to overwrite mismatches.")


# private
def _file_info(root: Path, path: Path) -> tuple[bool, int | None, str | None]:
    """exists, size, hash."""
    if not path.is_file():
        return False, None, None
    
    return True, path.stat().st_size, file_hash(root, path)


def _reason(
    proj_ok: bool,
    data_ok: bool,
    proj_hash: str | None,
    data_hash: str | None,
) -> str:
    if not proj_ok and not data_ok:
        return "missing_both"
    
    if not proj_ok:
        return "missing_in_project"
    
    if not data_ok:
        return "missing_in_data"
    
    if proj_hash != data_hash:
        return "hash_mismatch"
    
    return "unknown"


def _save_unresolved(root: Path, entries: dict[str, Any]) -> None:
    path = root / ASSETOUT_DIR_NAME / SYNC_UNRESOLVED_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "files": entries,
    }
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _clear_unresolved(root: Path) -> None:
    path = root / ASSETOUT_DIR_NAME / SYNC_UNRESOLVED_FILE
    if path.exists():
        path.unlink()


def _resolve_policy(cli_policy: str | None, config: dict[str, Any]) -> str:
    policy = (cli_policy or config.get("sync_policy") or "remote").strip().lower()
    if policy not in SYNC_ALLOWED_POLICIES:
        console.print(f"[red]Error:[/red] unknown sync policy {policy!r}.")
        console.print(f"Allowed: {', '.join(SYNC_ALLOWED_POLICIES)}")
        raise SystemExit(1)
    
    return policy


# Policy handlers (каждая возвращает: copied, unresolved_entry | None)
def _handle_manual(
    rel: str,
    proj_ok: bool,
    data_ok: bool,
    proj_hash: str | None,
    data_hash: str | None,
    proj_size: int | None,
    data_size: int | None,
) -> tuple[bool, dict[str, Any] | None]:
    reason = _reason(proj_ok, data_ok, proj_hash, data_hash)
    entry = {
        "reason": reason,
        "project_exists": proj_ok,
        "data_exists": data_ok,
        "project_hash": proj_hash,
        "data_hash": data_hash,
        "project_size": proj_size,
        "data_size": data_size,
    }
    console.print(f"[yellow]unresolved[/yellow] {rel} ({reason})")
    return False, entry


def _handle_remote(
    root: Path,
    rel: str,
    proj: Path,
    data: Path,
    proj_ok: bool,
    data_ok: bool,
    data_size: int | None,
    force: bool,
) -> tuple[bool, dict[str, Any] | None]:
    if not data_ok:
        console.print(f"[red]missing in data[/red] {rel}")
        return False, {
            "reason": "missing_in_data",
            "project_exists": proj_ok,
            "data_exists": False,
        }

    if not proj_ok:
        safe_copy(data, proj)
        console.print(f"[green]→ project[/green] {rel} ({human_size(data_size or 0)})")
        return True, None

    # оба есть, хэши разные
    if force:
        safe_copy(data, proj)
        console.print(f"[green]→ project (force)[/green] {rel}")
        return True, None

    console.print(f"[yellow]mismatch[/yellow] {rel} — use --force to overwrite project")
    return False, {
        "reason": "hash_mismatch",
        "project_hash": file_hash(root, proj),
        "data_hash": file_hash(root, data),
        "project_size": proj.stat().st_size if proj_ok else None,
        "data_size": data_size,
    }


def _handle_local(
    root: Path,
    rel: str,
    proj: Path,
    data: Path,
    proj_ok: bool,
    data_ok: bool,
    proj_size: int | None,
    force: bool,
    manifest: dict[str, Any],
) -> tuple[bool, dict[str, Any] | None, bool]:
    """Возвращает (copied, unresolved_entry, manifest_dirty)."""
    if not proj_ok:
        console.print(f"[red]missing in project[/red] {rel}")
        return False, {
            "reason": "missing_in_project",
            "project_exists": False,
            "data_exists": data_ok,
        }, False

    if not data_ok:
        safe_copy(proj, data)
        manifest["files"][rel] = make_manifest_entry(root, data)
        console.print(f"[green]→ data[/green] {rel} ({human_size(proj_size or 0)})")
        return True, None, True

    if force:
        safe_copy(proj, data)
        manifest["files"][rel] = make_manifest_entry(root, data)
        console.print(f"[green]→ data (force)[/green] {rel}")
        return True, None, True

    console.print(f"[yellow]mismatch[/yellow] {rel} — use --force to overwrite data")
    return False, {
        "reason": "hash_mismatch",
        "project_hash": file_hash(root, proj),
        "data_hash": file_hash(root, data),
        "project_size": proj_size,
        "data_size": data.stat().st_size if data_ok else None,
    }, False


# Обработка одного файла
def _process_one(
    root: Path,
    rel: str,
    policy: str,
    force: bool,
    manifest: dict[str, Any],
) -> tuple[bool, dict[str, Any] | None, bool]:
    """
    Возвращает:
        copied: bool
        unresolved_entry: dict | None
        manifest_dirty: bool
    """
    proj = get_project_path(root, rel)
    data = get_data_path(root, rel)

    proj_ok, proj_size, proj_hash = _file_info(root, proj)
    data_ok, data_size, data_hash = _file_info(root, data)

    # оба есть и совпадают
    if proj_ok and data_ok and proj_hash == data_hash:
        return False, None, False

    if policy == "manual":
        copied, entry = _handle_manual(rel, proj_ok, data_ok, proj_hash, data_hash, proj_size, data_size)
        return copied, entry, False

    if policy == "remote":
        copied, entry = _handle_remote(root, rel, proj, data, proj_ok, data_ok, data_size, force)
        return copied, entry, False

    # policy == "local"
    return _handle_local(root, rel, proj, data, proj_ok, data_ok, proj_size, force, manifest)
