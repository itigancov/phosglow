"""The herdr Plugin: its generated files and its two actions.

Build tests run tools/build.py on a fixture project. Action tests copy only
ports/herdr into a throwaway directory, read each action's command from the
manifest, run it from that folder with HOME and XDG_CONFIG_HOME in the sandbox
and a stub `herdr` first on PATH that records its arguments.
"""
import os
import shutil
import stat
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path

from test_build import Project, palette_toml

REPO = Path(__file__).resolve().parent.parent
START = "# >>> phosglow >>>"
END = "# <<< phosglow <<<"
MANIFEST = "ports/herdr/herdr-plugin.toml"


def setUpModule():
    if os.environ.get("PHOSGLOW_NESTED"):
        raise unittest.SkipTest("nested run")


class BuildOutput(unittest.TestCase):
    def project(self, version="1.0.0"):
        p = Project(self, palette_toml(bg="#050A05"),
                    {"herdr/phosglow.toml.tmpl": "[theme.custom]\nx = \"{{bg}}\"\n"})
        (p.root / "VERSION").write_text(version + "\n")
        (p.root / "tools").mkdir()
        (p.root / "tools" / "lib.sh").write_text("# helpers\nfoo() { :; }\n")
        r = p.build()
        self.assertEqual(r.returncode, 0, r.stderr)
        return p

    def manifest(self, p):
        return tomllib.loads((p.root / MANIFEST).read_text())

    def test_manifest_fields(self):
        m = self.manifest(self.project("2.13.7"))
        self.assertEqual(m["id"], "itigancov.phosglow")
        self.assertEqual(m["name"], "Phosglow")
        self.assertEqual(m["version"], "2.13.7")
        self.assertEqual(m["min_herdr_version"], "0.9.5")
        self.assertEqual(m["platforms"], ["macos", "linux"])
        self.assertTrue(m["description"])

    def test_two_global_actions_with_relative_commands(self):
        actions = self.manifest(self.project())["actions"]
        self.assertEqual(len(actions), 2)
        self.assertEqual({a["id"] for a in actions}, {"apply", "remove"})
        for a in actions:
            self.assertEqual(a["contexts"], ["global"])
            self.assertTrue(a["title"])
            self.assertTrue(a["command"][0].startswith("./"))

    def test_helper_copy_equals_the_shared_helpers(self):
        p = self.project()
        self.assertEqual((p.root / "ports/herdr/lib.sh").read_bytes(),
                         (p.root / "tools/lib.sh").read_bytes())

    def test_version_change_changes_the_manifest(self):
        p = self.project("1.0.0")
        before = (p.root / MANIFEST).read_bytes()
        (p.root / "VERSION").write_text("1.0.1\n")
        self.assertEqual(p.build().returncode, 0)
        self.assertNotEqual((p.root / MANIFEST).read_bytes(), before)

    def test_no_herdr_templates_no_plugin_files(self):
        p = Project(self, palette_toml(bg="#050A05"), {"a/t.tmpl": "x\n"})
        self.assertEqual(p.build().returncode, 0)
        self.assertFalse((p.root / "ports/herdr").exists())


