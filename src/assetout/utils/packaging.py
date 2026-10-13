# assetout/utils/packaging.py

from __future__ import annotations

import re

from typing import Any
from pathlib import Path
from rich.console import Console

from assetout.constants import (
    DEFAULT_MAX_ARCHIVE_SIZE,
    DEFAULT_MAX_FILE_SIZE,
)
from assetout.utils.helpers import (
    human_size,
    parse_size,
    run_process
)


console = Console()

# public
def get_size_limits(config: dict[str, Any]) -> tuple[int, int]:
    """
    Возвращает (max_archive_bytes, max_file_bytes).
    Всегда читаем из конфига, константы — только fallback.
    """
    packaging = config.get("packaging") or {}

    archive_str = packaging.get("max_archive_size") or DEFAULT_MAX_ARCHIVE_SIZE
    file_str = packaging.get("max_file_size") or DEFAULT_MAX_FILE_SIZE

    return parse_size(archive_str), parse_size(file_str)


def group_key(rel: str, group_by_top_level: bool) -> str:
    """Ключ группы: '' для корня или имя первой папки."""
    if not group_by_top_level:
        return ""

    parts = rel.split("/")
    return parts[0] if len(parts) > 1 else ""


def archive_prefix(group: str) -> str:
    """projectA → projectA-binaries | '' → binaries"""
    return f"{group}-binaries" if group else "binaries"


def split_into_chunks(
    items: list[tuple[str, Path, int]],
    max_bytes: int,
) -> list[list[tuple[str, Path, int]]]:
    """Жадно набивает архивы по размеру. items уже отсортированы."""
    chunks: list[list[tuple[str, Path, int]]] = []
    current: list[tuple[str, Path, int]] = []
    current_size = 0

    for item in items:
        _, _, size = item

        if current and current_size + size > max_bytes:
            chunks.append(current)
            current = []
            current_size = 0
        
        current.append(item)
        current_size += size

    if current:
        chunks.append(current)
    
    return chunks


def filter_too_large(
    items: list[tuple[str, Path, int]],
    max_bytes: int,
) -> list[tuple[str, Path, int]]:
    """Пропускает файлы ≥ {human_size(max_bytes)} с предупреждением."""
    ok = []
    for rel, path, size in items:
        if size >= max_bytes:
            console.print(f"[yellow]Skip:[/yellow] {rel} — {human_size(size)} ≥ {human_size(max_bytes)}. Upload this file manually.")
            continue
        
        ok.append((rel, path, size))
    
    return ok


def list_release_assets(owner: str, repo: str, tag: str) -> list[str]:
    result = run_process([
        "gh", "release", "view", tag,
        "-R", f"{owner}/{repo}",
        "--json", "assets",
        "--jq", ".assets[].name",
    ])

    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        console.print(f"[red]Error:[/red] cannot list release assets:\n{err}")
        raise SystemExit(result.returncode)
    
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def is_assetout_archive(name: str) -> bool:
    return bool(re.fullmatch(r"(?:[\w.-]+-)?binaries-\d{2}\.zip", name) or name == "binaries.zip")


def delete_assetout_archives(owner: str, repo: str, tag: str) -> int:
    assets = list_release_assets(owner, repo, tag)
    to_delete = [a for a in assets if is_assetout_archive(a)]
    deleted = 0

    for name in to_delete:
        result = run_process([
            "gh", "release", "delete-asset", tag, name,
            "-R", f"{owner}/{repo}",
            "--yes",
        ])

        if result.returncode == 0:
            console.print(f"  [dim]deleted[/dim] {name}")
            deleted += 1
        else:
            console.print(f"  [yellow]failed to delete[/yellow] {name}")

    return deleted
