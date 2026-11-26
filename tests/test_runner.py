"""The test runner as a command-line black box.

Each test copies the repo into a throwaway directory, breaks one thing there,
points `tools/test.sh` at the copy through PHOSGLOW_ROOT and checks the exit
code and the PASS/FAIL/SKIP lines. Nothing here calls the checks directly.

The runner runs these tests too (it discovers every test). The nested run
sets PHOSGLOW_NESTED so that it skips them and does not recurse.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RUNNER = REPO / "tools" / "test.sh"


@unittest.skipIf(os.environ.get("PHOSGLOW_NESTED"), "nested run: no recursion")
class RunnerCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.copy = self.tmp / "repo"
        shutil.copytree(REPO, self.copy, ignore=shutil.ignore_patterns(
            ".git", "__pycache__"))

    # -- helpers -----------------------------------------------------------
    def run_runner(self, path=None):
        env = {"PATH": path or os.environ["PATH"],
               "HOME": str(self.tmp / "home"),
               "PHOSGLOW_ROOT": str(self.copy),
               "PHOSGLOW_NESTED": "1"}
        r = subprocess.run(["/bin/bash", str(RUNNER)], capture_output=True,
                           text=True, env=env, cwd=self.tmp, timeout=300)
        r.all = r.stdout + r.stderr
        return r

    def read(self, rel):
        return (self.copy / rel).read_text()

    def write(self, rel, text):
        path = self.copy / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def edit(self, rel, old, new):
        text = self.read(rel)
        self.assertIn(old, text, f"fixture drifted: {old!r} not in {rel}")
        self.write(rel, text.replace(old, new, 1))

    def snapshot(self):
        return {str(p.relative_to(self.copy)): p.read_bytes()
                for p in sorted(self.copy.rglob("*"))
                if p.is_file() and "__pycache__" not in p.parts}

    def assertFails(self, step, *messages):
        before = self.snapshot()
        r = self.run_runner()
        self.assertEqual(self.snapshot(), before, "the run changed the tree")
        self.assertEqual(r.returncode, 1, r.all)
        self.assertRegex(r.all, rf"(?m)^FAIL +{re.escape(step)}\b")
        for m in messages:
            self.assertIn(m, r.all)
        return r

    def assertGreen(self, r):
        self.assertEqual(r.returncode, 0, r.all)
        self.assertNotRegex(r.all, r"(?m)^FAIL ")


class Green(RunnerCase):
    def test_clean_copy_passes_every_step(self):
        r = self.run_runner()
        self.assertGreen(r)
        for step in ("freshness", "unit tests"):
            self.assertRegex(r.all, rf"(?m)^PASS +{step}\b")
        self.assertRegex(r.all, r"(?m)^(PASS|SKIP) +plugin validation\b")

    def test_run_leaves_the_tree_untouched(self):
        before = self.snapshot()
        self.run_runner()
        self.assertEqual(self.snapshot(), before)

    def test_nested_run_skips_the_runner_tests(self):
        r = self.run_runner()
        self.assertRegex(r.all, r"OK \(skipped=\d+\)")

    def test_old_python_fails_naming_the_required_version(self):
        shim = self.tmp / "shim"
        shim.mkdir()
        (shim / "python3").write_text(
            '#!/bin/sh\necho "Python 3.9.6"\n')
        (shim / "python3").chmod(0o755)
        r = self.run_runner(path=f"{shim}:{os.environ['PATH']}")
        self.assertEqual(r.returncode, 1, r.all)
        self.assertRegex(r.all, r"(?m)^FAIL +python\b")
        self.assertIn("3.11", r.all)


class Freshness(RunnerCase):
    def test_stale_port_names_the_file(self):
        self.edit("ports/herdr/phosglow.toml", "[theme.custom]",
                  "# hand edit\n[theme.custom]")
        self.assertFails("freshness", "ports/herdr/phosglow.toml")

    def test_extra_file_in_a_port_names_the_file(self):
        self.write("ports/herdr/leftover.toml", "x = 1\n")
        self.assertFails("freshness", "ports/herdr/leftover.toml")

    def test_missing_rendered_file_names_the_file(self):
        (self.copy / "assets" / "palette.svg").unlink()
        self.assertFails("freshness", "assets/palette.svg")

    def test_stale_manifest_after_a_version_bump(self):
        self.write("VERSION", "9.9.9\n")
        self.assertFails("freshness", ".claude-plugin/marketplace.json",
                         "ports/claude-code/.claude-plugin/plugin.json")

    def test_stale_herdr_manifest_names_the_file(self):
        self.edit("ports/herdr/herdr-plugin.toml", 'name = "Phosglow"',
                  'name = "Hand edit"')
        self.assertFails("freshness", "ports/herdr/herdr-plugin.toml")

    def test_stale_herdr_helper_copy_names_the_file(self):
        self.edit("ports/herdr/lib.sh", "_dry()", "# hand edit\n_dry()")
        self.assertFails("freshness", "ports/herdr/lib.sh")

    def test_helper_change_without_regenerating_fails(self):
        self.edit("tools/lib.sh", "_dry()", "# changed\n_dry()")
        self.assertFails("freshness", "ports/herdr/lib.sh")

    def test_palette_change_without_regenerating_fails(self):
        self.edit("palette.toml", 'surface_1           = "#10241A"',
                  'surface_1           = "#112233"')
        self.assertFails("freshness")

    def test_stale_readme_table_names_the_readme(self):
        self.edit("README.md", "`#050A05`", "`#050A06`")
        self.assertFails("freshness", "README.md")

    def test_readme_without_markers_fails_freshness(self):
        self.edit("README.md", "<!-- palette:end -->", "")
        self.assertFails("freshness", "README.md")

    def test_regenerated_uncommitted_change_passes(self):
        self.edit("palette.toml", 'surface_1           = "#10241A"',
                  'surface_1           = "#112233"')
        subprocess.run([sys.executable, str(self.copy / "tools" / "build.py"), str(self.copy)],
                       check=True)
        r = self.run_runner()
        self.assertRegex(r.all, r"(?m)^PASS +freshness\b")


class PaletteChecks(RunnerCase):
    def test_unused_role_is_named(self):
        self.write("palette.toml", self.read("palette.toml") + 'lonely = "#112233"\n')
        self.assertFails("unit tests", "lonely")

    def test_role_used_only_through_a_reference_is_used(self):
        # `deep` is used by no template; only the used role `bg` points at it.
        self.edit("palette.toml", 'bg           = "#050A05"', 'bg           = "deep"')
        self.write("palette.toml", self.read("palette.toml") + 'deep = "#050A05"\n')
        self.assertGreen(self.run_runner())

    def test_hex_in_a_template_names_file_and_line(self):
        self.write("templates/herdr/phosglow.toml.tmpl",
                   self.read("templates/herdr/phosglow.toml.tmpl") + "oops = \"#123456\"\n")
        n = len(self.read("templates/herdr/phosglow.toml.tmpl").splitlines())
        self.assertFails("unit tests", f"templates/herdr/phosglow.toml.tmpl:{n}")

    def test_hex_in_a_port_installer_names_file_and_line(self):
        self.write("ports/ghostty/install.sh",
                   self.read("ports/ghostty/install.sh") + "# tint #ABCDEF\n")
        n = len(self.read("ports/ghostty/install.sh").splitlines())
        self.assertFails("unit tests", f"ports/ghostty/install.sh:{n}")

    def test_hex_in_readme_prose_names_file_and_line(self):
        self.write("README.md", self.read("README.md") + "\nuse #123456\n")
        n = len(self.read("README.md").splitlines())
        self.assertFails("unit tests", f"README.md:{n}")

    def test_hex_in_contributing_names_file_and_line(self):
        self.write("CONTRIBUTING.md", self.read("CONTRIBUTING.md") + "\n#ABCDEF\n")
        n = len(self.read("CONTRIBUTING.md").splitlines())
        self.assertFails("unit tests", f"CONTRIBUTING.md:{n}")

    def test_hex_inside_the_generated_block_is_not_flagged(self):
        # The table is generated, so it is full of hex and the run stays green.
        self.assertIn("`#050A05`", self.read("README.md"))
        self.assertGreen(self.run_runner())

    def test_hex_in_a_rendered_port_is_not_flagged(self):
        r = self.run_runner()  # rendered Ports are full of hex
        self.assertNotIn("outside the Palette", r.all)

    def test_fg_below_aa_fails_and_mentions_the_readme(self):
        self.edit("palette.toml", 'fg           = "#29E050"', 'fg           = "#1A5A28"')
        self.assertFails("unit tests", "fg", "README")

    def test_fourteenth_ansi_above_threshold_fails(self):
        self.edit("palette.toml", 'blue           = "#1B7A52"', 'blue           = "#3FD6A0"')
        self.assertFails("unit tests", "13", "README")

    def test_different_below_set_fails(self):
        self.edit("palette.toml", 'blue           = "#1B7A52"', 'blue           = "#3FD6A0"')
        self.edit("palette.toml", 'red            = "#E8512F"', 'red            = "#6A1A0A"')
        self.assertFails("unit tests", "black, blue, bright_black", "red")

    def test_contrast_report_is_printed_on_every_run(self):
        r = self.run_runner()
        self.assertRegex(r.all, r"(?m)^ *bright_black +#44805A +\d+\.\d\d +below\b")
        self.assertRegex(r.all, r"(?m)^ *fg +#29E050 +\d+\.\d\d +PASS\b")


class PortChecks(RunnerCase):
    def test_broken_herdr_toml_fails(self):
        self.write("ports/herdr/phosglow.toml", "[theme.custom\nbroken\n")
        self.assertFails("unit tests", "herdr")

    def test_broken_claude_code_json_fails(self):
        self.write("ports/claude-code/themes/phosglow.json", "{ not json")
        self.assertFails("unit tests", "claude-code")

    def test_broken_plugin_manifest_fails(self):
        self.write("ports/claude-code/.claude-plugin/plugin.json", "{")
        self.assertFails("unit tests", "claude-code")

    def test_broken_itermcolors_fails(self):
        self.write("ports/iterm2/Phosglow.itermcolors", "<plist>")
        self.assertFails("unit tests", "iterm2")

    def test_broken_iterm2_yaml_fails(self):
        self.edit("ports/iterm2/Phosglow.yml", 'color_01: "#0A140A"', "color_01 oops")
        self.assertFails("unit tests", "iterm2")

    def test_ghostty_theme_missing_a_palette_index_fails(self):
        self.edit("ports/ghostty/Phosglow", "palette = 7=#9FE8A8\n", "")
        self.assertFails("unit tests", "ghostty", "7")

    def test_ghostty_theme_with_a_repeated_palette_index_fails(self):
        self.edit("ports/ghostty/Phosglow", "palette = 7=#9FE8A8\n",
                  "palette = 7=#9FE8A8\npalette = 7=#9FE8A8\n")
        self.assertFails("unit tests", "ghostty", "7")

    def test_ghostty_theme_with_an_extra_palette_index_fails(self):
        self.edit("ports/ghostty/Phosglow", "palette = 7=#9FE8A8\n",
                  "palette = 7=#9FE8A8\npalette = 99=#9FE8A8\n")
        self.assertFails("unit tests", "ghostty", "99")

    def test_new_port_without_a_checker_names_the_port(self):
        self.write("ports/newport/theme.txt", "x\n")
        self.assertFails("unit tests", "add a parse check for newport")


class Plugin(RunnerCase):
    def test_missing_claude_cli_skips_without_failing(self):
        bin_ = self.tmp / "bin"
        bin_.mkdir()
        (bin_ / "python3").symlink_to(Path(sys.executable).resolve())
        r = self.run_runner(path=f"{bin_}:/usr/bin:/bin")
        self.assertGreen(r)
        self.assertRegex(r.all, r"(?m)^SKIP +plugin validation\b")


if __name__ == "__main__":
    unittest.main()