class Actions(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.plugin = self.root / "plugin"
        shutil.copytree(REPO / "ports/herdr", self.plugin)
        self.home = self.root / "home"
        self.xdg = self.home / ".config"
        self.config = self.xdg / "herdr/config.toml"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.calls = self.root / "herdr-calls"
        self.stub(0)
        manifest = tomllib.loads((self.plugin / "herdr-plugin.toml").read_text())
        self.commands = {a["id"]: a["command"] for a in manifest["actions"]}
        self.colours = (REPO / "ports/herdr/phosglow.toml").read_text()
        self.table = self.colours[self.colours.index("[theme.custom]"):]
        self.block = f"\n{START}\n{self.table.rstrip()}\n{END}\n"

    def stub(self, code):
        stub = self.bin / "herdr"
        stub.write_text(f'#!/bin/sh\necho "$@" >> "{self.calls}"\nexit {code}\n')
        stub.chmod(0o755)

    def run_action(self, name, path=None, **extra):
        env = {"PATH": path or f"{self.bin}:{os.environ['PATH']}",
               "HOME": str(self.home), **extra}
        env.setdefault("XDG_CONFIG_HOME", str(self.xdg))
        return subprocess.run(self.commands[name], cwd=self.plugin, env=env,
                              capture_output=True, text=True)

    def write(self, text):
        self.config.parent.mkdir(parents=True, exist_ok=True)
        self.config.write_bytes(text.encode())

    def reloads(self):
        return self.calls.read_text().splitlines() if self.calls.exists() else []

    # --- apply / remove ---------------------------------------------------

    def test_commands_are_executable_files_in_the_plugin_folder(self):
        for command in self.commands.values():
            path = self.plugin / command[0]
            self.assertTrue(path.is_file(), command)
            self.assertTrue(path.stat().st_mode & stat.S_IXUSR, command)

    def test_apply_creates_a_missing_config_and_remove_deletes_it(self):
        r = self.run_action("apply")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.config.read_text(), self.block)
        r = self.run_action("remove")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(self.config.exists())

    def test_block_holds_only_the_colour_table(self):
        self.run_action("apply")
        text = self.config.read_text()
        self.assertNotIn("Paste", text)
        parsed = tomllib.loads(text)
        self.assertEqual(list(parsed), ["theme"])
        self.assertEqual(list(parsed["theme"]), ["custom"])
        self.assertEqual(parsed["theme"]["custom"], tomllib.loads(self.colours)["theme"]["custom"])

    def test_apply_keeps_the_user_theme_and_remove_restores_bytes(self):
        for original in ('[theme]\nname = "dracula"\nauto_switch = false\n',
                         '[theme]\nname = "dracula"',
                         '[theme]\nname = "dracula"\n\n',
                         ""):
            with self.subTest(original=original):
                self.write(original)
                self.assertEqual(self.run_action("apply").returncode, 0)
                text = self.config.read_text()
                self.assertTrue(text.startswith(original.rstrip("\n")))
                self.assertTrue(text.endswith(END + "\n"))
                self.assertEqual(tomllib.loads(text)["theme"].get("name"),
                                 "dracula" if original else None)
                self.assertEqual(self.run_action("remove").returncode, 0)
                if original:
                    self.assertEqual(self.config.read_bytes(), original.encode())
                else:
                    self.assertFalse(self.config.exists())

    def test_apply_twice_equals_apply_once(self):
        self.write('[theme]\nname = "dracula"\n')
        self.run_action("apply")
        once = self.config.read_bytes()
        self.run_action("apply")
        self.assertEqual(self.config.read_bytes(), once)

    def test_remove_without_a_block_is_a_noop(self):
        self.write('[theme]\nname = "dracula"\n')
        r = self.run_action("remove")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.config.read_text(), '[theme]\nname = "dracula"\n')
        self.assertEqual(self.reloads(), [])
        self.config.unlink()
        self.assertEqual(self.run_action("remove").returncode, 0)

    def test_xdg_config_home_is_used(self):
        other = self.root / "elsewhere"
        r = self.run_action("apply", XDG_CONFIG_HOME=str(other))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((other / "herdr/config.toml").exists())
        self.assertFalse(self.config.exists())

    def test_default_config_dir_is_home_dot_config(self):
        env = {"PATH": f"{self.bin}:{os.environ['PATH']}", "HOME": str(self.home)}
        r = subprocess.run(self.commands["apply"], cwd=self.plugin, env=env,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.config.exists())

    # --- conflicts --------------------------------------------------------

    def assert_refuses(self, text, line_no):
        self.write(text)
        r = self.run_action("apply")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.config.read_text(), text)
        self.assertIn(f"line {line_no}", r.stderr + r.stdout)
        self.assertIn("comment it out", r.stderr + r.stdout)
        self.assertEqual(self.reloads(), [])

    def test_refuses_an_active_custom_table(self):
        self.assert_refuses('[theme]\nname = "x"\n\n[theme.custom]\ntext = "#fff"\n', 4)

    def test_refuses_light_and_dark_subtables(self):
        self.assert_refuses('[theme]\nname = "x"\n[theme.custom.dark]\ntext = "#fff"\n', 3)
        self.assert_refuses('[theme]\n[theme.custom.light]\ntext = "#fff"\n', 2)

    def test_refuses_custom_keys_inside_the_theme_table(self):
        self.assert_refuses('[theme]\nname = "x"\ncustom.text = "#fff"\n', 3)
        self.assert_refuses('[theme]\nname = "x"\ncustom = { text = "#fff" }\n', 3)

    def test_refusal_message_shows_the_conflicting_line(self):
        self.write('[theme]\n[theme.custom]\n')
        r = self.run_action("apply")
        self.assertIn("[theme.custom]", r.stderr + r.stdout)

    def test_commented_conflicts_do_not_block(self):
        original = ('[theme]\nname = "x"\n# [theme.custom]\n# text = "#fff"\n'
                    '#custom.text = "#fff"\n  # [theme.custom.dark]\n')
        self.write(original)
        r = self.run_action("apply")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.config.read_text().startswith(original.rstrip("\n")))

    def test_custom_key_in_another_table_is_not_a_conflict(self):
        self.write('[theme]\nname = "x"\n\n[other]\ncustom = 1\n')
        self.assertEqual(self.run_action("apply").returncode, 0)

    def test_its_own_block_is_not_a_conflict(self):
        self.run_action("apply")
        r = self.run_action("apply")
        self.assertEqual(r.returncode, 0, r.stderr)

    # --- reload -----------------------------------------------------------

    def test_both_actions_reload_herdr(self):
        self.run_action("apply")
        self.assertEqual(self.reloads(), ["server reload-config"])
        self.run_action("remove")
        self.assertEqual(self.reloads(), ["server reload-config"] * 2)

    def test_failed_reload_prints_the_command_and_exits_zero(self):
        self.stub(1)
        for name in ("apply", "remove"):
            r = self.run_action(name)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("herdr server reload-config", r.stdout + r.stderr)

    def test_missing_herdr_prints_the_command_and_exits_zero(self):
        (self.bin / "herdr").unlink()
        shim = self.root / "nobin"
        shim.mkdir()
        for tool in ("bash", "env", "grep", "sed", "awk", "cat", "mkdir",
                     "dirname", "rm", "cp"):
            found = shutil.which(tool)
            if found:
                (shim / tool).symlink_to(found)
        r = self.run_action("apply", path=str(shim))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("herdr server reload-config", r.stdout + r.stderr)
        self.assertTrue(self.config.exists())


if __name__ == "__main__":
    unittest.main()
