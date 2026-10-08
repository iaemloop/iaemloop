#!/usr/bin/env python3
"""Fail when the V2 branch changes any pre-existing V1 file."""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "f8940c9be285670639ff22ad83323d29ffb271c0"
ALLOWED_PREFIXES = ("v2/", "privado/v2/", "css/v2/", "js/v2/", "tests/v2/", "scripts/verify_v1_unchanged.py")

def run(*args: str) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True)

changed = [line.strip() for line in run("git", "diff", "--name-only", BASE, "--").splitlines() if line.strip()]
untracked = [line.strip() for line in run("git", "ls-files", "--others", "--exclude-standard").splitlines() if line.strip()]
changed = sorted(set(changed + untracked))
violations = [path for path in changed if not any(path == prefix or path.startswith(prefix) for prefix in ALLOWED_PREFIXES)]
if violations:
    print("V1_CHANGED")
    for path in violations:
        print(path)
    sys.exit(1)

manifest_path = ROOT / "tests/v2/v1-byte-manifest.sha256"
if manifest_path.exists():
    for line in manifest_path.read_text().splitlines():
        if not line.strip():
            continue
        expected, rel = line.split("  ", 1)
        path = ROOT / rel
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            print(f"V1_HASH_MISMATCH {rel}")
            sys.exit(1)

print(f"V1_UNCHANGED_OK files_changed={len(changed)}")
