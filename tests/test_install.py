"""Installers as a command-line black box.

Each test copies the installer (install.sh, tools/lib.sh, ports/) into a
throwaway directory, runs it under /bin/bash with HOME, XDG_CONFIG_HOME and
CLAUDE_CONFIG_DIR pointed into that directory, and checks files, output and
exit code.
"""
import os
import pty
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
START = "# >>> phosglow >>>"
END = "# <<< phosglow <<<"
BLOCK_CRT = f"\n{START}\ntheme = Phosglow\ncustom-shader = shaders/phosglow.glsl\n{END}\n"
BLOCK_NO_CRT = f"\n{START}\ntheme = Phosglow\n{END}\n"


def setUpModule():
    # tests/test_runner.py runs the runner on broken copies; these slow suites
    # test code the copies do not change, so the nested run leaves them out.
    if os.environ.get("PHOSGLOW_NESTED"):
        raise unittest.SkipTest("nested run")


class Sandbox(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.repo = self.root / "repo"
        self.home = self.root / "home"
        self.home.mkdir()
        self.repo.mkdir()
        shutil.copy(REPO / "install.sh", self.repo / "install.sh")
        shutil.copytree(REPO / "tools", self.repo / "tools",
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(REPO / "ports", self.repo / "ports")
        self.xdg = self.home / ".config"
        self.ghostty = self.xdg / "ghostty"

    def env(self, **extra):
        env = {"PATH": os.environ["PATH"], "HOME": str(self.home)}
        env.update(extra)
        return env

    def run_install(self, *args, stdin="", env=None, **extra):
        return subprocess.run(
            ["/bin/bash", str(self.repo / "install.sh"), *args],
            input=stdin, capture_output=True, text=True,
            env=env if env is not None else self.env(**extra), cwd=self.root)

    def run_with_tty(self, *args, answer=""):
        """Run with a pseudo-terminal as stdin, typing `answer`."""
        master, slave = pty.openpty()
        try:
            os.write(master, answer.encode())
            r = subprocess.run(
                ["/bin/bash", str(self.repo / "install.sh"), *args],
                stdin=slave, capture_output=True, text=True,
                env=self.env(), cwd=self.root, timeout=20)
        finally:
            os.close(master)
            os.close(slave)
        return r

    def snapshot(self):
        """Every file under the sandbox, with its bytes."""
        return {str(p.relative_to(self.root)): p.read_bytes()
                for p in sorted(self.root.rglob("*")) if p.is_file()}

    def config(self, name="config.ghostty"):
        return self.ghostty / name

    def write_config(self, text, name="config.ghostty"):
        self.ghostty.mkdir(parents=True, exist_ok=True)
        self.config(name).write_bytes(text.encode())


class GhosttyInstall(Sandbox):
    def test_install_copies_files_and_adds_one_block(self):
        r = self.run_install("ghostty")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.ghostty / "themes/Phosglow").read_bytes(),
                         (REPO / "ports/ghostty/Phosglow").read_bytes())
        self.assertEqual((self.ghostty / "shaders/phosglow.glsl").read_bytes(),
                         (REPO / "ports/ghostty/phosglow.glsl").read_bytes())
        self.assertEqual(self.config().read_text(), BLOCK_CRT)
        self.assertIn("Reload", r.stdout)

    def test_no_crt_installs_the_colours_without_the_shader(self):
        r = self.run_install("ghostty", "--no-crt")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.config().read_text(), BLOCK_NO_CRT)

    def test_install_twice_equals_install_once(self):
        self.run_install("ghostty")
        once = self.snapshot()
        self.run_install("ghostty")
        self.assertEqual(self.snapshot(), once)

    def test_rerun_with_other_no_crt_setting_swaps_the_block(self):
        self.run_install("ghostty")
        self.run_install("ghostty", "--no-crt")
        self.assertEqual(self.config().read_text(), BLOCK_NO_CRT)
        self.run_install("ghostty")
        self.assertEqual(self.config().read_text(), BLOCK_CRT)

    def test_existing_lines_are_untouched_and_block_comes_last(self):
        before = "font-size = 14\ntheme = Dracula\nbackground-opacity = 0.9\n"
        self.write_config(before)
        r = self.run_install("ghostty")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.config().read_text(), before + BLOCK_CRT)

    def test_existing_theme_line_is_reported_with_its_line_number(self):
        self.write_config("font-size = 14\ntheme = Dracula\n")
        r = self.run_install("ghostty")
        warnings = [l for l in (r.stdout + r.stderr).splitlines() if "Dracula" in l]
        self.assertEqual(len(warnings), 1, r.stdout + r.stderr)
        self.assertIn("line 2", warnings[0])
        self.assertIn("overrid", warnings[0])

    def test_no_warning_about_its_own_theme_line_on_rerun(self):
        self.run_install("ghostty")
        r = self.run_install("ghostty")
        self.assertNotIn("overrid", r.stdout + r.stderr)

    def test_older_config_named_config_is_used(self):
        self.write_config("font-size = 14\n", name="config")
        self.run_install("ghostty")
        self.assertEqual(self.config("config").read_text(), "font-size = 14\n" + BLOCK_CRT)
        self.assertFalse(self.config().exists())

    def test_config_ghostty_wins_over_config(self):
        self.write_config("a = 1\n", name="config")
        self.write_config("b = 2\n")
        self.run_install("ghostty")
        self.assertEqual(self.config("config").read_text(), "a = 1\n")
        self.assertEqual(self.config().read_text(), "b = 2\n" + BLOCK_CRT)

    def test_config_without_trailing_newline_keeps_its_last_line(self):
        self.write_config("font-size = 14")
        self.run_install("ghostty")
        text = self.config().read_text()
        self.assertTrue(text.startswith("font-size = 14\n"), text)
        self.assertEqual(text.count(START), 1)


