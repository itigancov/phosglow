---
Status: accepted (supersedes ADR-0001)
---

# Rename the theme "Phosglow", not "P31"

The theme is called **Phosglow** everywhere (repo `phosglow`, `theme = Phosglow` in Ghostty, `custom:phosglow` in Claude Code, catalogue listings). "P31" turned out hard to read for anyone who doesn't know CRT phosphor codes, hard to search, and a same-niche npm package (`bootstra-p31`, a "P31 phosphor CRT" Bootstrap theme) appeared in October 2026. "Phosglow" had zero hits across every catalogue we may target (Ghostty/iTerm2, VS Code, Open VSX, Zed, Obsidian, JetBrains, Claude Code plugins, Neovim, kitty, Alacritty, Gogh, tinted-theming, Homebrew, Sublime, npm, PyPI, crates, GitHub) and on the web, reads as a brand, and keeps "phos" as a link to the "green phosphor CRT" subtitle.

## Considered Options

- **Glowtube, Tubeglow**: clean, but "tube" now reads as YouTube (their GitHub namesakes are video apps) and they describe rather than name.
- **Greenbeam**: clean but generic.
- **Monoglow, Rasterglow, Afterimage**: taken in the same niche (a Neovim colorscheme, a CRT terminal, a built-in iTerm2/Ghostty scheme).

## Consequences

- Spelled by ear it is ambiguous ("fosglow"); accepted, since themes are found by links and catalogues.
- Trademark registers were not checked; re-check before publishing.
