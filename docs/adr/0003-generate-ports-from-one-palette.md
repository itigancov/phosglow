---
Status: accepted
---

# Generate every Port from one Palette, and commit the output

All Phosglow colours live in one `palette.toml` (a flat table of named colours, entries may reference each other). Each Port is a template under `templates/<port>/` with `{{name}}` placeholders instead of hex; a stdlib-only Python script, `tools/build.py`, renders them into `ports/<port>/`. `.itermcolors` (plist with float components) is built in code. The rendered files are committed, so users install without running anything. The Ghostty Shader is hand-written and sits in `ports/ghostty/` untouched by the generator. `ports/claude-code/` is a Claude Code plugin directory (`.claude-plugin/plugin.json`, `themes/phosglow.json`), so the marketplace file at the repo root can point at it.

## Considered Options

- **Upstream `Phosglow.yml` as the source**: it is what iTerm2-Color-Schemes wants, but it has no room for the extra tones Claude Code and herdr need (shimmer, diff backgrounds, sidebar), so those Ports would stay hand-written.
- **No generator, hand-written Ports plus a lint check**: no tooling, but each colour change touches four files by hand.
- **Node or shell generator**: Node needs a `package.json`; shell templating is brittle for JSON and plist.

## Consequences

- Hand-editing anything in `ports/` (except the Shader) is wrong; a freshness check (`build.py` then `git diff --exit-code`) should guard it.
- `Phosglow.yml` sent upstream is a build output, not a source.
- One `palette.toml` at the root; a second variant would mean moving to `palettes/`.
