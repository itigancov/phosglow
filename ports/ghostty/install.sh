#!/usr/bin/env bash
# Ghostty Port. Commands: describe | install | uninstall | options.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../tools/lib.sh
. "$here/../../tools/lib.sh"

cmd=${1:-}
[ $# -gt 0 ] && shift

dir="${XDG_CONFIG_HOME:-$HOME/.config}/ghostty"
crt=1
while [ $# -gt 0 ]; do
  case $1 in
    --ghostty-dir) dir=$2; shift ;;
    --no-crt) crt=0 ;;
  esac
  shift
done

# Ghostty reads config.ghostty; older installs use a file named config.
if [ -f "$dir/config.ghostty" ]; then
  config="$dir/config.ghostty"
elif [ -f "$dir/config" ]; then
  config="$dir/config"
else
  config="$dir/config.ghostty"
fi

# Prints the last `theme =` line outside the phosglow block, if any.
overridden_theme() {
  [ -f "$config" ] || return 0
  local line n=0 in_block=0 found=""
  while IFS= read -r line || [ -n "$line" ]; do
    n=$((n + 1))
    if [ "$line" = "$PHOSGLOW_BLOCK_START" ]; then in_block=1; continue; fi
    if [ "$line" = "$PHOSGLOW_BLOCK_END" ]; then in_block=0; continue; fi
    [ "$in_block" -eq 1 ] && continue
    if [[ $line =~ ^[[:space:]]*theme[[:space:]]*=[[:space:]]*(.*)$ ]]; then
      found="$n:${BASH_REMATCH[1]}"
    fi
  done < "$config"
  [ -z "$found" ] || echo "$found"
}

case $cmd in
  describe)
    echo "ghostty: Phosglow colours and the optional CRT shader for Ghostty"
    ;;
  options)
    printf -- '--ghostty-dir DIR\tDirectory holding the Ghostty config, themes/ and shaders/ (default: $XDG_CONFIG_HOME/ghostty or ~/.config/ghostty)\n'
    printf -- '--no-crt\tInstall the colours without the CRT shader\n'
    ;;
  install)
    copy_file "$here/Phosglow" "$dir/themes/Phosglow"
    copy_file "$here/phosglow.glsl" "$dir/shaders/phosglow.glsl"
    old=$(overridden_theme)
    if [ -n "$old" ]; then
      echo "warning: $config line ${old%%:*}: theme = ${old#*:} is overridden by the phosglow block (remove the block to restore)"
    fi
    content="theme = Phosglow"
    if [ "$crt" -eq 1 ]; then
      content="$content"$'\n'"custom-shader = shaders/phosglow.glsl"
    fi
    add_block "$config" "$content"
    echo "Reload Ghostty's config (Cmd+Shift+, on macOS) or open a new window."
    ;;
  uninstall)
    remove_block "$config"
    remove_file "$dir/themes/Phosglow"
    remove_file "$dir/shaders/phosglow.glsl"
    ;;
  *)
    echo "usage: $0 describe|install|uninstall|options [flags]" >&2
    exit 2
    ;;
esac
