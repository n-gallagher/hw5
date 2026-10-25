"""Reset the working database to the original before a full run.

    python -m backend.reset_db

Copies data/campus_customs.db (never modified) over data/campus_customs_new.db.
This also removes the payment_requests and board_drafts tables the MCP server
adds to the working copy. It is a file copy, not a shop tool: agents never call it.
"""

import hashlib
import shutil

from backend.config import PROJECT_DIR

ORIGINAL = PROJECT_DIR / "data" / "campus_customs.db"
WORKING = PROJECT_DIR / "data" / "campus_customs_new.db"


def sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reset() -> str:
    if not ORIGINAL.exists():
        raise FileNotFoundError(f"Original database missing: {ORIGINAL}")
    shutil.copyfile(ORIGINAL, WORKING)
    digest = sha256(WORKING)
    if digest != sha256(ORIGINAL):
        raise RuntimeError("Reset copy does not match the original.")
    return digest


if __name__ == "__main__":
    print(f"Reset {WORKING.name} from {ORIGINAL.name} (sha256 {reset()[:12]}...)")
