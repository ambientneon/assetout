# assetout/commands/cmd_init.py

from __future__ import annotations

from rich.console import Console

from assetout.utils.configs import (
    write_default_config,
    write_default_manifest,
)
from assetout.utils.paths import (
    find_repo_root,    
    get_manifest_path,
    get_config_path,
    get_data_path
)
from assetout.utils.helpers import (
    sync_gitignore_tracked
)


console = Console()

def run_init() -> None:
    """Точка входа команды init"""
    root = find_repo_root(after_init=False)
    config_path = get_config_path(root)
    manifest_path = get_manifest_path(root)
    data_path = get_data_path(root)

    if config_path.exists():
        console.print("[yellow]assetout already initialized here.[/yellow]")
        return
    
    data_path.mkdir(parents=True, exist_ok=True)
    write_default_config(config_path)
    write_default_manifest(manifest_path)
    sync_gitignore_tracked(root, {"version": 1, "files": {}})

    console.print(
        f"[green]✓[/green] Initialized in [bold]{root}[/bold]\n"
        f"  {config_path}\n"
        f"  {manifest_path}\n"
        f"  {data_path}\n"
    )
