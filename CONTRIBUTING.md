# Contributing

Phosglow is one Palette rendered into a Port per app. Review is best-effort.

## Requirements

- bash (3.2 is fine)
- Python 3.11+ (`tomllib`)
- optional: the `claude` CLI. Without it, plugin validation shows SKIP.

## Before a PR

```sh
python3 tools/build.py && tools/test.sh
git diff --exit-code
```

The build re-renders every generated file; `tools/test.sh` runs what CI runs.
Commit the rendered files. The working tree must be unchanged after the build.

## The Palette

`palette.toml` is the only place a colour is defined, and its values are the
maintainer's. A PR that changes a colour is closed with a pointer to this section.

- A Port needs a colour the Palette lacks? Map it to an existing Role first.
- Still missing? Add a new Role named by its purpose, not by the app
  (`diff_added_bg`, not `claude_diff`). It may reference another Role and never
  changes an existing value.
- No hex colour anywhere outside the Palette. The tests scan hand-written files,
  the README and this file for one.

## Adding a Port

A Port is done when all seven hold:

1. A template under `templates/<port>/` and its committed render under `ports/<port>/`.
2. `ports/<port>/install.sh` answers `describe`, `install`, `uninstall` and
   `options`, and works with `--dry-run` and `--uninstall`.
3. A README section (install, uninstall, "Verified with" the app version) and one PNG.
4. A CHANGELOG entry (a MINOR release).
5. No hex colour outside the Palette.
6. Any marketplace manifest sits inside the Port's own folder.
7. `tools/test.sh` covers the Port and CI is green.

Look at `ports/iterm2` for the smallest example.

## When an app changes

Ports are best-effort, and drift is reported by users only. Open an issue with
"broken since <app version>". A fix is a PATCH release. A Port left broken for
about 90 days with no PR is removed, which is a MAJOR release. This is a
guideline, not a promise.

A Port lives in this repo. A separate repo is never the default.
