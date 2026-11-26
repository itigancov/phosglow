#!/usr/bin/env python3
"""Check that the rendered Ports in the working tree match the Palette and templates.

    python3 tools/check_fresh.py

Reads the repo from PHOSGLOW_ROOT (default: the repo this file lives in).
Copies the generator inputs (palette.toml, VERSION, templates/) to a temp dir,
renders there, and compares with what the working tree holds. Never writes to
the working tree. Exit 1 if anything differs, is missing, or is left over.
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(os.environ.get("PHOSGLOW_ROOT")
            or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "tools"))  # the generator of the repo under test
import build  # noqa: E402

INPUTS = ("palette.toml", "VERSION", "templates")
# Hand-written files that live beside rendered ones, by name.
HAND_WRITTEN = {"install.sh", "phosglow.glsl"}


def rendered(root):
    """Every generated file as {path relative to root: bytes}."""
    return {p.relative_to(root): data for p, data in build.build(root).items()}


def main():
    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp)
        for name in INPUTS:
            src = ROOT / name
            if src.is_dir():
                shutil.copytree(src, scratch / name)
            elif src.exists():
                shutil.copy(src, scratch / name)
        try:
            expected = rendered(scratch)
        except build.BuildError as e:
            print(f"freshness: the generator fails: {e}")
            return 1

    problems = []
    for rel, data in sorted(expected.items()):
        path = ROOT / rel
        if not path.is_file():
            problems.append(f"missing: {rel} (run tools/build.py)")
        elif path.read_bytes() != data:
            problems.append(f"stale:   {rel} differs from the render (run tools/build.py)")
    for path in sorted((ROOT / "ports").rglob("*")):
        rel = path.relative_to(ROOT)
        if (path.is_file() and rel not in expected
                and path.name not in HAND_WRITTEN
                and "__pycache__" not in path.parts):
            problems.append(f"extra:   {rel} is neither generated nor hand-written")

    for p in problems:
        print(f"freshness: {p}")
    if problems:
        return 1
    print(f"freshness: {len(expected)} generated files up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
