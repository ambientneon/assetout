# assetout/commands/cmd_push.py

from __future__ import annotations

import tempfile
import zipfile

from typing import Any
from pathlib import Path
from rich.console import Console

from assetout.utils.paths import (
    find_repo_root,
    get_data_path,
)
from assetout.utils.configs import (
    get_github_settings,
    load_config,
    load_manifest,
)
from assetout.utils.helpers import (
    human_size,
    run_process,
    get_owner_repo,
    check_bin_backend,
)
from assetout.utils.packaging import (
    group_key,
    archive_prefix,
    split_into_chunks,
    filter_too_large,
    delete_assetout_archives,
    get_size_limits,
)


console = Console()

def run_push(replace_all: bool = False, update_tag: bool = True) -> None:
    root = find_repo_root(after_init=True)
    config = load_config(root)
    manifest = load_manifest(root)
    max_archive_bytes, max_file_bytes = get_size_limits(config)

    check_bin_backend(config)
    _check_gh()

    owner, repo = get_owner_repo(root, config)
    tag, _ = get_github_settings(config)
    group_by = bool((config.get("packaging") or {}).get("group_by_top_level", False))
    groups = _get_groups(root, manifest, group_by, owner, repo, tag, max_file_bytes, max_archive_bytes)
    archive_count = 0

    with tempfile.TemporaryDirectory(prefix="assetout-") as tmp:
        tmp_dir = Path(tmp)
        all_archives: list[Path] = []

        for group in sorted(groups.keys()):
            group_items = sorted(groups[group], key=lambda x: x[0].lower())
            archives = _pack_group(group, group_items, tmp_dir, max_archive_bytes)
            all_archives.extend(archives)

        _prepare_release(owner, repo, tag, root, update_tag=update_tag)

        if replace_all:
            console.print("  [bold]--replace-all[/bold]: cleaning old archives ...")
            n = delete_assetout_archives(owner, repo, tag)
            console.print(f"  removed {n} old archive(s)")

        for zip_path in all_archives:
            console.print(f"  upload {zip_path.name} ...", end=" ")
            _upload_one(owner, repo, tag, zip_path)
            console.print("[green]ok[/green]")

        archive_count = len(all_archives)

    console.print(f"[green]✓[/green] Push complete ({archive_count} archive(s))")


def _prepare_release(
    owner: str,
    repo: str,
    tag: str,
    root: Path,
    update_tag: bool = True,
) -> None:
    """
    Prepares a release so that the source code (zip/tar.gz) matches the current HEAD.

    --update-tag (default):
        git tag -f + force-push tag → GitHub updates the source archives.

    --no-update-tag:
        Delete the release along with the tag and recreate it.
    """
    _warn_if_dirty(root)

    if update_tag:
        console.print(f"  update tag {tag} → HEAD ...", end=" ")
        _move_tag_to_head(root, tag)
        console.print("[green]ok[/green]")

        # the release might already exist - we're just making sure it exists
        _ensure_release_exists(owner, repo, tag)
    else:
        console.print(f"  recreate release {tag} (no tag move) ...", end=" ")
        _delete_release_and_tag(owner, repo, tag)
        _create_release(owner, repo, tag)
        console.print("[green]ok[/green]")


def _warn_if_dirty(root: Path) -> None:
    res = run_process(["git", "status", "--porcelain"], cwd=root)
    if res.stdout.strip():
        console.print(
            "[yellow]Warning:[/yellow] working tree is not clean. "
            "Tag will point to the last commit, not to uncommitted changes."
        )


def _move_tag_to_head(root: Path, tag: str) -> None:
    # local
    res = run_process(["git", "tag", "-f", tag], cwd=root)
    if res.returncode != 0:
        err = (res.stderr or res.stdout or "").strip()
        console.print(f"\n[red]Error:[/red] cannot create/move local tag '{tag}':\n{err}")
        raise SystemExit(res.returncode)

    # force-push
    res = run_process(
        ["git", "push", "origin", f"refs/tags/{tag}", "--force"],
        cwd=root,
    )
    if res.returncode != 0:
        err = (res.stderr or res.stdout or "").strip()
        console.print(f"\n[red]Error:[/red] cannot force-push tag '{tag}':\n{err}")
        raise SystemExit(res.returncode)


