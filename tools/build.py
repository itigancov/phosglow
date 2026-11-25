#!/usr/bin/env python3
"""Render every Phosglow Port from the Palette.

    python3 tools/build.py [ROOT]

ROOT (default: the repo root) holds `palette.toml` and `templates/<port>/`.
Output goes to `ROOT/ports/<port>/`. Standard library only (Python 3.11+, for
tomllib).
"""
import plistlib
import re
import sys
import tomllib
from pathlib import Path

PLACEHOLDER = re.compile(r"\{\{(.*?)\}\}")


class BuildError(Exception):
    pass


HEX = re.compile(r"#[0-9A-F]{6}")
ROLE_NAME = re.compile(r"[a-z][a-z0-9_]*")


def load_palette(path):
    """Read the Palette and resolve every reference to a #RRGGBB value."""
    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise BuildError(f"cannot read {path}: {e}") from e

    for name, value in raw.items():
        is_hex = isinstance(value, str) and HEX.fullmatch(value)
        is_ref = isinstance(value, str) and ROLE_NAME.fullmatch(value)
        if not (is_hex or is_ref):
            raise BuildError(
                f"palette: role '{name}' has {value!r}; "
                "expected #RRGGBB (uppercase) or the name of another role")
        if is_ref and value not in raw:
            raise BuildError(
                f"palette: role '{name}' references missing role '{value}'")

    def resolve(name, chain):
        if name in chain:
            cycle = " -> ".join(chain[chain.index(name):] + [name])
            raise BuildError(f"palette: reference cycle {cycle}")
        value = raw[name]
        return value if HEX.fullmatch(value) else resolve(value, chain + [name])

    return {name: resolve(name, []) for name in raw}


FILTERS = {"bare": lambda hex_: hex_.lstrip("#")}


def render(text, palette, source):
    def sub(match):
        name, *filters = [part.strip() for part in match.group(1).split("|")]
        if name not in palette:
            raise BuildError(f"{source}: unknown role '{name}' in {match.group(0)}")
        value = palette[name]
        for f in filters:
            if f not in FILTERS:
                raise BuildError(f"{source}: unknown filter '{f}' in {match.group(0)}")
            value = FILTERS[f](value)
        return value

    return PLACEHOLDER.sub(sub, text)


ITERM_KEYS = (
    [(f"Ansi {i} Color", role) for i, role in enumerate([
        "black", "red", "green", "yellow", "blue", "magenta", "cyan", "white",
        "bright_black", "bright_red", "bright_green", "bright_yellow",
        "bright_blue", "bright_magenta", "bright_cyan", "bright_white"])]
    + [("Background Color", "bg"), ("Foreground Color", "fg"),
       ("Cursor Color", "cursor"), ("Cursor Text Color", "cursor_text"),
       ("Selection Color", "selection_bg"), ("Selected Text Color", "selection_fg")]
)


def itermcolors(palette):
    """The iTerm2 colour preset: a plist with float colour components."""
    def colour(hex_):
        r, g, b = (int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5))
        return {"Alpha Component": 1.0, "Blue Component": b,
                "Color Space": "sRGB", "Green Component": g, "Red Component": r}

    missing = [role for _, role in ITERM_KEYS if role not in palette]
    if missing:
        raise BuildError(f"iterm2: palette lacks roles {', '.join(missing)}")
    plist = {key: colour(palette[role]) for key, role in ITERM_KEYS}
    return plistlib.dumps(plist, sort_keys=True)


def build(root):
    """Return {output path: bytes} for every Port under root."""
    root = Path(root)
    palette = load_palette(root / "palette.toml")
    outputs = {}
    templates = sorted((root / "templates").rglob("*.tmpl"))
    if not templates:
        raise BuildError(f"no *.tmpl files under {root / 'templates'}")
    for tmpl in templates:
        rel = tmpl.relative_to(root / "templates")
        try:
            source = tmpl.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            raise BuildError(f"cannot read templates/{rel}: {e}") from e
        text = render(source, palette, f"templates/{rel}")
        outputs[root / "ports" / rel.with_suffix("")] = text.encode("utf-8")
    if (root / "templates" / "iterm2").is_dir():
        outputs[root / "ports" / "iterm2" / "Phosglow.itermcolors"] = itermcolors(palette)
    return outputs


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    root = Path(argv[0]) if argv else Path(__file__).resolve().parent.parent
    try:
        outputs = build(root)
    except BuildError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    for path, data in sorted(outputs.items()):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
