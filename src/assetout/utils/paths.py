from __future__ import annotations

from typing import Any
from pathlib import Path
from rich.console import Console

from assetout.constants import (
    ASSETOUT_DIR_NAME,
    DATA_DIR_NAME,
    CONFIG_FILE,
    MANIFEST_FILE
)


console = Console()

def find_repo_root(after_init: bool) -> Path:
    """Ищем .git вверх. Если нет - текущая папка."""
    current = Path.cwd().resolve()

    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            if not after_init:
                return parent
            
            if (get_config_path(parent)).exists():
                return parent

    console.print("[red]Error: not in an assetout repository. Run 'assetout init' first.[/red]")
    raise SystemExit(1)


def get_config_path(root: Path) -> Path:
    return root / ASSETOUT_DIR_NAME / CONFIG_FILE


def get_manifest_path(root: Path) -> Path:
    return root / ASSETOUT_DIR_NAME / MANIFEST_FILE


def get_data_path(root: Path, rel: str | None = None) -> Path:
    if rel is not None:
        return root / ASSETOUT_DIR_NAME / DATA_DIR_NAME / rel
    else:
        return root / ASSETOUT_DIR_NAME / DATA_DIR_NAME


def get_project_path(root: Path, rel: str) -> Path:
    return root / rel


def get_rel_path(path: Path, root: Path) -> str | None:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def resolve_rel(raw: str, root: Path, manifest: dict[str, Any]) -> str | None:
    """Путь как в манифесте, либо существующий файл -> relative path."""
    # уже ключ манифеста
    if raw in manifest.get("files", {}):
        return raw

    # нормализация слэшей
    normalized = raw.replace("\\", "/")
    if normalized in manifest.get("files", {}):
        return normalized

    path = Path(raw)
    if path.is_absolute() or path.exists():
        rel = get_rel_path(path, root)

        if rel is not None:
            return rel

    # относительный путь от корня репо
    candidate = (root / raw).resolve()
    rel = get_rel_path(candidate, root)
    return rel
