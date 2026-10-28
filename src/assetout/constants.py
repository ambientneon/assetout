# assetout/constants.py

# Default sizes (in human-readable format)
DEFAULT_MAX_GIT_FILE_SIZE = "10MB"          # What do we consider "big" for Git?
DEFAULT_MAX_ARCHIVE_SIZE  = "1900MB"        # limit of one zip (~1.9 GB)
DEFAULT_MAX_FILE_SIZE     = "2048MB"        # single file limit (GitHub hard limit)

DEFAULT_HASH_ALGORITHM = "xxh3"
DEFAULT_CONFLICT_POLICY = "ask"
DEFAULT_STORAGE_BACKEND = "github_releases"
DEFAULT_GITHUB_TAG = "assets-latest"
DEFAULT_GITHUB_ASSET_NAME = "binaries.zip"

ASSETOUT_DIR_NAME = ".assetout"
CONFIG_FILE = "config.yaml"
MANIFEST_FILE = "manifest.json"
DATA_DIR_NAME = "data"

# folders that are never visited
SKIP_DIR_NAMES = {
    ASSETOUT_DIR_NAME,
    ".git",
    ".venv",
    "__pycache__",
    "node_modules"
}

SYNC_ALLOWED_POLICIES = ("remote", "local", "manual")
SYNC_UNRESOLVED_FILE = "unresolved.json"