def _delete_release_and_tag(owner: str, repo: str, tag: str) -> None:
    # --cleanup-tag removes both the release and the tag itself
    res = run_process([
        "gh", "release", "delete", tag,
        "-R", f"{owner}/{repo}",
        "--yes",
        "--cleanup-tag",
    ])
    
    # If there was no release, that's okay
    if res.returncode != 0:
        # check that the error is actually "not found"
        err = (res.stderr or res.stdout or "").lower()
        if "not found" not in err and "could not find" not in err:
            console.print(f"\n[yellow]Warning:[/yellow] failed to delete release '{tag}':\n{err.strip()}")


def _ensure_release_exists(owner: str, repo: str, tag: str) -> None:
    view = run_process(["gh", "release", "view", tag, "-R", f"{owner}/{repo}"])
    if view.returncode == 0:
        return
    _create_release(owner, repo, tag)


def _create_release(owner: str, repo: str, tag: str) -> None:
    created = run_process([
        "gh", "release", "create", tag,
        "-R", f"{owner}/{repo}",
        "--title", "Binary assets",
        "--notes", "Large binary assets managed by assetout.",
        "--latest=false",
    ])
    if created.returncode != 0:
        err = (created.stderr or created.stdout or "").strip()
        console.print(f"\n[red]Error:[/red] cannot create release '{tag}':\n{err}")
        raise SystemExit(created.returncode)


def _check_gh() -> None:
    result = run_process(["gh", "--version"])
    if result.returncode != 0:
        console.print(
            "[red]Error:[/red] GitHub CLI (gh) not found.\n"
            "Install: https://cli.github.com/\n"
            "Then run: gh auth login"
        )
        raise SystemExit(result.returncode)


def _get_groups(
    root: Path,
    manifest: dict[str, Any],
    group_by: bool,
    owner: str,
    repo: str,
    tag: str,
    max_file_bytes: int,
    max_archive_bytes: int,
) -> dict[str, Any]:
    items = _collect_files(root, manifest)
    if not items:
        console.print("[red]Error:[/red] manifest is empty or mirror files missing.")
        raise SystemExit(1)

    items = filter_too_large(items, max_file_bytes)
    if not items:
        console.print("[red]Error:[/red] no files left to upload after size filter.")
        raise SystemExit(1)

    groups: dict[str, list[tuple[str, Path, int]]] = {}
    for rel, path, size in items:
        key = group_key(rel, group_by)
        groups.setdefault(key, []).append((rel, path, size))

    console.print(f"[bold]Push[/bold] → {owner}/{repo} @ {tag}")
    console.print(f"  groups: {len(groups)}, group_by_top_level={group_by}")
    console.print(
        f"  limits: archive ≤ {human_size(max_archive_bytes)}, "
        f"file ≤ {human_size(max_file_bytes)}"
    )
    return groups


def _collect_files(root: Path, manifest: dict[str, Any]) -> list[tuple[str, Path, int]]:
    items: list[tuple[str, Path, int]] = []
    for rel, entry in sorted(manifest.get("files", {}).items()):
        local = get_data_path(root, rel)
        if not local.is_file():
            console.print(f"[red]Missing in mirror {rel}[/red]")
            continue
        items.append((rel, local, local.stat().st_size))
    return items


def _build_zip(items: list[tuple[str, Path, int]], zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for rel, local, _ in items:
            zf.write(local, arcname=rel.replace("\\", "/"))


def _upload_one(owner: str, repo: str, tag: str, zip_path: Path) -> None:
    result = run_process([
        "gh", "release", "upload", tag, str(zip_path),
        "-R", f"{owner}/{repo}",
        "--clobber",
    ])
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        console.print(f"[red]Error:[/red] upload {zip_path.name} failed:\n{err}")
        raise SystemExit(result.returncode)


def _pack_group(
    group: str,
    items: list[tuple[str, Path, int]],
    tmp_dir: Path,
    max_archive_bytes: int,
) -> list[Path]:
    prefix = archive_prefix(group)
    chunks = split_into_chunks(items, max_archive_bytes)
    result: list[Path] = []

    for idx, chunk in enumerate(chunks, start=1):
        asset_name = f"{prefix}-{idx:02d}.zip"
        zip_path = tmp_dir / asset_name
        _build_zip(chunk, zip_path)
        total = sum(s for _, _, s in chunk)
        console.print(f"  [cyan]{asset_name}[/cyan] — {len(chunk)} files, {human_size(total)}")
        result.append(zip_path)

    return result