class GhosttyUninstall(Sandbox):
    def assert_roundtrip(self, original, name="config.ghostty"):
        if original is not None:
            self.write_config(original, name=name)
        self.run_install("ghostty")
        r = self.run_install("--uninstall", "ghostty")
        self.assertEqual(r.returncode, 0, r.stderr)
        if original is None:
            self.assertFalse(self.config().exists())
        else:
            self.assertEqual(self.config(name).read_bytes(), original.encode())
        self.assertFalse((self.ghostty / "themes/Phosglow").exists())
        self.assertFalse((self.ghostty / "shaders/phosglow.glsl").exists())

    def test_restores_config_with_user_content(self):
        self.assert_roundtrip("font-size = 14\ntheme = Dracula\n")

    def test_restores_config_with_blank_line_at_the_end(self):
        self.assert_roundtrip("font-size = 14\n\n")

    def test_deletes_a_config_the_installer_created(self):
        self.assert_roundtrip(None)

    def test_restores_config_without_trailing_newline(self):
        self.assert_roundtrip("font-size = 14")

    def test_restores_older_config_name(self):
        self.assert_roundtrip("font-size = 14\n", name="config")

    def test_keeps_lines_the_user_added_after_the_block(self):
        self.write_config("a = 1\n")
        self.run_install("ghostty")
        with open(self.config(), "a") as f:
            f.write("b = 2\n")
        self.run_install("--uninstall", "ghostty")
        self.assertEqual(self.config().read_text(), "a = 1\nb = 2\n")

    def test_uninstall_without_install_is_harmless(self):
        before = self.snapshot()
        r = self.run_install("--uninstall", "ghostty")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_ghostty_dir_redirects_everything(self):
        target = self.root / "elsewhere"
        r = self.run_install("ghostty", "--ghostty-dir", str(target))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((target / "themes/Phosglow").is_file())
        self.assertEqual((target / "config.ghostty").read_text(), BLOCK_CRT)
        self.assertFalse(self.xdg.exists())

    def test_xdg_config_home_redirects_defaults(self):
        xdg = self.root / "xdg"
        r = self.run_install("ghostty", XDG_CONFIG_HOME=str(xdg))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((xdg / "ghostty/themes/Phosglow").is_file())
        self.assertFalse(self.xdg.exists())


PORTS = ["claude-code", "ghostty", "herdr", "iterm2"]


class DryRun(Sandbox):
    def test_dry_run_changes_nothing_for_every_port(self):
        self.write_config("font-size = 14\n")
        for action in ([], ["--uninstall"]):
            with self.subTest(action=action):
                before = self.snapshot()
                r = self.run_install("--dry-run", *action, *PORTS)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(self.snapshot(), before)

    def test_dry_run_after_install_changes_nothing_on_uninstall(self):
        self.run_install(*PORTS)
        before = self.snapshot()
        self.run_install("--dry-run", "--uninstall", *PORTS)
        self.assertEqual(self.snapshot(), before)

    def test_dry_run_lists_the_changes(self):
        r = self.run_install("--dry-run", "ghostty")
        self.assertIn("Phosglow", r.stdout)
        self.assertIn("theme = Phosglow", r.stdout)
        self.assertIn("config.ghostty", r.stdout)

    def test_dry_run_still_prints_instructions(self):
        r = self.run_install("--dry-run", "herdr", "iterm2")
        self.assertIn("[theme.custom]", r.stdout)
        self.assertIn("Phosglow.itermcolors", r.stdout)


