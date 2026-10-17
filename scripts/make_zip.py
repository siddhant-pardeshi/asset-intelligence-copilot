"""Create a clean submission zip of the project (excludes .git, __pycache__, .db files)."""
import zipfile
import os
from pathlib import Path

ROOT = Path(r"c:\Users\siddh\Desktop\FlytHackathon2\asset-intelligence-copilot")
OUT  = Path(r"c:\Users\siddh\Desktop\FlytHackathon2\asset-intelligence-copilot-submission.zip")

EXCLUDE_DIRS  = {".git", "__pycache__", ".venv", "venv", "env", ".idea", ".vscode"}
EXCLUDE_EXTS  = {".db", ".db-wal", ".db-shm", ".pyc", ".pyo"}
EXCLUDE_FILES = {"_capture.html"}   # internal helper

count = 0
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    for fpath in ROOT.rglob("*"):
        if not fpath.is_file():
            continue
        # Skip excluded dirs anywhere in path
        parts = set(fpath.relative_to(ROOT).parts)
        if parts & EXCLUDE_DIRS:
            continue
        if fpath.suffix.lower() in EXCLUDE_EXTS:
            continue
        if fpath.name in EXCLUDE_FILES:
            continue
        arcname = fpath.relative_to(ROOT.parent)  # keep project folder name in zip
        zf.write(fpath, arcname)
        count += 1
        print(f"  + {arcname}")

size_mb = OUT.stat().st_size / 1_048_576
print(f"\nDone: {count} files -> {OUT.name} ({size_mb:.1f} MB)")
