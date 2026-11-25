"""Black-box tests for tools/build.py: run the CLI on a fixture project."""
import json
import plistlib
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

BUILD = Path(__file__).resolve().parent.parent / "tools" / "build.py"

ANSI = [
    "black", "red", "green", "yellow", "blue", "magenta", "cyan", "white",
    "bright_black", "bright_red", "bright_green", "bright_yellow",
    "bright_blue", "bright_magenta", "bright_cyan", "bright_white",
]


def palette_toml(**roles):
    return "".join(f'{k} = "{v}"\n' for k, v in roles.items())


class Project:
    """A throwaway project directory with a palette and templates."""

    def __init__(self, test, palette, templates=None):
        tmp = tempfile.TemporaryDirectory()
        test.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "palette.toml").write_text(palette)
        for rel, text in (templates or {}).items():
            path = self.root / "templates" / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)

    def build(self):
        return subprocess.run(
            [sys.executable, str(BUILD), str(self.root)],
            capture_output=True, text=True,
        )

    def out(self, rel):
        return (self.root / "ports" / rel).read_text()

    def snapshot(self):
        return {
            str(p.relative_to(self.root)): p.read_bytes()
            for p in sorted(self.root.rglob("*")) if p.is_file()
        }


class RenderTest(unittest.TestCase):
    def test_renders_placeholders_into_ports_dir(self):
        p = Project(self, palette_toml(bg="#050A05", fg="#29E050"),
                    {"app/theme.tmpl": "# keep me\nbackground = {{bg}}\ntext={{ fg }}\n"})
        r = p.build()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(p.out("app/theme"),
                         "# keep me\nbackground = #050A05\ntext=#29E050\n")

    def test_reference_resolves_including_chains(self):
        p = Project(self, palette_toml(bg="#050A05", a="bg", b="a"),
                    {"app/t.tmpl": "{{b}} {{a}}\n"})
        self.assertEqual(p.build().returncode, 0)
        self.assertEqual(p.out("app/t"), "#050A05 #050A05\n")

    def test_bare_filter_strips_hash(self):
        p = Project(self, palette_toml(bg="#050A05"),
                    {"app/t.tmpl": "background = {{bg|bare}}\nx={{ bg | bare }}\n"})
        self.assertEqual(p.build().returncode, 0)
        self.assertEqual(p.out("app/t"), "background = 050A05\nx=050A05\n")