class ClaudeCode(Sandbox):
    def test_install_copies_the_theme_and_prints_the_settings_line(self):
        r = self.run_install("claude-code")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.home / ".claude/themes/phosglow.json").read_bytes(),
                         (REPO / "ports/claude-code/themes/phosglow.json").read_bytes())
        self.assertIn('"theme": "custom:phosglow"', r.stdout)
        self.assertIn("/plugin marketplace add", r.stdout)
        self.assertIn("/plugin install", r.stdout)

    def test_settings_json_is_never_created_or_touched(self):
        self.run_install("claude-code")
        self.assertFalse((self.home / ".claude/settings.json").exists())
        (self.home / ".claude/settings.json").write_text('{"a": 1}\n')
        before = self.snapshot()
        self.run_install("claude-code")
        self.assertEqual(self.snapshot(), before)

    def test_claude_config_dir_is_used(self):
        target = self.root / "cc"
        self.run_install("claude-code", CLAUDE_CONFIG_DIR=str(target))
        self.assertTrue((target / "themes/phosglow.json").is_file())
        self.assertFalse((self.home / ".claude").exists())

    def test_claude_dir_flag_overrides_the_variable(self):
        flag, var = self.root / "flag", self.root / "var"
        self.run_install("claude-code", "--claude-dir", str(flag),
                         CLAUDE_CONFIG_DIR=str(var))
        self.assertTrue((flag / "themes/phosglow.json").is_file())
        self.assertFalse(var.exists())

    def test_uninstall_removes_the_copied_theme(self):
        before = self.snapshot()
        self.run_install("claude-code")
        r = self.run_install("--uninstall", "claude-code")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((self.home / ".claude/themes/phosglow.json").exists())


class PrintedPorts(Sandbox):
    def test_herdr_prints_the_snippet_and_writes_nothing(self):
        before = self.snapshot()
        r = self.run_install("herdr")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertIn((REPO / "ports/herdr/phosglow.toml").read_text().strip(), r.stdout)
        self.assertIn("config.toml", r.stdout)
        self.assertIn("herdr server reload-config", r.stdout)

    def test_herdr_leaves_an_existing_config_alone(self):
        cfg = self.xdg / "herdr/config.toml"
        cfg.parent.mkdir(parents=True)
        cfg.write_text("[theme]\nname = 'x'\n[theme.custom]\ntext = '#fff'\n")
        before = self.snapshot()
        self.run_install("herdr")
        self.assertEqual(self.snapshot(), before)

    def test_iterm2_prints_import_steps_and_writes_nothing(self):
        before = self.snapshot()
        r = self.run_install("iterm2")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertIn("Phosglow.itermcolors", r.stdout)
        self.assertIn("Import", r.stdout)

    def test_uninstall_prints_removal_text_and_writes_nothing(self):
        for port, word in (("herdr", "theme.custom"), ("iterm2", "Delete")):
            with self.subTest(port=port):
                before = self.snapshot()
                r = self.run_install("--uninstall", port)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(self.snapshot(), before)
                self.assertIn(word, r.stdout)


