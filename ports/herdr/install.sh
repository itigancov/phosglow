#!/usr/bin/env bash
# herdr Port. Prints instructions; never edits the herdr config (only the
# Plugin's Apply action, which the user invokes, does).
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

$(cat "$here/phosglow.toml")

Or install the herdr Plugin and run its action instead of pasting:

  herdr plugin install itigancov/phosglow/ports/herdr
  herdr plugin action invoke apply --plugin itigancov.phosglow   # \"Apply Phosglow\""
    ;;
  uninstall)
    print_snippet "herdr: remove by hand" \
"Delete the [theme.custom] section from $config, then run:

  herdr server reload-config

If you used the herdr Plugin, run \"Remove Phosglow\" first, then uninstall it:

  herdr plugin action invoke remove --plugin itigancov.phosglow
  herdr plugin uninstall itigancov.phosglow"
    ;;
  *)
    echo "usage: $0 describe|install|uninstall|options [flags]" >&2
    exit 2
    ;;
esac
