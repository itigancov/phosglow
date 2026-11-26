#!/usr/bin/env python3
"""Render every Phosglow Port from the Palette.

    python3 tools/build.py [ROOT]

ROOT (default: the repo root) holds `palette.toml`, `VERSION` and
`templates/<port>/`. Output goes to `ROOT/ports/<port>/`, plus the Claude Code
plugin and marketplace manifests, the herdr Plugin manifest and helper copy,
and `ROOT/assets/palette.svg`. If `ROOT/README.md` exists, its Palette tables
(between the palette:start and palette:end markers) are regenerated in place;
the README is both an input and an output. Standard library only (Python 3.11+, for
tomllib).
"""
import json
import plistlib
import re
import sys
import tomllib
from pathlib import Path

# Published metadata. The identity is the GitHub handle only: no real name, no
# email. Names must not start with `claude-` or `anthropic-`.
NAME = "phosglow"
TITLE = "Phosglow"
HANDLE = "itigancov"
HOMEPAGE = f"https://github.com/{HANDLE}/{NAME}"
REPOSITORY = HOMEPAGE  # the same URL today; kept separate for the manifests
LICENSE = "MIT"
DESCRIPTION = ("Green phosphor CRT colour theme for terminals and AI coding "
               "tools, with an optional CRT shader for Ghostty.")
KEYWORDS = ["theme", "phosphor", "crt", "green", "terminal", "retro", "dark"]
PLUGIN_DIR = "claude-code"  # ports/<this> is the plugin directory
HERDR_DIR = "herdr"  # ports/<this> is the herdr Plugin folder
HERDR_MIN_VERSION = "0.9.5"  # the herdr version the Plugin was tested with

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


VERSION_RE = re.compile(r"\d+\.\d+\.\d+")


def read_version(root):
    try:
        version = (root / "VERSION").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as e:
        raise BuildError(f"cannot read VERSION: {e}") from e
    if not VERSION_RE.fullmatch(version):
        raise BuildError(f"VERSION: {version!r} is not X.Y.Z")
    return version


