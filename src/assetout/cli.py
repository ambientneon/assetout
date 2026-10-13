# assetout/cli.py

from pathlib import Path

import typer
from typing import Optional

from rich.console import Console

from assetout.constants             import SYNC_ALLOWED_POLICIES
from assetout.commands.cmd_init     import run_init
from assetout.commands.cmd_add      import run_add
from assetout.commands.cmd_status   import run_status
from assetout.commands.cmd_rm       import run_rm
from assetout.commands.cmd_push     import run_push
from assetout.commands.cmd_pull     import run_pull
from assetout.commands.cmd_sync     import run_sync
from assetout.commands.cmd_git_wrappers import (
    run_git_add, 
    run_git_push
)

app = typer.Typer(
    name="assetout",
    help="Keep large binary assets out of Git",
    no_args_is_help=True
)
console = Console()

@app.callback()
def main() -> None:
    """Keep large binary assets out of Git."""
    pass


@app.command()
def init() -> None:
    """Initialize assetout in the current repository."""
    run_init()


@app.command()
def add(
    paths: list[Path] = typer.Argument(
        ...,
        help="Files or directories to scan for large assets"
    ),
) -> None:
    """Add large file(s) to the mirror and manifest (not to Git)."""
    run_add([str(p) for p in paths])


@app.command()
def status() -> None:
    """Show status of tracked large files."""
    run_status()


@app.command()
def rm(
    paths: list[Path] = typer.Argument(..., help="Tracked files to remove"),
    project: bool = typer.Option(
        False,
        "--project",
        help="Also delete the file from the project working tree"
    ),
) -> None:
    """Remove file(s) from manifest and mirror (not from cloud until push)."""
    run_rm([str(p) for p in paths], delete_project=project)


@app.command()
def push(
    replace_all: bool = typer.Option(
        False,
        "--replace-all",
        "-ra",
        help="Delete all existing assetout archives from the release before uploading.",
    ),
) -> None:
    """Pack mirror into zip(s) and upload to GitHub Releases."""
    run_push(replace_all=replace_all)

    
@app.command()
def pull() -> None:
    """Download Release zip into .assetout/data/ (replace)."""
    run_pull()

    
@app.command()
def sync(
    policy: Optional[str] = typer.Option(
        None,
        "--policy",
        "-p",
        help=f"Sync direction. Allowed: {', '.join(SYNC_ALLOWED_POLICIES)}. Default: from config (sync_policy).",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite on hash mismatch (remote→project or local→data).",
    ),
) -> None:
    """Sync between .assetout/data/ and project files (manifest paths only)."""
    run_sync(policy=policy, force=force)


@app.command("git-add")
def git_add(
    paths: list[Path] = typer.Argument(..., help="Files/dirs to add"),
) -> None:
    """
    1. assetout add (переносит большие файлы в mirror)
    2. git add (остальное)
    """
    run_git_add([str(p) for p in paths])


@app.command("git-push")
def git_push(
    remote: str = typer.Argument("origin"),
    branch: Optional[str] = None,
    replace_all: bool = typer.Option(False, "--replace-all", "-ra"),
) -> None:
    """
    1. git push
    2. assetout push (binaries)
    """
    run_git_push(remote, branch, replace_all=replace_all)


if __name__ == "__main__":
    app()
