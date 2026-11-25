#!/usr/bin/env bash
# herdr Port. Prints instructions; never edits the herdr config.
# Commands: describe | install | uninstall | options.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../tools/lib.sh
. "$here/../../tools/lib.sh"

cmd=${1:-}
config="${XDG_CONFIG_HOME:-$HOME/.config}/herdr/config.toml"

case $cmd in
  describe)
    echo "herdr: Phosglow colours for herdr (printed snippet, added by hand)"
    ;;
  options)
    ;;
  install)
    print_snippet "herdr: paste into $config" \
"Add this to $config (under the [theme] section), then run:

  herdr server reload-config

$(cat "$here/phosglow.toml")"
    ;;
  uninstall)
    print_snippet "herdr: remove by hand" \
"Delete the [theme.custom] section from $config, then run:

  herdr server reload-config"
    ;;
  *)
    echo "usage: $0 describe|install|uninstall|options [flags]" >&2
    exit 2
    ;;
esac
