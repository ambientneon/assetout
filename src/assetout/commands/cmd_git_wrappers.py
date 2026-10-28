# commands/cmd_git_wrappers.py

from __future__ import annotations

from rich.console import Console

from assetout.commands.cmd_add import run_add
from assetout.commands.cmd_push import run_push
from assetout.utils.helpers import run_process
from assetout.utils.paths import find_repo_root

console = Console()

def run_git_add(paths: list[str]) -> None:
    root = find_repo_root(after_init=True)

    # 1. binaries
    console.print("[bold]assetout add[/bold] ...")
    run_add(paths)

    # 2. code (git add)
    console.print("[bold]git add[/bold] ...")
    result = run_process(["git", "add", "--"] + paths, cwd=root)

    if result.returncode != 0:
        console.print(f"[red]Error:[/red] {result.stderr or 'git add failed'}")
        raise SystemExit(result.returncode)


def run_git_push(
    remote: str = "origin",
    branch: str | None = None,
    replace_all: bool = False,
    update_tag: bool = True,
) -> None:
    root = find_repo_root(after_init=True)

    # 1. code (git push)
    cmd = ["git", "push", remote]
    if branch:
        cmd.append(branch)

    console.print(f"[bold]git push[/bold] {' '.join(cmd[2:])} ...")
    result = run_process(cmd, cwd=root)

    if result.returncode != 0:
        console.print(f"[red]Error:[/red] {result.stderr or 'git push failed'}")
        raise SystemExit(result.returncode)

    # 2. binaries
    console.print("[bold]assetout push[/bold] ...")
    run_push(replace_all=replace_all, update_tag=update_tag)
