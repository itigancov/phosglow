# Phosglow for Ghostty

A green phosphor CRT theme for [Ghostty](https://ghostty.org). Near-black
background, green text, and an optional shader that adds the monitor look:
a soft glow, scanlines, dark corners with a lit centre, an amber glow for
warnings and a softly pulsing cursor.

| File | What it is |
| --- | --- |
| `ports/ghostty/Phosglow` | The colours: background, foreground, cursor, selection and the 16-colour palette |
| `ports/ghostty/phosglow.glsl` | The CRT effects: glow, scanlines, vignette, centre lift, amber glow, cursor halo |
| `ports/claude-code/themes/phosglow.json` | A matching [Claude Code](https://claude.com/claude-code) theme (optional) |
| `ports/herdr/phosglow.toml` | Matching colours for [herdr](https://herdr.dev) (optional, added by hand) |
| `install.sh` | Copies the files into place and points your Ghostty config at them |

## Install

```sh
./install.sh
```

Then reload Ghostty's config (`Cmd+Shift+,` on macOS) or open a new window.

Options:

- `./install.sh --no-crt` installs the colours without the shader.
- `./install.sh --claude-code` also installs the Claude Code theme. To turn it
  on, set `"theme": "custom:phosglow"` in `~/.claude/settings.json`.

You can run the script again safely. It overwrites the theme files and adds
its config block only once.

### By hand

1. Copy `ports/ghostty/Phosglow` to `~/.config/ghostty/themes/Phosglow`.
2. Copy `ports/ghostty/phosglow.glsl` to `~/.config/ghostty/shaders/phosglow.glsl`.
3. Add these lines to `~/.config/ghostty/config.ghostty`:

   ```
   theme = Phosglow
   custom-shader = shaders/phosglow.glsl
   ```

## Optional: herdr

herdr draws its own colours, so it ignores the Ghostty theme. To match it, paste
`ports/herdr/phosglow.toml` under the `[theme]` section of
`~/.config/herdr/config.toml`. Then run `herdr server reload-config`.
The `install.sh` script does not do this for you.

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
  `ports/ghostty/phosglow.glsl`: `BLOOM_STRENGTH`, `SCAN_DEPTH`, `VIGNETTE`,
  `CENTER_LIFT`, `HOT_BOOST`, `CURSOR_PULSE`. `FLICKER` is off by default.
  Set `CURSOR_PULSE` to `0.0` for a steady cursor halo.
- **The cursor halo needs Ghostty 1.2 or newer.** It uses the cursor
  uniforms (shader inputs) that Ghostty provides.
- **Extra glow is for green only.** `HOT_BOOST` lights the brightest green
  pixels, such as the Claude Code mascot. White and grey text, for example
  in Neovim, gets the normal glow.
- **Retina screens.** `SCAN_PERIOD` is in physical pixels. Raise it if the
  scanlines look too fine.

## Uninstall

Delete the `# --- phosglow ---` block from your Ghostty config, then remove
`~/.config/ghostty/themes/Phosglow`, `~/.config/ghostty/shaders/phosglow.glsl`
and, if you installed it, `~/.claude/themes/phosglow.json`. For herdr, delete
the `[theme.custom]` section.
