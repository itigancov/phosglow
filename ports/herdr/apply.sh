#!/usr/bin/env bash
# herdr Plugin action: apply Phosglow. Appends the colour table from
# phosglow.toml to herdr's config as a marked block, refusing when the config
# already defines a custom theme, then reloads herdr. Self-contained: uses only
# files in this folder.
set -euo pipefail
unset PHOSGLOW_DRY_RUN

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
. "$here/lib.sh"

config="${XDG_CONFIG_HOME:-$HOME/.config}/herdr/config.toml"
reload_cmd="herdr server reload-config"

# Conflicts: uncommented lines, outside the Phosglow block, that define a
# custom theme: [theme.custom], [theme.custom.*], theme.custom... keys, or a
# `custom` key inside [theme].
if [ -f "$config" ]; then
  conflict=$(awk -v start="$PHOSGLOW_BLOCK_START" -v end="$PHOSGLOW_BLOCK_END" '
    $0 == start { inblock = 1; next }
    inblock { if ($0 == end) inblock = 0; next }
    /^[ \t]*#/ { next }
    /^[ \t]*\[/ {
      h = $0; sub(/[ \t]*#.*/, "", h); gsub(/[ \t]/, "", h)
      table = h
      if (h ~ /^\[theme\.custom(\.[^]]*)?\]/) { print NR ": " $0; exit }
      next
    }
    /^[ \t]*theme[ \t]*\.[ \t]*custom/ { print NR ": " $0; exit }
    table == "[theme]" && /^[ \t]*custom[ \t]*[.=]/ { print NR ": " $0; exit }
  ' "$config")
  if [ -n "$conflict" ]; then
    {
      echo "phosglow: $config already has a custom theme, not changing anything."
      echo "  line $conflict"
      echo "Delete or comment it out, then run Apply again."
    } >&2
    exit 1
  fi
fi

# Only the table: drop the file's leading comments (written for hand pasting).
table=$(sed -n '/^\[theme\.custom\]/,$p' "$here/phosglow.toml")
if [ -z "$table" ]; then
  echo "phosglow: no [theme.custom] table in $here/phosglow.toml; nothing applied." >&2
  exit 1
fi
add_block "$config" "$table"

if ! $reload_cmd >/dev/null 2>&1; then
  echo "Reload herdr's config yourself: $reload_cmd"
fi
