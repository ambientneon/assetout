# assetout/commands/cmd_pull.py

from __future__ import annotations

import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile

from typing import Any
from pathlib import Path
from rich.console import Console

from assetout.utils.paths import (
    find_repo_root,
    get_data_path
)
from assetout.utils.configs import (
    get_github_settings,
    load_config,
    load_manifest
)
from assetout.utils.helpers import (
    human_size,
    run_process,
    file_hash,
    get_owner_repo,
    check_bin_backend
)
from assetout.utils.packaging import (
    is_assetout_archive,
    list_release_assets
)


console = Console()

# public    
def run_pull() -> None:
    root = find_repo_root(after_init=True)
    config = load_config(root)
    manifest = load_manifest(root)

    check_bin_backend(config)
    if not manifest.get("files"):
        console.print("[yellow]Manifest is empty — nothing to pull.[/yellow]")
        return

    owner, repo = get_owner_repo(root, config)
    tag, asset_name = get_github_settings(config)
    data_dir = get_data_path(root)

    assets = list_release_assets(owner, repo, tag)
    archives = [a for a in assets if is_assetout_archive(a)]

    if not archives:
        console.print("[red]Error:[/red] no assetout archives found in the release.")
        raise SystemExit(1)

    console.print(f"  found {len(archives)} archive(s)")
    with tempfile.TemporaryDirectory(prefix="assetout-pull-") as tmp:
        tmp_dir = Path(tmp)

        console.print("  clear data/ ...", end=" ")
        _clear_data_dir(data_dir)
        console.print("[green]ok[/green]")

        total_files = 0
        for asset_name in sorted(archives):
            zip_path = tmp_dir / asset_name
            console.print(f"  download {asset_name} ...", end=" ")
            _download_asset(owner, repo, tag, asset_name, zip_path)

            console.print(f"  extract {asset_name} ...", end=" ")
            n = _extract_zip(zip_path, data_dir)
            total_files += n
            console.print(f"[green]ok[/green] ({n} files)")

    console.print(f"  total extracted: {total_files}")

    console.print("  verify manifest ...")
    ok, failed = _verify_against_manifest(root, manifest)
    console.print(f"  verified: {ok} ok, {failed} failed")

    if failed:
        raise SystemExit(1)

    console.print("[green]✓[/green] Pull complete (data/ only). Run sync to update project files.")


# private
def _download_url(url: str, dest: Path) -> bool:
    """Anonymous HTTPS, streaming to disk. True if ok"""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "assetout"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            with open(dest, "wb") as out:
                shutil.copyfileobj(resp, out, length=1024 * 1024)
        
        return dest.is_file() and dest.stat().st_size > 0
    
    except urllib.error.HTTPError as e:
        console.print(f"[dim]HTTPS download failed (HTTP {e.code})[/dim]")
        if dest.exists():
            dest.unlink(missing_ok=True)
        
        return False
    
    except Exception as e:
        console.print(f"[dim]HTTPS download failed: {type(e).__name__}: {e}[/dim]")
        if dest.exists():
            dest.unlink(missing_ok=True)
        
        return False


def _download_via_gh(owner: str, repo: str, tag: str, asset_name: str, dest: Path) -> None:
    result = run_process(["gh", "--version"])
    if result.returncode != 0:
        console.print(f"[red]Error:[/red] cannot download asset (HTTPS failed) and gh is not available.")
        console.print(f"Install GitHub CLI and run: gh auth login")
        raise SystemExit(result.returncode)

    # download to the dest.parent directory under the name asset
    out_dir = dest.parent
    result = run_process(
        [
            "gh",
            "release",
            "download",
            tag,
            "-R",
            f"{owner}/{repo}",
            "-p",
            asset_name,
            "-D",
            str(out_dir),
            "--clobber",
        ],
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        console.print(f"[red]Error:[/red] gh release download failed:\n{err}")
        raise SystemExit(result.returncode)

    downloaded = out_dir / asset_name
    if not downloaded.is_file():
        console.print(f"[red]Error:[/red] expected file not found after download: {downloaded}")
        raise SystemExit(1)

    if downloaded != dest:
        dest.write_bytes(downloaded.read_bytes())
        if downloaded.exists() and downloaded != dest:
            downloaded.unlink(missing_ok=True)


def _download_asset(
    owner: str,
    repo: str,
    tag: str,
    asset_name: str,
    dest: Path,
) -> None:
    url = f"https://github.com/{owner}/{repo}/releases/download/{tag}/{asset_name}"
    console.print(f"  try HTTPS: {url}")
    if _download_url(url, dest):
        console.print(f"  [green]ok[/green] ({human_size(dest.stat().st_size)})")
        return

    console.print("  fallback: gh release download ...")
    _download_via_gh(owner, repo, tag, asset_name, dest)
    console.print(f"  [green]ok[/green] ({human_size(dest.stat().st_size)})")


def _clear_data_dir(data_dir: Path) -> None:
    if data_dir.exists():
        shutil.rmtree(data_dir)

    data_dir.mkdir(parents=True, exist_ok=True)


def _extract_zip(zip_path: Path, data_dir: Path) -> int:
    count = 0
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue

            # path traversal protection
            name = info.filename.replace("\\", "/")
            if name.startswith("/") or ".." in name.split("/"):
                console.print(f"[yellow]Skip unsafe path in zip[/yellow] {name}")
                continue
            
            target = data_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
            
            count += 1
    
    return count


def _verify_against_manifest(root: Path, manifest: dict[str, Any]) -> tuple[int, int]:
    """Returns (ok, failed)."""
    data_dir = get_data_path(root)
    ok = failed = 0

    for rel, entry in sorted(manifest.get("files", {}).items()):
        local = data_dir / rel
        if not local.is_file():
            console.print(f"[red]missing[/red] {rel}")
            failed += 1
            continue

        size = local.stat().st_size
        expected_size = entry.get("size")
        if expected_size is not None and size != expected_size:
            console.print(
                f"[red]size mismatch[/red] {rel}: "
                f"got {human_size(size)}, expected {human_size(expected_size)}"
            )
            failed += 1
            continue

        expected_hash = entry.get("hash")
        if expected_hash:
            actual = file_hash(root, local)
            if actual != expected_hash:
                console.print(f"[red]hash mismatch[/red] {rel}")
                failed += 1
                continue

        ok += 1

    return ok, failed
