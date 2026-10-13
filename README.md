# assetout

**Keep large binary assets out of Git.**  
Store them in a local mirror and sync with GitHub Releases.

Lightweight alternative to Git LFS when you just need to push big files to Releases.

## Features

- Track large files outside Git
- Local mirror in `.assetout/data/`
- Pack into zip archives and upload to GitHub Releases
- Split into multiple archives when over size limit
- Optional grouping by top-level project folder
- Sync between project files and mirror
- Simple CLI + optional `git-add` / `git-push` wrappers

## Requirements

- Python 3.10+
- [GitHub CLI (`gh`)](https://cli.github.com/) authenticated (`gh auth login`)
- Git repository with `origin` pointing to GitHub

## Install

```bash
pip install assetout
# or from source
pip install -e .
```

## Quick start

```bash
# in your git repo
assetout init

# add large files (copies to .assetout/data/, updates manifest + .gitignore)
assetout add path/to/big/files

# see status
assetout status

# upload to GitHub Releases
assetout push

# on another machine
assetout pull
assetout sync          # copy from mirror → project
```

## Commands

| Command | Description |
|---------|-------------|
| `init` | Create `.assetout/` config + manifest |
| `add` | Add large files to mirror |
| `rm` | Remove from mirror/manifest |
| `status` | Show tracked files state |
| `push` | Pack & upload to GitHub Releases |
| `pull` | Download archives into `.assetout/data/` |
| `sync` | Sync mirror ↔ project files |
| `git-add` | `assetout add` then `git add` |
| `git-push` | `git push` then `assetout push` |

### Useful flags

```bash
assetout push --replace-all    # delete old archives before upload
assetout sync --policy local --force
assetout rm path/to/file --project
```

## How it works

```
project files  ←→  .assetout/data/  ←→  GitHub Release (zip archives)
     ↑ sync              ↑ push/pull
```

- Files above `max_git_file_size` are kept out of Git
- Manifest tracks size + hash
- Archives are named `binaries-01.zip`, `project-binaries-01.zip`, …

## Config

`.assetout/config.yaml` (created by `init`):

```yaml
max_git_file_size: 10MB
packaging:
  group_by_top_level: false
  max_archive_size: 1900MB
  max_file_size: 2048MB
sync_policy: remote          # remote | local | manual
github:
  tag: assets-latest
```

## License

MIT