class Discovery(Sandbox):
    def test_list_shows_every_port_one_line_each(self):
        r = self.run_install("--list")
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.strip().splitlines()
        self.assertEqual([l.split(":")[0] for l in lines], PORTS)

    def test_port_scripts_answer_describe_and_options(self):
        for port in PORTS:
            with self.subTest(port=port):
                script = str(self.repo / "ports" / port / "install.sh")
                d = subprocess.run(["/bin/bash", script, "describe"], capture_output=True,
                                   text=True, env=self.env())
                self.assertEqual(len(d.stdout.strip().splitlines()), 1)
        o = subprocess.run(["/bin/bash", str(self.repo / "ports/ghostty/install.sh"), "options"],
                           capture_output=True, text=True, env=self.env())
        flags = [l.split("\t")[0].split()[0] for l in o.stdout.splitlines()]
        self.assertEqual(flags, ["--ghostty-dir", "--no-crt"])

    def test_help_documents_every_flag_of_every_port(self):
        r = self.run_install("--help")
        self.assertEqual(r.returncode, 0, r.stderr)
        for flag in ("--list", "--dry-run", "--uninstall", "--ghostty-dir",
                     "--no-crt", "--claude-dir"):
            self.assertIn(flag, r.stdout)

    def test_a_new_port_folder_needs_no_dispatcher_change(self):
        port = self.repo / "ports/dummy"
        port.mkdir()
        (port / "install.sh").write_text(
            "#!/usr/bin/env bash\n"
            'here="$(cd "$(dirname "$0")" && pwd)"\n'
            '. "$here/../../tools/lib.sh"\n'
            'case $1 in\n'
            '  describe) echo "dummy: a test Port" ;;\n'
            '  options) printf -- "--dummy-dir DIR\\tWhere\\n" ;;\n'
            '  install) shift; d=$HOME/dummy; while [ $# -gt 0 ]; do'
            ' [ "$1" = --dummy-dir ] && d=$2; shift; done;'
            ' copy_file "$here/install.sh" "$d/copy.sh" ;;\n'
            '  uninstall) remove_file "$HOME/dummy/copy.sh" ;;\n'
            "esac\n")
        r = self.run_install("--list")
        self.assertIn("dummy: a test Port", r.stdout)
        self.assertIn("--dummy-dir", self.run_install("--help").stdout)
        r = self.run_install("dummy")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.home / "dummy/copy.sh").is_file())
        before = self.snapshot()
        self.run_install("--dry-run", "--uninstall", "dummy")
        self.assertEqual(self.snapshot(), before)
        self.run_install("--uninstall", "dummy")
        self.assertFalse((self.home / "dummy/copy.sh").exists())


class Errors(Sandbox):
    def assert_fails_cleanly(self, code, *args, **kw):
        before = self.snapshot()
        r = self.run_install(*args, **kw)
        self.assertEqual(r.returncode, code, r.stdout + r.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertTrue(r.stderr.strip())
        return r

    def test_unknown_port_stops_before_any_action(self):
        self.assert_fails_cleanly(1, "ghostty", "nope")

    def test_mistyped_flag_stops_before_any_action(self):
        self.assert_fails_cleanly(1, "ghostty", "--no-crtt")

    def test_flag_accepted_by_no_selected_port_stops(self):
        self.assert_fails_cleanly(1, "ghostty", "--claude-dir", str(self.root / "x"))

    def test_flag_missing_its_value_stops(self):
        self.assert_fails_cleanly(1, "ghostty", "--ghostty-dir")

    def test_no_arguments_without_a_terminal_prints_usage_and_exits_2(self):
        r = self.assert_fails_cleanly(2)
        self.assertIn("Usage", r.stderr)

    def test_flags_only_without_a_terminal_is_a_usage_error(self):
        self.assert_fails_cleanly(2, "--no-crt")

    def test_equals_form_of_a_flag_works(self):
        target = self.root / "eq"
        r = self.run_install("ghostty", f"--ghostty-dir={target}")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((target / "themes/Phosglow").is_file())


class Menu(Sandbox):
    def test_numbers_install_only_those_ports(self):
        r = self.run_with_tty(answer="2\n")  # ghostty is #2
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.ghostty / "themes/Phosglow").is_file())
        self.assertFalse((self.home / ".claude").exists())

    def test_several_numbers(self):
        self.run_with_tty(answer="1 2\n")
        self.assertTrue((self.ghostty / "themes/Phosglow").is_file())
        self.assertTrue((self.home / ".claude/themes/phosglow.json").is_file())

    def test_a_selects_all(self):
        r = self.run_with_tty(answer="a\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.ghostty / "themes/Phosglow").is_file())
        self.assertTrue((self.home / ".claude/themes/phosglow.json").is_file())
        self.assertIn("[theme.custom]", r.stdout)

    def test_enter_alone_does_nothing(self):
        before = self.snapshot()
        r = self.run_with_tty(answer="\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_invalid_choice_is_an_error_and_changes_nothing(self):
        before = self.snapshot()
        r = self.run_with_tty(answer="9\n")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.snapshot(), before)

    def test_menu_applies_to_uninstall_too(self):
        self.run_install("ghostty", "claude-code")
        self.run_with_tty("--uninstall", answer="2\n")
        self.assertFalse((self.ghostty / "themes/Phosglow").exists())
        self.assertTrue((self.home / ".claude/themes/phosglow.json").is_file())

    def test_uninstall_without_port_and_terminal_applies_to_all(self):
        self.run_install("ghostty", "claude-code")
        r = self.run_install("--uninstall")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((self.ghostty / "themes/Phosglow").exists())
        self.assertFalse((self.home / ".claude/themes/phosglow.json").exists())


if __name__ == "__main__":
    unittest.main()
