"""Every Port's files parse, and every Port has a parse check.

Reads the repo from PHOSGLOW_ROOT (default: the repo this file lives in).
Standard library only: TOML, JSON and plist are parsed; Ghostty and iTerm2 YAML
are checked line by line.
"""
import json
import os
import plistlib
import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(os.environ.get("PHOSGLOW_ROOT")
            or Path(__file__).resolve().parent.parent)
HEX = r"#[0-9A-Fa-f]{6}"


class Invalid(Exception):
    pass


def parse(path, loader):
    try:
        return loader(path)
    except FileNotFoundError:
        raise Invalid(f"{path.relative_to(ROOT)} is missing")
    except Exception as e:
        raise Invalid(f"{path.relative_to(ROOT)} does not parse: {e}")


def load_toml(path):
    with open(path, "rb") as f:
        return tomllib.load(f)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_plist(path):
    with open(path, "rb") as f:
        return plistlib.load(f)


def check_indexed_colours(path, line_re, index_of, indexes, what):
    """Each line is blank, a `#` comment or matches line_re; the colour indexes
    found (via index_of) are each of `indexes` exactly once, and no others."""
    seen = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = line_re.fullmatch(line.strip())
        if not m:
            raise Invalid(f"{path.relative_to(ROOT)}:{n}: not `{what}`: {line!r}")
        index = index_of(m)
        if index is not None:
            seen.append(index)
    for i in sorted(set(seen) | set(indexes)):
        if (i in indexes) != (seen.count(i) == 1):
            raise Invalid(f"{path.relative_to(ROOT)}: colour {i} appears "
                          f"{seen.count(i)} times, expected "
                          f"{'exactly once' if i in indexes else 'never'}")


def check_herdr(port):
    parse(port / "phosglow.toml", load_toml)
    parse(port / "herdr-plugin.toml", load_toml)


def check_claude_code(port):
    parse(port / "themes" / "phosglow.json", load_json)
    parse(port / ".claude-plugin" / "plugin.json", load_json)
    parse(ROOT / ".claude-plugin" / "marketplace.json", load_json)


def check_iterm2(port):
    plist = parse(port / "Phosglow.itermcolors", load_plist)
    if "Bold Color" not in plist:
        raise Invalid("ports/iterm2/Phosglow.itermcolors has no Bold Color")
    if not re.search(rf'^bold: "{HEX}"$',
                     (port / "Phosglow.yml").read_text(encoding="utf-8"), re.M):
        raise Invalid("ports/iterm2/Phosglow.yml has no bold field")
    check_indexed_colours(
        port / "Phosglow.yml",
        re.compile(rf'color_(\d\d): "{HEX}"|[a-z_]+: "(?:{HEX}|[^"]*)"'),
        lambda m: int(m.group(1)) - 1 if m.group(1) else None,
        range(16), 'key: "value"')


def check_ghostty(port):
    check_indexed_colours(
        port / "Phosglow",
        re.compile(rf"palette = (\d+)={HEX}|[a-z-]+ = [^=\s]+"),
        lambda m: int(m.group(1)) if m.group(1) else None,
        range(16), "key = value")


# Port folder name -> a check that parses that Port's files. Add yours here.
CHECKERS = {
    "claude-code": check_claude_code,
    "ghostty": check_ghostty,
    "herdr": check_herdr,
    "iterm2": check_iterm2,
}


def port_names():
    return sorted(p.name for p in (ROOT / "ports").iterdir() if p.is_dir())


class PortFiles(unittest.TestCase):
    def test_every_port_has_a_parse_check(self):
        missing = [p for p in port_names() if p not in CHECKERS]
        self.assertEqual(
            missing, [],
            "\n".join(f"add a parse check for {p} (CHECKERS in "
                      "tests/test_ports.py)" for p in missing))

    def test_every_port_parses(self):
        for name in port_names():
            if name not in CHECKERS:
                continue
            with self.subTest(port=name):
                try:
                    CHECKERS[name](ROOT / "ports" / name)
                except Invalid as e:
                    self.fail(f"{name}: {e}")


if __name__ == "__main__":
    unittest.main()
