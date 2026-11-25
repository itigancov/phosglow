---
Status: superseded by ADR-0002
---

# Name the theme "P31", not "Phosphor"

The theme is called **P31** everywhere (repo `p31`, `theme = P31` in Ghostty, `custom:p31` in Claude Code, catalogue listings). "Phosphor" alone is taken: Phosphor Icons is a large brand that also ships a "Phosphor Theme" for VS Code and Zed, and there are same-niche themes called Phosphor on Obsidian, VS Code and GitHub. "P31" is free in the registries we checked (GitHub themes, npm, VS Code Marketplace, Open VSX, iTerm2-Color-Schemes, Ghostty built-ins).

"Phosphor" is kept out of the name but stays in the subtitle, descriptions and topics ("a green phosphor CRT theme"), because themes are found by category, not by name.

## Considered Options

- **P31 Phosphor**: keeps the search word, but sits next to Phosphor Icons and the same-niche Phosphor themes in results, and is heavy.
- **Halation**: describes only the shader glow, not the theme as a whole.
- **Sprawl, Chiba, Geiger**: clean in the registries, but unrelated to the theme or its screen.
- **Matrix, Nostromo, Fallout/Pip-Boy names, WOPR**: already used by other themes, or franchise trademarks.

## Consequences

- A single name everywhere; no separate "keyword" repo or listing names.
- "P31" alone is hard to search, so every listing needs the subtitle and topics.
- The local rename from `ghostty-phosphor-theme` happens at execution time.
