# assetout

**Keep large binary assets out of Git.**  
Store them in a local mirror (`.assetout/`) and sync with [GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github).

A simple alternative to Git LFS when you only need to keep big files out of the repository history and distribute them via Releases.

## Features

- Track large files outside Git (manifest + hashes)
- Local mirror in `.assetout/data/`
- Pack into zip archives and upload to GitHub Releases
- Automatic split into multiple archives when over the size limit
- Optional grouping by top-level project folder
- Sync between project files and the mirror (`remote` / `local` / `manual`)
- Automatic update of the release tag so Source code archives stay current
- Wrappers: `git-add`, `git-push`

## Requirements

- Python 3.11+
- Git repository with `origin` on GitHub
- [GitHub CLI (`gh`)](https://cli.github.com/) — authenticated (`gh auth login`)

## Install

```bash
pip install assetout
```

If the `assetout` command is not found (common on Windows):

```bash
# option A — recommended for CLI tools
pipx install assetout

# option B — module form (after adding __main__.py)
python -m assetout --help

# option C — add Python Scripts folder to PATH, then:
assetout --help
```

## Quick start

```bash
# inside your git repo
assetout init

# register large files (copy into .assetout/data/, update manifest & .gitignore)
assetout add path/to/big/files_or_dirs

assetout status

# upload archives to GitHub Releases
assetout push

# on another machine / clean checkout
assetout pull
assetout sync          # mirror → project files
```

## Commands

| Command | Description |
|---------|-------------|
| `init` | Create `.assetout/` (config, manifest, data dir) |
| `add` | Add large files to the mirror |
| `rm` | Remove from manifest and mirror |
| `status`   | Show tracked files + release tag status relative to HEAD           |
| `push`     | Pack mirror and upload to GitHub Releases (updates tag by default) |
| `pull` | Download release archives into `.assetout/data/` |
| `sync` | Sync between `.assetout/data/` and project files |
| `git-add` | `assetout add` then `git add` |
| `git-push` | `git push` then `assetout push` |

### Useful flags

```bash
# push
assetout push --replace-all          # delete old assetout archives, then upload
assetout push --update-tag           # move tag to HEAD (default)
assetout push --no-update-tag        # delete + recreate release instead of moving tag

# sync / rm
assetout sync --policy local --force
assetout rm path/to/file --project   # also delete from working tree
```

## How it works

```text
project files  ←→  .assetout/data/  ←→  GitHub Release (zip archives)
     ↑ sync              ↑ push / pull
```

- Files larger than `max_git_file_size` are kept out of Git
- Manifest stores size + hash for each path
- Archives are named `binaries-01.zip`, `project-binaries-01.zip`, …

## Configuration

Created by `assetout init` at `.assetout/config.yaml`:

```yaml
max_git_file_size: 10MB
hash_algorithm: xxh3
use_only_git_files: true
storage_backend: github_releases
sync_policy: remote          # remote | local | manual

packaging:
  group_by_top_level: false  # true → group by first folder name
  max_archive_size: 1900MB
  max_file_size: 2048MB

github:
  tag: assets-latest
  asset_name: binaries.zip   # legacy; names are generated automatically
  owner: ""                  # optional; taken from git remote if empty
  repo: ""
```

## Typical workflow

```bash
# day-to-day
assetout git-add .
git commit -m "Update assets"
assetout git-push                # = git push + assetout push (with tag update)

# or explicitly
assetout add assets/
assetout push --replace-all
```


### Updating the release tag

By default `assetout push` moves the configured tag (`assets-latest`) to the current `HEAD`  
and force-pushes it. This makes GitHub's automatic **Source code** archives contain the latest code.

```bash
assetout push                  # update tag (default)
assetout push --no-update-tag  # delete + recreate release instead
```

Use `--no-update-tag` if your team forbids force-pushing tags.

## License

MIT