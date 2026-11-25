"""Black-box tests for tools/build.py: run the CLI on a fixture project."""
import plistlib
import subprocess
import sys
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
