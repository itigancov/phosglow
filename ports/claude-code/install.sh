#!/usr/bin/env bash
# Claude Code Port. Commands: describe | install | uninstall | options.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../tools/lib.sh
. "$here/../../tools/lib.sh"

cmd=${1:-}
[ $# -gt 0 ] && shift

dir="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
while [ $# -gt 0 ]; do
  case $1 in
    --claude-dir) dir=$2; shift ;;
  esac
  shift
done

case $cmd in
  describe)
    echo "claude-code: Phosglow theme for Claude Code (copied into its config directory)"
    ;;
  options)
    printf -- '--claude-dir DIR\tClaude Code config directory (default: $CLAUDE_CONFIG_DIR or ~/.claude)\n'
    ;;
  install)
    copy_file "$here/themes/phosglow.json" "$dir/themes/phosglow.json"
    print_snippet "Turn the theme on" \
"Add this line to $dir/settings.json (not edited for you):

  \"theme\": \"custom:phosglow\"

Or use the plugin instead of the copied file:

  /plugin marketplace add itigancov/phosglow
  /plugin install phosglow@phosglow"
    ;;
  uninstall)
    remove_file "$dir/themes/phosglow.json"
    echo "If you set \"theme\": \"custom:phosglow\" in $dir/settings.json, change it back."
    ;;
  *)
    echo "usage: $0 describe|install|uninstall|options [flags]" >&2
    exit 2
    ;;
esac
