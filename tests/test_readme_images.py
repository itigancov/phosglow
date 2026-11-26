"""The README's screenshots are all there: no placeholder is left, and every
image it references under assets/ exists, is a PNG and fits the size budget.

Reads the repo from PHOSGLOW_ROOT (default: the repo this file lives in).
"""
import os
import re
import unittest
from pathlib import Path

ROOT = Path(os.environ.get("PHOSGLOW_ROOT")
            or Path(__file__).resolve().parent.parent)
README = ROOT / "README.md"
PLACEHOLDER = "TODO(07)"
IMAGE = re.compile(r"!\[[^\]]*\]\((assets/[^)\s]+\.png)\)")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
BUDGET_KB = 500  # per image
BUDGET = BUDGET_KB * 1024


def readme_lines():
    return README.read_text(encoding="utf-8").splitlines()


class ReadmeImages(unittest.TestCase):
    def test_no_screenshot_placeholder_is_left(self):
        left = [f"README.md:{i}: {line.strip()}"
                for i, line in enumerate(readme_lines(), 1) if PLACEHOLDER in line]
        self.assertEqual(left, [], f"screenshot placeholder ({PLACEHOLDER}) left:\n"
                         + "\n".join(left))

    def test_every_referenced_image_is_a_png_within_budget(self):
        problems = []
        for i, line in enumerate(readme_lines(), 1):
            for rel in IMAGE.findall(line):
                where = f"README.md:{i}: {rel}"
                path = ROOT / rel
                if not path.is_file():
                    problems.append(f"{where} is missing")
                    continue
                with open(path, "rb") as f:
                    if f.read(len(PNG_SIGNATURE)) != PNG_SIGNATURE:
                        problems.append(f"{where} is not a PNG")
                size = path.stat().st_size
                if size >= BUDGET:
                    problems.append(f"{where} is {size // 1024} KB, over the {BUDGET_KB} KB budget")
        self.assertEqual(problems, [], "README images:\n" + "\n".join(problems))


if __name__ == "__main__":
    unittest.main()
