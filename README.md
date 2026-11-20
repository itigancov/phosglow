# Phosphor for Ghostty

A green phosphor CRT theme for [Ghostty](https://ghostty.org). Near-black
background, green text, and an optional shader that adds the monitor look:
a soft glow, scanlines, dark corners and a faint flicker.

| File | What it is |
| --- | --- |
| `themes/phosphor` | The colours: background, foreground, cursor, selection and the 16-colour palette |
| `shaders/phosphor.glsl` | The CRT effects: glow, scanlines, vignette, flicker |
| `claude-code/phosphor.json` | A matching [Claude Code](https://claude.com/claude-code) theme (optional) |
| `install.sh` | Copies the files into place and points your Ghostty config at them |

## Install

```sh
./install.sh
```

Then reload Ghostty's config (`Cmd+Shift+,` on macOS) or open a new window.

Options:

- `./install.sh --no-crt` installs the colours without the shader.
- `./install.sh --claude-code` also installs the Claude Code theme. To turn it
  on, set `"theme": "custom:phosphor"` in `~/.claude/settings.json`.

You can run the script again safely. It overwrites the theme files and adds
its config block only once.

### By hand

1. Copy `themes/phosphor` to `~/.config/ghostty/themes/phosphor`.
2. Copy `shaders/phosphor.glsl` to `~/.config/ghostty/shaders/phosphor.glsl`.
3. Add these lines to `~/.config/ghostty/config.ghostty`:

   ```
   theme = phosphor
   custom-shader = shaders/phosphor.glsl
   ```

## Notes

- **Green only, except red and amber.** Errors and warnings keep a warm
  colour, so diffs and failed commands stay readable.
- **Dark only.** There is no light variant.
- **Shaders stack.** If you already have a `custom-shader`, both run. Remove
  the other one if the result looks muddy. The same applies to the Til Glow
  theme: install only one of them at a time.
- **If the effects don't show,** the shader probably failed to compile.
  Ghostty logs shader errors and doesn't report them as config errors.
- **To tune the look,** edit the constants at the top of
  `shaders/phosphor.glsl`: `BLOOM_STRENGTH`, `SCAN_DEPTH`, `VIGNETTE`,
  `FLICKER`. Set `FLICKER` to `0.0` if it bothers your eyes.
- **Retina screens.** `SCAN_PERIOD` is in physical pixels. Raise it if the
  scanlines look too fine.

## Uninstall

Delete the `# --- phosphor ---` block from your Ghostty config, then remove
`~/.config/ghostty/themes/phosphor`, `~/.config/ghostty/shaders/phosphor.glsl`
and, if you installed it, `~/.claude/themes/phosphor.json`.
