#!/usr/bin/env bash
# iTerm2 Port. Prints instructions; never edits iTerm2 preferences.
# Commands: describe | install | uninstall | options.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../tools/lib.sh
. "$here/../../tools/lib.sh"

cmd=${1:-}

case $cmd in
  describe)
    echo "iterm2: Phosglow colour preset for iTerm2 (printed import steps)"
    ;;
  options)
    ;;
  install)
    print_snippet "iTerm2: import the colours" \
"1. Open iTerm2 > Settings > Profiles > Colors.
2. Open the Color Presets... menu and choose Import...
3. Select $here/Phosglow.itermcolors
4. Open Color Presets... again and choose Phosglow."
    ;;
  uninstall)
    print_snippet "iTerm2: remove the colours" \
"1. Open iTerm2 > Settings > Profiles > Colors.
2. Open the Color Presets... menu and choose Delete Preset...
3. Select Phosglow."
    ;;
  *)
    echo "usage: $0 describe|install|uninstall|options [flags]" >&2
    exit 2
    ;;
esac
