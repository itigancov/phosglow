"""Golden check: the generated Ports equal the pre-Palette hand-written files.

The old files live in commit 02a315c (before the Palette). After renaming
Phosphor -> Phosglow they must match the rendered Ports byte for byte.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OLD_COMMIT = "02a315c"
GOLDEN = {
    "themes/phosphor": "ports/ghostty/Phosglow",
    "claude-code/phosphor.json": "ports/claude-code/themes/phosglow.json",
    "herdr/phosphor.toml": "ports/herdr/phosglow.toml",
}


def old_file(path):
    r = subprocess.run(["git", "show", f"{OLD_COMMIT}:{path}"], cwd=REPO,
                       capture_output=True)
    if r.returncode != 0:
        raise unittest.SkipTest(f"commit {OLD_COMMIT} not available")
    return r.stdout


class GoldenTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls._tmp.name)
        for name in ("palette.toml", "VERSION", "templates", "ports/ghostty/phosglow.glsl"):
            src = REPO / name
            dst = cls.root / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                dst.write_bytes(src.read_bytes())
        r = subprocess.run([sys.executable, str(REPO / "tools/build.py"), str(cls.root)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(r.stderr)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_ports_match_old_files_after_the_rename(self):
        for old, new in GOLDEN.items():
            with self.subTest(port=new):
                expected = (old_file(old).decode()
                            .replace("Phosphor", "Phosglow")
                            .replace("phosphor", "phosglow"))
                self.assertEqual((self.root / new).read_text(), expected)

    def test_shader_is_untouched(self):
        self.assertEqual((REPO / "ports/ghostty/phosglow.glsl").read_bytes(),
                         old_file("shaders/phosphor.glsl"))


if __name__ == "__main__":
    unittest.main()
