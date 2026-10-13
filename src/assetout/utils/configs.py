# assetout/utils/configs.py

from __future__ import annotations

import json
import yaml

from typing import Any
from pathlib import Path
from rich.console import Console

from assetout.constants import (
    DEFAULT_MAX_GIT_FILE_SIZE,
    DEFAULT_MAX_ARCHIVE_SIZE,
    DEFAULT_MAX_FILE_SIZE,
    DEFAULT_HASH_ALGORITHM,
    DEFAULT_CONFLICT_POLICY,
    DEFAULT_STORAGE_BACKEND,
    DEFAULT_GITHUB_TAG,
    DEFAULT_GITHUB_ASSET_NAME
)
from assetout.utils.paths import (
    get_config_path,
    get_manifest_path
)


console = Console()

# public 
def get_hash_algorithm(root: Path) -> str:
    return load_config(root).get("hash_algorithm", DEFAULT_HASH_ALGORITHM)


def get_github_settings(config: dict[str, Any]) -> tuple[str, str]:
    gh = config.get("github") or {}
    tag = (gh.get("tag") or "assets-latest").strip()
    asset_name = (gh.get("asset_name") or "binaries.zip").strip()
    
    return tag, asset_name


def load_config(root: Path) -> dict[str, Any]:
    path = get_config_path(root)

    if not path.exists():
        console.print("[red]Error:[/red] config not found. Run 'assetout init' first")
        raise SystemExit(1)

    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_manifest(root: Path) -> dict[str, Any]:
    path = get_manifest_path(root)

    if not path.exists():
        return {
            "version": 1,
            "files": {}
        }

    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_default_config(path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(_get_default_config(), f, default_flow_style=False)


def write_default_manifest(path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"version": 1, "files": {}}, f, indent=2)
        f.write("\n")


def save_manifest(root: Path, manifest: dict[str, Any]) -> None:
    path = get_manifest_path(root)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")
    

# private
def _get_default_config() -> dict[str, Any]:
    return {
        "max_git_file_size": DEFAULT_MAX_GIT_FILE_SIZE,
        "hash_algorithm": DEFAULT_HASH_ALGORITHM,
        "conflict_policy": DEFAULT_CONFLICT_POLICY,
        "use_only_git_files": True,
        "storage_backend": DEFAULT_STORAGE_BACKEND,
        "sync_policy": "remote",
        "packaging": {
            "group_by_top_level": False,
            "max_archive_size": DEFAULT_MAX_ARCHIVE_SIZE,
            "max_file_size": DEFAULT_MAX_FILE_SIZE,
        },
        "github": {
            "tag": DEFAULT_GITHUB_TAG,
            "asset_name": DEFAULT_GITHUB_ASSET_NAME,
            "owner": "",
            "repo": "",
        },
    }