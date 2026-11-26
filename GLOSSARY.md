# Phosglow

A green phosphor CRT colour theme for terminals and AI coding tools, with an optional CRT shader for Ghostty.

## Language

**Phosglow**:
The name of the theme, written the same everywhere: repo, theme files, config values, catalogue listings. From "phosphor" + "glow": the green phosphor of classic monochrome CRT monitors and the glow of its screen.
_Avoid_: P31, PhosGlow, Phosphor, Phosphor theme, ghostty-phosphor-theme

**Palette**:
The set of named Phosglow colours. The only place a Phosglow colour is defined; every Port takes its colours from it.
_Avoid_: colour scheme, theme file

**Port**:
Phosglow as it appears in one application (Ghostty, iTerm2, Claude Code, herdr). One Palette, many Ports.
_Avoid_: target, flavour

**Plugin**:
A Port packaged for an application's own plugin system (Claude Code, herdr). Not every Port is a Plugin.
_Avoid_: extension, package

**Shader**:
The optional CRT effect (glow, scanlines) layered over the screen. Ghostty only; not part of the Palette or of any Port's colours.
_Avoid_: CRT theme

**Role**:
A named entry of the Palette, named by its purpose, not by the application that uses it (`diff_added_bg`, not `claude_diff`). A Role may reference another Role. Adding a Role never changes existing values.
_Avoid_: token, variable, slot
