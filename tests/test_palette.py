"""Checks on the Palette: no unused Roles, no colour defined outside it, and
the contrast promises of the README.

Reads the repo from PHOSGLOW_ROOT (default: the repo this file lives in).
"""
import os
import re
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(os.environ.get("PHOSGLOW_ROOT")
            or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "tools"))
import build  # noqa: E402

PALETTE = ROOT / "palette.toml"
AA = 4.5
README_NOTE = ("The README contrast claim must be updated along with this "
               "gate (a Palette decision for the maintainer).")

# Hand-written files, where no colour may be defined. Rendered Ports and other
# generated files are left out on purpose: they are full of hex.
HAND_WRITTEN = ("templates/**/*", "install.sh", "tools/lib.sh",
                "ports/*/install.sh", "ports/*/*.glsl")
HEX_COLOUR = re.compile(r"#[0-9A-Fa-f]{6}\b")
# "path:HEX" entries that may hold a hex colour, each with a reason. Empty:
# Shader tints are float vec3 values, not hex. Add here, with a reason, rather
# than widening HAND_WRITTEN's exclusions.
HEX_ALLOWED = []

# Of the 16 ANSI colours, these are below AA against bg and the README names
# them. Everything else reaches AA.
ANSI_BELOW_AA = {"black", "blue", "bright_black"}


def raw_palette():
    with open(PALETTE, "rb") as f:
        return tomllib.load(f)


def used_roles(raw):
    used = set()
    for tmpl in sorted((ROOT / "templates").rglob("*")):
        if tmpl.is_file():
            for m in build.PLACEHOLDER.finditer(tmpl.read_text(encoding="utf-8")):
                used.add(m.group(1).split("|")[0].strip())
    generator = (ROOT / "tools" / "build.py").read_text(encoding="utf-8")
    for name in raw:  # the iTerm2 preset and the palette image use Roles directly
        if re.search(rf"""["']{re.escape(name)}["']""", generator):
            used.add(name)
    pending = [n for n in used if n in raw]
    while pending:  # a used Role keeps the Role it references alive
        target = raw[pending.pop()]
        if target in raw and target not in used:
            used.add(target)
            pending.append(target)
    return used


class UnusedRoles(unittest.TestCase):
    def test_every_role_is_used(self):
        raw = raw_palette()
        used = used_roles(raw)
        unused = [n for n in raw if n not in used]
        self.assertEqual(
            unused, [],
            "unused Role(s): " + ", ".join(unused) + ". Use each in a template "
            "or the generator, or remove it from palette.toml.")


class NoHexOutsideThePalette(unittest.TestCase):
    def test_hand_written_files_hold_no_hex_colour(self):
        hits = []
        for pattern in HAND_WRITTEN:
            for path in sorted(ROOT.glob(pattern)):
                if not path.is_file():
                    continue
                rel = path.relative_to(ROOT).as_posix()
                text = path.read_text(encoding="utf-8", errors="replace")
                for n, line in enumerate(text.splitlines(), 1):
                    for m in HEX_COLOUR.finditer(line):
                        if f"{rel}:{m.group(0).upper()}" not in HEX_ALLOWED:
                            hits.append(f"{rel}:{n}: {m.group(0)}")
        self.assertEqual(
            hits, [],
            "hex colour outside the Palette (define a Role in palette.toml and "
            "use it via the template):\n  " + "\n  ".join(hits))


class Contrast(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.palette = build.load_palette(PALETTE)

    def ratio(self, fore, back):
        return build.contrast(self.palette[fore], self.palette[back])

    def test_report(self):
        rows = [("fg", "bg"), ("cursor", "bg"), ("selection_fg", "selection_bg")]
        rows += [(r, "bg") for r in build.ANSI_ROLES]
        print("\nContrast (WCAG 2; AA is 4.5:1)")
        print(f"  {'role':<15}{'hex':<9}{'ratio':>6}  {'':<6}on")
        for role, back in rows:
            ratio = self.ratio(role, back)
            verdict = "PASS" if ratio >= AA else "below"
            print(f"  {role:<15}{self.palette[role]:<9}{ratio:>6.2f}  "
                  f"{verdict:<6}{back}")

    def test_text_roles_reach_aa(self):
        for fore, back in [("fg", "bg"), ("cursor", "bg"),
                           ("selection_fg", "selection_bg")]:
            ratio = self.ratio(fore, back)
            self.assertGreaterEqual(
                ratio, AA,
                f"{fore} {self.palette[fore]} on {back} is {ratio:.2f}:1, "
                f"below {AA}:1. {README_NOTE}")

    def test_thirteen_of_sixteen_ansi_reach_aa(self):
        ok = [r for r in build.ANSI_ROLES if self.ratio(r, "bg") >= AA]
        self.assertEqual(
            len(ok), 13,
            f"{len(ok)} of 16 ANSI colours reach {AA}:1 against bg; the "
            f"README says 13. {README_NOTE}")

    def test_below_set_is_exactly_the_named_exceptions(self):
        below = {r for r in build.ANSI_ROLES if self.ratio(r, "bg") < AA}
        self.assertEqual(
            below, ANSI_BELOW_AA,
            "ANSI colours below AA are " + ", ".join(sorted(below)) +
            "; the README names " + ", ".join(sorted(ANSI_BELOW_AA)) +
            f". {README_NOTE}")


if __name__ == "__main__":
    unittest.main()
