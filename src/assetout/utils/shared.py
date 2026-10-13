# # assetout/utils/shared.py

# from __future__ import annotations

# import os
# import re
# import xxhash
# import shutil
# import subprocess
# import tempfile

# from typing import Any
# from pathlib import Path
# from datetime import datetime, timezone
# from rich.console import Console

# from assetout.constants import (
#     DEFAULT_HASH_ALGORITHM,
#     BIG_DIR_NAME,
#     DATA_DIR_NAME
# )
# from assetout.utils.configs import (
#     load_manifest,
#     get_hash_algorithm
# )


# console = Console()

# # public
# def run_process(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
#     return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


# def make_manifest_entry(root: Path, path: Path) -> dict[str, Any]:
#     stat = path.stat()
    
#     return {
#         "size": stat.st_size,
#         "hash": file_hash(root, path),
#         "mtime": stat.st_mtime,
#         "added_at": datetime.now(timezone.utc).isoformat(),
#     }


# def file_hash(root: Path, path: Path) -> str:
#     algorithm = get_hash_algorithm(root)
#     hash_algo = (algorithm or DEFAULT_HASH_ALGORITHM).strip().lower()

#     if hash_algo in ("xxh3", "xxh3_128"):
#         h = xxhash.xxh3_128()
#     else:
#         console.print(f"[red]Error: unsupported hash_algorithm={algorithm!r}. Currently only 'xxh3' is supported.[/red]")
#         raise SystemExit(1)

#     with open(path, "rb") as f:
#         while chunk := f.read(1024 * 1024):
#             h.update(chunk)

#     return h.hexdigest()


# def get_owner_repo(root: Path, config: dict[str, Any]) -> tuple[str, str]:
#     gh = config.get("github") or {}
#     owner = (gh.get("owner") or "").strip()
#     repo = (gh.get("repo") or "").strip()
    
#     if owner and repo:
#         return owner, repo

#     git_remote_url = _get_git_remote_url(root).stdout.strip()
#     parsed = _parse_github_remote(git_remote_url)

#     if not parsed:
#         console.print(f"[red]Error: origin is not a GitHub URL: {git_remote_url}[/red]")
#         console.print("Set github.owner and github.repo in config.yaml")
#         raise SystemExit(1)
    
#     return parsed


# def safe_copy(src: Path, dest: Path) -> None:
#     """
#     Копирует файл атомарно:
#     1. пишет во временный файл в той же директории
#     2. os.replace (атомарно на большинстве FS)
#     """
#     dest.parent.mkdir(parents=True, exist_ok=True)

#     # временный файл в той же директории, чтобы rename был атомарным
#     fd, tmp_name = tempfile.mkstemp(
#         prefix=f".{dest.name}.",
#         suffix=".tmp",
#         dir=dest.parent,
#     )
#     tmp_path = Path(tmp_name)

#     try:
#         with os.fdopen(fd, "wb") as tmp_f, open(src, "rb") as src_f:
#             shutil.copyfileobj(src_f, tmp_f, length=1024 * 1024)

#         # сохраняем mtime/atime
#         shutil.copystat(src, tmp_path)
#         os.replace(tmp_path, dest)          # атомарно
#     except Exception:
#         tmp_path.unlink(missing_ok=True)
#         raise


# def sync_gitignore_tracked(root: Path, manifest: dict[str, Any] | None = None) -> None:
#     """
#     Перезаписывает блок путей assetout в .gitignore по манифесту.
#     Всё до BEGIN и после END не меняется.
#     """
#     begin_line = "# BEGIN assetout-tracked"
#     end_line = "# END assetout-tracked"

#     if manifest is None:
#         manifest = load_manifest(root)

#     gitignore_path = root / ".gitignore"
#     existing = ""
#     if gitignore_path.exists():
#         existing = gitignore_path.read_text(encoding="utf-8")

#     before, after = _split_gitignore(existing, begin_line, end_line)

#     tracked_paths = sorted(manifest.get("files", {}).keys())
#     block_lines = [begin_line]
#     # data/ — всегда
#     block_lines.append(f"{BIG_DIR_NAME}/{DATA_DIR_NAME}/")
#     block_lines.extend(tracked_paths)
#     block_lines.append(end_line)

#     parts: list[str] = []
#     if before.strip():
#         parts.append(before.rstrip("\n"))
    
#     parts.append("\n".join(block_lines))
    
#     if after.strip():
#         parts.append(after.lstrip("\n").rstrip("\n"))

#     text = "\n\n".join(parts) + "\n"
#     gitignore_path.write_text(text, encoding="utf-8")


# # private
# def _get_git_remote_url(root: Path) -> subprocess.CompletedProcess[str]:
#     result = run_process(["git", "remote", "get-url", "origin"], cwd=root)
#     if result.returncode != 0:
#         console.print("[red]Error: cannot get git remote 'origin'.[/red]")
#         console.print("Set github.owner and github.repo in config.yaml or add origin remote.")
#         raise SystemExit(result.returncode)

#     return result


# def _parse_github_remote(url: str) -> tuple[str, str] | None:
#     url = url.strip()

#     # git@github.com:owner/repo.git
#     # (SSH Host alias)
#     m = re.match(r"git@[^:]+:([^/]+)/(.+?)(?:\.git)?$", url)
#     if m:
#         return m.group(1), m.group(2)

#     # ssh://git@host/owner/repo.git
#     m = re.match(r"ssh://git@[^/]+/([^/]+)/(.+?)(?:\.git)?/?$", url)
#     if m:
#         return m.group(1), m.group(2)

#     # https://github.com/owner/repo.git
#     # https://www.github.com/owner/repo.git
#     m = re.match(r"https?://(?:www\.)?github\.com/([^/]+)/(.+?)(?:\.git)?/?$", url)
#     if m:
#         return m.group(1), m.group(2)

#     return None


# def _split_gitignore(content: str, begin_line: str, end_line: str) -> tuple[str, str]:
#     """
#     Делит .gitignore на (до блока, после блока).
#     Если маркеров нет — весь файл = before, after пустой.
#     Если есть только BEGIN или только END — всё равно вырезаем
#     от первого BEGIN до первого END (или до конца).
#     """
#     lines = content.splitlines(keepends=True)
#     begin_idx = None
#     end_idx = None

#     for i, line in enumerate(lines):
#         stripped = line.strip()
    
#         if stripped == begin_line and begin_idx is None:
#             begin_idx = i
    
#         if stripped == end_line:
#             end_idx = i

#     if begin_idx is None and end_idx is None:
#         return content, ""

#     if begin_idx is None:
#         # только END — считаем блок с начала файла
#         begin_idx = 0
    
#     if end_idx is None:
#         end_idx = len(lines) - 1

#     if end_idx < begin_idx:
#         end_idx = begin_idx

#     before = "".join(lines[:begin_idx])
#     after = "".join(lines[end_idx + 1 :])
#     return before, after