def manifests(root):
    """The plugin manifest and the marketplace listing, both from VERSION."""
    version = read_version(root)
    owner = {"name": HANDLE, "url": f"https://github.com/{HANDLE}"}
    plugin = {
        "name": NAME,
        "version": version,
        "description": DESCRIPTION,
        "author": owner,
        "homepage": HOMEPAGE,
        "repository": REPOSITORY,
        "license": LICENSE,
        "keywords": KEYWORDS,
        "experimental": {"themes": "./themes/"},
    }
    marketplace = {
        "name": NAME,
        "description": DESCRIPTION,
        "owner": owner,
        "plugins": [{
            "name": NAME,
            "source": f"./ports/{PLUGIN_DIR}",
            "version": version,
            "description": DESCRIPTION,
        }],
    }

    def dump(data):
        return (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")

    return {
        root / "ports" / PLUGIN_DIR / ".claude-plugin" / "plugin.json": dump(plugin),
        root / ".claude-plugin" / "marketplace.json": dump(marketplace),
    }


def herdr_plugin(root):
    """The herdr Plugin manifest and its copy of the shared installer helpers.

    The Plugin folder may be installed alone from GitHub, so it carries its
    own copy of tools/lib.sh instead of reaching outside itself."""
    version = read_version(root)
    try:
        helpers = (root / "tools" / "lib.sh").read_bytes()
    except OSError as e:
        raise BuildError(f"herdr: cannot read tools/lib.sh: {e}") from e
    actions = [
        ("apply", "Apply Phosglow", "./apply.sh"),
        ("remove", "Remove Phosglow", "./remove.sh"),
    ]
    lines = [
        f'id = "{HANDLE}.{NAME}"',
        f'name = "{TITLE}"',
        f'version = "{version}"',
        f'min_herdr_version = "{HERDR_MIN_VERSION}"',
        f"description = {json.dumps(DESCRIPTION)}",
        'platforms = ["macos", "linux"]',
    ]
    for action_id, title, command in actions:
        lines += ["", "[[actions]]", f'id = "{action_id}"', f'title = "{title}"',
                  'contexts = ["global"]', f'command = ["{command}"]']
    base = root / "ports" / HERDR_DIR
    return {
        base / "herdr-plugin.toml": ("\n".join(lines) + "\n").encode("utf-8"),
        base / "lib.sh": helpers,
    }


ANSI_ROLES = [
    "black", "red", "green", "yellow", "blue", "magenta", "cyan", "white",
    "bright_black", "bright_red", "bright_green", "bright_yellow",
    "bright_blue", "bright_magenta", "bright_cyan", "bright_white"]
IMAGE_ROLES = ANSI_ROLES + ["bg", "fg", "cursor", "selection_bg", "selection_fg"]


def luminance(hex_):
    """WCAG 2 relative luminance of #RRGGBB."""
    def linear(i):
        c = int(hex_[i:i + 2], 16) / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * linear(1) + 0.7152 * linear(3) + 0.0722 * linear(5)


def contrast(a, b):
    """WCAG 2 contrast ratio of two #RRGGBB colours (1 to 21)."""
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


TILE_W, TILE_H, GAP, MARGIN, HEADER, COLS = 168, 88, 12, 16, 40, 4


def palette_svg(palette):
    """An image of the Palette: each colour on the background with its exact
    contrast ratio against it (selection text against the selection background)."""
    missing = [r for r in IMAGE_ROLES if r not in palette]
    if missing:
        raise BuildError(f"image: palette lacks roles {', '.join(missing)}")
    bg, fg = palette["bg"], palette["fg"]
    # (id, name, swatch colour, sample text colour, reference for the ratio)
    tiles = [(r, r, palette[r], palette[r], bg) for r in ANSI_ROLES]
    tiles += [("bg", "bg", bg, fg, None),
              ("fg", "fg", fg, fg, bg),
              ("cursor", "cursor", palette["cursor"], palette["cursor"], bg),
              ("selection", f"text {palette['selection_fg']}", palette["selection_bg"],
               palette["selection_fg"], palette["selection_bg"])]
    rows = -(-len(tiles) // COLS)
    width = 2 * MARGIN + COLS * TILE_W + (COLS - 1) * GAP
    height = 2 * MARGIN + HEADER + rows * TILE_H + (rows - 1) * GAP
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="ui-monospace, Menlo, monospace">',
        f"<title>{TITLE} palette with WCAG contrast ratios against the background</title>",
        f'<rect width="{width}" height="{height}" fill="{bg}"/>',
        f'<text x="{MARGIN}" y="{MARGIN + 20}" font-size="16" font-weight="bold" '
        f'fill="{fg}">{TITLE}</text>',
        f'<text x="{MARGIN + 100}" y="{MARGIN + 20}" font-size="12" fill="{fg}">'
        "contrast ratio (WCAG 2) against the background</text>",
    ]
    for n, (tid, name, swatch, sample, ref) in enumerate(tiles):
        x = MARGIN + (n % COLS) * (TILE_W + GAP)
        y = MARGIN + HEADER + (n // COLS) * (TILE_H + GAP)
        field = palette["selection_bg"] if tid == "selection" else bg
        ratio = ""
        if ref is not None:
            ratio = (f'<text class="ratio" x="{TILE_W - 8}" y="{TILE_H - 8}" '
                     f'font-size="12" text-anchor="end" fill="{fg}">'
                     f"{contrast(sample, ref):.2f}:1</text>")
        out.append(
            f'<g id="tile-{tid}" transform="translate({x} {y})">'
            f'<rect width="{TILE_W}" height="{TILE_H}" rx="6" fill="{bg}" '
            f'stroke="{fg}" stroke-opacity="0.3"/>'
            f'<rect x="1" y="8" width="{TILE_W - 2}" height="32" fill="{field}"/>'
            f'<rect x="8" y="12" width="24" height="24" rx="3" fill="{swatch}" '
            f'stroke="{fg}" stroke-opacity="0.3"/>'
            f'<text x="44" y="33" font-size="18" font-weight="bold" fill="{sample}">Aa</text>'
            f'<text class="name" x="8" y="58" font-size="11" fill="{fg}">{name}</text>'
            f'<text class="hex" x="8" y="{TILE_H - 8}" font-size="12" fill="{fg}">{swatch}</text>'
            f"{ratio}</g>")
    out.append("</svg>")
    return ("\n".join(out) + "\n").encode("utf-8")


README_START, README_END = "<!-- palette:start -->", "<!-- palette:end -->"
BASE_ROLES = ["bg", "fg", "cursor", "selection_bg", "selection_fg"]


def palette_tables(palette):
    """The README's two tables: the base Roles, and the ANSI colours."""
    needed = BASE_ROLES + ANSI_ROLES
    missing = [r for r in needed if r not in palette]
    if missing:
        raise BuildError(f"README.md: palette lacks roles {', '.join(missing)}")
    rows = ["| Role | Hex |", "| --- | --- |"]
    rows += [f"| `{r}` | `{palette[r]}` |" for r in BASE_ROLES]
    rows += ["", "| Colour | Normal | Bright |", "| --- | --- | --- |"]
    rows += [f"| {n} | `{palette[n]}` | `{palette['bright_' + n]}` |"
             for n in ANSI_ROLES[:8]]
    return "\n".join(rows)


def render_readme(root, palette):
    """The README with its Palette block regenerated; everything outside the
    markers is kept byte for byte."""
    try:
        text = (root / "README.md").read_bytes().decode("utf-8")
    except UnicodeDecodeError as e:
        raise BuildError(f"cannot read README.md: {e}") from e
    if (text.count(README_START) != 1 or text.count(README_END) != 1
            or text.index(README_START) > text.index(README_END)):
        raise BuildError(
            f"README.md: expected exactly one {README_START} followed by one "
            f"{README_END}")
    head, rest = text.split(README_START)
    _, tail = rest.split(README_END)
    block = f"{README_START}\n{palette_tables(palette)}\n{README_END}"
    return (head + block + tail).encode("utf-8")


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
    if (root / "templates" / PLUGIN_DIR).is_dir():
        outputs.update(manifests(root))
    if (root / "templates" / HERDR_DIR).is_dir():
        outputs.update(herdr_plugin(root))
    if any(r in palette for r in ANSI_ROLES):
        outputs[root / "assets" / "palette.svg"] = palette_svg(palette)
    if (root / "README.md").is_file():
        outputs[root / "README.md"] = render_readme(root, palette)
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