class FailureTest(unittest.TestCase):
    def assert_fails(self, project, *needles):
        r = project.build()
        self.assertNotEqual(r.returncode, 0)
        for needle in needles:
            self.assertIn(needle, r.stderr)
        self.assertFalse((project.root / "ports").exists(), "wrote output on failure")

    def test_unknown_placeholder_names_role_and_file(self):
        p = Project(self, palette_toml(bg="#050A05"),
                    {"app/theme.tmpl": "ok = {{bg}}\nbad = {{bgg}}\n"})
        self.assert_fails(p, "bgg", "app/theme.tmpl")

    def test_unknown_filter_fails(self):
        p = Project(self, palette_toml(bg="#050A05"),
                    {"app/theme.tmpl": "{{bg|shout}}\n"})
        self.assert_fails(p, "shout", "app/theme.tmpl")

    def test_malformed_hex_names_role(self):
        for bad in ("#12345", "#GGGGGG", "#abcdef", "050A05", "#050A0512"):
            with self.subTest(bad=bad):
                p = Project(self, palette_toml(bg="#050A05", fg=bad),
                            {"app/t.tmpl": "{{bg}}\n"})
                self.assert_fails(p, "fg")

    def test_malformed_hex_in_unused_role_still_fails(self):
        p = Project(self, palette_toml(bg="#050A05", unused="#XYZ"),
                    {"app/t.tmpl": "{{bg}}\n"})
        self.assert_fails(p, "unused")

    def test_non_string_value_fails(self):
        p = Project(self, "bg = 5\n", {"app/t.tmpl": "x\n"})
        self.assert_fails(p, "bg")

    def test_missing_reference_fails(self):
        p = Project(self, palette_toml(cursor="bright_green"),
                    {"app/t.tmpl": "{{cursor}}\n"})
        self.assert_fails(p, "cursor", "bright_green")

    def test_cycle_fails_showing_the_cycle(self):
        p = Project(self, palette_toml(a="b", b="c", c="a", bg="#050A05"),
                    {"app/t.tmpl": "{{bg}}\n"})
        self.assert_fails(p, "a -> b -> c -> a")

    def test_self_reference_is_a_cycle(self):
        p = Project(self, palette_toml(a="a"), {"app/t.tmpl": "x\n"})
        self.assert_fails(p, "a -> a")

    def test_missing_palette_file_fails_cleanly(self):
        p = Project(self, "", {"a/t.tmpl": "x\n"})
        (p.root / "palette.toml").unlink()
        r = p.build()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("palette.toml", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_invalid_toml_fails_cleanly(self):
        p = Project(self, "bg = = =\n", {"a/t.tmpl": "x\n"})
        r = p.build()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("palette.toml", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_no_templates_is_an_error(self):
        p = Project(self, palette_toml(bg="#050A05"), {})
        r = p.build()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("templates", r.stderr)

    def test_non_utf8_template_fails_cleanly(self):
        p = Project(self, palette_toml(bg="#050A05"), {})
        t = p.root / "templates" / "a" / "t.tmpl"
        t.parent.mkdir(parents=True)
        t.write_bytes(b"\xff\xfe{{bg}}\n")
        r = p.build()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("a/t.tmpl", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_failure_in_one_port_writes_nothing_for_any(self):
        p = Project(self, palette_toml(bg="#050A05"),
                    {"good/t.tmpl": "{{bg}}\n", "zbad/t.tmpl": "{{nope}}\n"})
        self.assert_fails(p, "nope")


class DeterminismTest(unittest.TestCase):
    def test_second_run_changes_nothing(self):
        p = Project(self, palette_toml(bg="#050A05"), {"a/t.tmpl": "{{bg}}\n"})
        p.build()
        first = p.snapshot()
        r = p.build()
        self.assertEqual(r.returncode, 0)
        self.assertEqual(p.snapshot(), first)

    def test_new_template_folder_is_picked_up(self):
        p = Project(self, palette_toml(bg="#050A05"), {"a/t.tmpl": "{{bg}}\n"})
        p.build()
        new = p.root / "templates" / "newport" / "deep" / "x.conf.tmpl"
        new.parent.mkdir(parents=True)
        new.write_text("bg={{bg}}\n")
        self.assertEqual(p.build().returncode, 0)
        self.assertEqual(p.out("newport/deep/x.conf"), "bg=#050A05\n")

    def test_output_has_lf_endings_even_from_crlf_templates(self):
        p = Project(self, palette_toml(bg="#050A05"), {})
        t = p.root / "templates" / "a" / "t.tmpl"
        t.parent.mkdir(parents=True)
        t.write_bytes(b"x={{bg}}\r\ny\r\n")
        p.build()
        self.assertEqual((p.root / "ports/a/t").read_bytes(), b"x=#050A05\ny\n")

    def test_files_that_are_not_templates_are_ignored(self):
        p = Project(self, palette_toml(bg="#050A05"),
                    {"a/t.tmpl": "{{bg}}\n", "a/README.md": "{{nope}}\n"})
        self.assertEqual(p.build().returncode, 0)
        self.assertFalse((p.root / "ports/a/README.md").exists())


def full_palette():
    colours = {name: f"#{i:02X}{i:02X}{i:02X}" for i, name in enumerate(ANSI)}
    colours.update(bg="#050A05", fg="#29E050", cursor="bright_green",
                   cursor_text="bg", selection_bg="#14401C", selection_fg="bright_white")
    return palette_toml(**colours)


class ItermColorsTest(unittest.TestCase):
    def build_plist(self, palette=None):
        p = Project(self, palette or full_palette(),
                    {"iterm2/Phosglow.yml.tmpl": "background: {{bg}}\n"})
        r = p.build()
        self.assertEqual(r.returncode, 0, r.stderr)
        return plistlib.loads((p.root / "ports/iterm2/Phosglow.itermcolors").read_bytes())

    def test_has_exactly_the_documented_keys(self):
        plist = self.build_plist()
        expected = {f"Ansi {i} Color" for i in range(16)} | {
            "Background Color", "Foreground Color", "Cursor Color",
            "Cursor Text Color", "Selection Color", "Selected Text Color"}
        self.assertEqual(set(plist), expected)

    def test_components_are_exact_floats(self):
        plist = self.build_plist()
        bg = plist["Background Color"]
        self.assertEqual(bg["Red Component"], 5 / 255)
        self.assertEqual(bg["Green Component"], 10 / 255)
        self.assertEqual(bg["Blue Component"], 5 / 255)
        self.assertEqual(bg["Alpha Component"], 1.0)
        self.assertEqual(bg["Color Space"], "sRGB")
        self.assertIsInstance(bg["Red Component"], float)

    def test_roles_map_to_keys_through_references(self):
        plist = self.build_plist()
        # ANSI n is #nnnnnn; cursor -> bright_green (10), selected text -> bright_white (15)
        self.assertEqual(plist["Ansi 3 Color"]["Red Component"], 3 / 255)
        self.assertEqual(plist["Cursor Color"]["Blue Component"], 10 / 255)
        self.assertEqual(plist["Selected Text Color"]["Green Component"], 15 / 255)
        self.assertEqual(plist["Cursor Text Color"]["Red Component"], 5 / 255)
        self.assertEqual(plist["Selection Color"]["Red Component"], 0x14 / 255)
        self.assertEqual(plist["Foreground Color"]["Blue Component"], 0x50 / 255)

    def test_missing_role_for_the_preset_fails_naming_it(self):
        p = Project(self, palette_toml(bg="#050A05"),
                    {"iterm2/Phosglow.yml.tmpl": "x\n"})
        r = p.build()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("black", r.stderr)

    def test_no_iterm2_port_means_no_preset(self):
        p = Project(self, palette_toml(bg="#050A05"), {"a/t.tmpl": "x\n"})
        self.assertEqual(p.build().returncode, 0)
        self.assertFalse((p.root / "ports/iterm2").exists())


PLUGIN = ".claude-plugin/plugin.json"
PLUGIN_PATH = "ports/claude-code/" + PLUGIN
MARKETPLACE_PATH = ".claude-plugin/marketplace.json"


class ManifestTest(unittest.TestCase):
    def project(self, version="1.0.0", with_port=True):
        templates = {"claude-code/themes/phosglow.json.tmpl": "{{bg}}\n"} if with_port else {"a/t.tmpl": "x\n"}
        p = Project(self, palette_toml(bg="#050A05"), templates)
        if version is not None:
            (p.root / "VERSION").write_text(version + "\n")
        return p

    def load(self, p, rel):
        return json.loads((p.root / rel).read_text())

    def build_ok(self, p):
        r = p.build()
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_both_manifests_carry_the_version_exactly(self):
        p = self.project("2.13.7")
        self.build_ok(p)
        self.assertEqual(self.load(p, PLUGIN_PATH)["version"], "2.13.7")
        entry, = self.load(p, MARKETPLACE_PATH)["plugins"]
        self.assertEqual(entry["version"], "2.13.7")

    def test_changing_version_changes_only_the_two_manifests(self):
        p = self.project("1.0.0")
        self.build_ok(p)
        before = p.snapshot()
        (p.root / "VERSION").write_text("1.0.1\n")
        self.build_ok(p)
        after = p.snapshot()
        changed = {k for k in before.keys() | after.keys() if before.get(k) != after.get(k)}
        self.assertEqual(changed, {"VERSION", PLUGIN_PATH, MARKETPLACE_PATH})

    def test_marketplace_points_at_the_plugin_directory(self):
        p = self.project()
        self.build_ok(p)
        m = self.load(p, MARKETPLACE_PATH)
        entry, = m["plugins"]
        self.assertEqual(entry["source"], "./ports/claude-code")
        self.assertEqual(entry["name"], m["name"])
        self.assertTrue((p.root / "ports/claude-code/themes/phosglow.json").is_file())

    def test_plugin_declares_the_themes_directory(self):
        p = self.project()
        self.build_ok(p)
        self.assertEqual(self.load(p, PLUGIN_PATH)["experimental"], {"themes": "./themes/"})

    def test_names_avoid_reserved_prefixes(self):
        p = self.project()
        self.build_ok(p)
        for name in (self.load(p, PLUGIN_PATH)["name"], self.load(p, MARKETPLACE_PATH)["name"]):
            self.assertEqual(name, "phosglow")
            self.assertFalse(name.startswith(("claude-", "anthropic-")))

    def test_identity_is_the_github_handle_only(self):
        p = self.project()
        self.build_ok(p)
        for rel in (PLUGIN_PATH, MARKETPLACE_PATH):
            text = (p.root / rel).read_text()
            self.assertNotRegex(text, r"[\w.+-]+@[\w-]+\.[\w.]+", "email")
            self.assertIn("itigancov", text)
        self.assertEqual(self.load(p, PLUGIN_PATH)["author"]["name"], "itigancov")
        self.assertEqual(self.load(p, MARKETPLACE_PATH)["owner"]["name"], "itigancov")
        self.assertEqual(self.load(p, PLUGIN_PATH)["repository"],
                         "https://github.com/itigancov/phosglow")

    def test_manifests_have_descriptive_metadata(self):
        p = self.project()
        self.build_ok(p)
        plugin = self.load(p, PLUGIN_PATH)
        for key in ("description", "homepage", "repository", "license", "keywords"):
            self.assertTrue(plugin[key], key)
        self.assertEqual(plugin["license"], "MIT")
        m = self.load(p, MARKETPLACE_PATH)
        self.assertTrue(m["description"])
        self.assertTrue(m["owner"]["name"])

    def test_invalid_version_fails_cleanly(self):
        for bad in ("1.0", "v1.0.0", "1.0.0-rc1", "", "one"):
            with self.subTest(bad=bad):
                p = self.project(bad)
                r = p.build()
                self.assertNotEqual(r.returncode, 0)
                self.assertIn("VERSION", r.stderr)
                self.assertNotIn("Traceback", r.stderr)
                self.assertFalse((p.root / "ports").exists())

    def test_missing_version_fails_when_the_plugin_port_exists(self):
        p = self.project(None)
        r = p.build()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("VERSION", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_no_claude_code_port_means_no_manifests(self):
        p = self.project(None, with_port=False)
        self.build_ok(p)
        self.assertFalse((p.root / ".claude-plugin").exists())
        self.assertFalse((p.root / "ports/claude-code").exists())

    def test_second_run_changes_nothing(self):
        p = self.project()
        self.build_ok(p)
        first = p.snapshot()
        self.build_ok(p)
        self.assertEqual(p.snapshot(), first)


SVG_PATH = "assets/palette.svg"
SVG = "{http://www.w3.org/2000/svg}"


class PaletteImageTest(unittest.TestCase):
    def build_svg(self, palette):
        p = Project(self, palette, {"a/t.tmpl": "x\n"})
        r = p.build()
        self.assertEqual(r.returncode, 0, r.stderr)
        return p

    def tiles(self, p):
        root = ET.parse(p.root / SVG_PATH).getroot()
        out = {}
        for g in root.iter(SVG + "g"):
            if g.get("id", "").startswith("tile-"):
                texts = {t.get("class"): t.text for t in g.iter(SVG + "text")}
                out[g.get("id")[5:]] = texts
        return out

    def palette(self, **overrides):
        colours = {name: f"#{i:02X}{i:02X}{i:02X}" for i, name in enumerate(ANSI)}
        colours.update(bg="#050A05", fg="#29E050", cursor="bright_green",
                       cursor_text="bg", selection_bg="#14401C", selection_fg="bright_white")
        colours.update(overrides)
        return palette_toml(**colours)

    def test_black_on_white_is_exactly_21(self):
        p = self.build_svg(self.palette(bg="#FFFFFF", black="#000000"))
        self.assertEqual(self.tiles(p)["black"]["ratio"], "21.00:1")

    def test_known_ratio_against_background(self):
        # #777777 on white is the textbook 4.48:1.
        p = self.build_svg(self.palette(bg="#FFFFFF", fg="#777777"))
        self.assertEqual(self.tiles(p)["fg"]["ratio"], "4.48:1")

    def test_one_tile_per_colour_with_its_hex(self):
        p = self.build_svg(self.palette())
        tiles = self.tiles(p)
        self.assertEqual(set(tiles), set(ANSI) | {"bg", "fg", "cursor", "selection"})
        self.assertEqual(tiles["red"]["hex"], "#010101")
        self.assertEqual(tiles["bg"]["hex"], "#050A05")
        self.assertEqual(tiles["cursor"]["hex"], "#0A0A0A")  # via reference bright_green
        self.assertEqual(tiles["selection"]["hex"], "#14401C")

    def test_selection_text_is_measured_against_the_selection_background(self):
        # On the selection background (black) #777777 is 4.69:1; on bg (white) 4.48:1.
        p = self.build_svg(self.palette(bg="#FFFFFF", selection_bg="#000000",
                                        selection_fg="#777777"))
        self.assertEqual(self.tiles(p)["selection"]["ratio"], "4.69:1")

    def test_selection_tile_also_shows_the_text_hex(self):
        p = self.build_svg(self.palette())
        self.assertIn("#0F0F0F", self.tiles(p)["selection"]["name"])  # via bright_white

    def test_background_tile_has_no_ratio(self):
        p = self.build_svg(self.palette())
        self.assertNotIn("ratio", self.tiles(p)["bg"])

    def test_output_is_valid_svg_with_an_accessible_title(self):
        p = self.build_svg(self.palette())
        root = ET.parse(p.root / SVG_PATH).getroot()
        self.assertEqual(root.tag, SVG + "svg")
        self.assertTrue(root.find(SVG + "title").text)

    def test_second_run_changes_nothing(self):
        p = self.build_svg(self.palette())
        first = p.snapshot()
        self.assertEqual(p.build().returncode, 0)
        self.assertEqual(p.snapshot(), first)

    def test_palette_without_ansi_roles_makes_no_image(self):
        p = Project(self, palette_toml(bg="#050A05"), {"a/t.tmpl": "x\n"})
        self.assertEqual(p.build().returncode, 0)
        self.assertFalse((p.root / "assets").exists())

    def test_partial_palette_fails_naming_the_missing_role(self):
        pal = palette_toml(bg="#050A05", fg="#29E050", black="#000000")
        p = Project(self, pal, {"a/t.tmpl": "x\n"})
        r = p.build()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("red", r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertFalse((p.root / "ports").exists())


if __name__ == "__main__":
    unittest.main()
