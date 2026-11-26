#!/usr/bin/env bash
# herdr Plugin action: remove Phosglow. Removes the marked block (and the blank
# line before it) from herdr's config, restoring it exactly, then reloads
# herdr. Does nothing when there is no block. Run this before uninstalling the
# Plugin: uninstalling does not undo the config change.
set -euo pipefail
unset PHOSGLOW_DRY_RUN

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
. "$here/lib.sh"

config="${XDG_CONFIG_HOME:-$HOME/.config}/herdr/config.toml"
reload_cmd="herdr server reload-config"

[ -f "$config" ] && grep -qxF "$PHOSGLOW_BLOCK_START" "$config" || exit 0
remove_block "$config"

if ! $reload_cmd >/dev/null 2>&1; then
  echo "Reload herdr's config yourself: $reload_cmd"
fi
