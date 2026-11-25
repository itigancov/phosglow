#!/usr/bin/env bash
# Phosglow installer: lists Ports, installs or uninstalls the chosen ones.
# Run with --help for usage and every flag.
#
# A Port is a folder ports/<name>/ with an install.sh that answers four
# commands: describe, install, uninstall, options. See --help.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

die() { echo "install.sh: $*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Usage:
  install.sh                      menu of Ports (needs a terminal)
  install.sh PORT...              install the named Ports
  install.sh --uninstall [PORT...]  uninstall (all Ports when no terminal)
  install.sh --list               list Ports
  install.sh --dry-run ...        show what would change, change nothing
  install.sh --help               this text

Exit codes: 0 success, 1 error, 2 usage error.
EOF
}

# --- discover Ports -------------------------------------------------------
port_names=()
port_opts=()   # parallel to port_names: that Port's `options` output
for d in "$here"/ports/*/; do
  [ -f "${d}install.sh" ] || continue
  name=$(basename "$d")
  port_names[${#port_names[@]}]=$name
  port_opts[${#port_opts[@]}]=$("$BASH" "${d}install.sh" options)
done
[ ${#port_names[@]} -gt 0 ] || die "no Ports found in $here/ports"

port_index() {  # NAME -> index in port_names, or fail
  local i
  for ((i = 0; i < ${#port_names[@]}; i++)); do
    [ "${port_names[i]}" = "$1" ] && { echo "$i"; return 0; }
  done
  return 1
}

port_describe() { "$BASH" "$here/ports/$1/install.sh" describe; }

# Flag names (first word of the spec before the tab) of Port i, one per line.
port_flag_names() {
  local line
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    line=${line%%$'\t'*}
    echo "${line%% *}"
  done <<EOF
${port_opts[$1]}
EOF
}

# Does any Port declare FLAG with a value (spec "--flag ARG")?
flag_takes_value() {
  local i line
  for ((i = 0; i < ${#port_names[@]}; i++)); do
    while IFS= read -r line; do
      line=${line%%$'\t'*}
      case $line in "$1 "*) return 0 ;; esac
    done <<EOF
${port_opts[i]}
EOF
  done
  return 1
}

port_accepts() {  # INDEX FLAG
  local f
  while IFS= read -r f; do
    [ "$f" = "$2" ] && return 0
  done <<EOF
$(port_flag_names "$1")
EOF
  return 1
}

any_port_accepts() {  # FLAG
  local i
  for ((i = 0; i < ${#port_names[@]}; i++)); do
    port_accepts "$i" "$1" && return 0
  done
  return 1
}

full_help() {
  usage
  local i line spec desc
  for ((i = 0; i < ${#port_names[@]}; i++)); do
    echo
    port_describe "${port_names[i]}"
    while IFS= read -r line; do
      [ -n "$line" ] || continue
      spec=${line%%$'\t'*}
      desc=${line#*$'\t'}
      printf '  %-22s %s\n' "$spec" "$desc"
    done <<EOF
${port_opts[i]}
EOF
  done
}

# --- parse arguments ------------------------------------------------------
action=install
dry=0
list=0
help=0
chosen=()
flags=()
while [ $# -gt 0 ]; do
  case $1 in
    --list) list=1 ;;
    --dry-run) dry=1 ;;
    --uninstall) action=uninstall ;;
    -h|--help) help=1 ;;
    --*)
      arg=$1
      name=${arg%%=*}
      any_port_accepts "$name" || die "unknown flag $name (try --help)"
      if flag_takes_value "$name"; then
        if [ "$arg" != "$name" ]; then
          flags[${#flags[@]}]=$name
          flags[${#flags[@]}]=${arg#*=}
        else
          [ $# -ge 2 ] || die "$name needs a value (try --help)"
          flags[${#flags[@]}]=$name
          flags[${#flags[@]}]=$2
          shift
        fi
      else
        [ "$arg" = "$name" ] || die "$name takes no value (try --help)"
        flags[${#flags[@]}]=$name
      fi
      ;;
    -*) die "unknown option $1 (try --help)" ;;
    *) chosen[${#chosen[@]}]=$1 ;;
  esac
  shift
done

if [ "$help" -eq 1 ]; then full_help; exit 0; fi
if [ "$list" -eq 1 ]; then
  for name in "${port_names[@]}"; do port_describe "$name"; done
  exit 0
fi

# --- choose Ports ---------------------------------------------------------
selected=()   # indices
for name in ${chosen[@]+"${chosen[@]}"}; do
  i=$(port_index "$name") || die "unknown Port $name (try --list)"
  selected[${#selected[@]}]=$i
done

menu() {
  local i answer tok seen=" "
  echo "Ports:"
  for ((i = 0; i < ${#port_names[@]}; i++)); do
    printf '  %d) %s\n' "$((i + 1))" "$(port_describe "${port_names[i]}")"
  done
  printf 'Which to %s? Numbers separated by spaces, a = all, Enter = none: ' "$action"
  read -r answer || answer=""
  [ -n "${answer//[[:space:]]/}" ] || { echo "Nothing selected."; exit 0; }
  for tok in $answer; do
    if [ "$tok" = a ]; then
      selected=()
      for ((i = 0; i < ${#port_names[@]}; i++)); do selected[i]=$i; done
      return 0
    fi
    case $tok in
      ''|*[!0-9]*) die "invalid choice '$tok'" ;;
    esac
    [ "$tok" -ge 1 ] && [ "$tok" -le ${#port_names[@]} ] || die "invalid choice '$tok'"
    case $seen in *" $tok "*) continue ;; esac
    seen="$seen$tok "
    selected[${#selected[@]}]=$((tok - 1))
  done
}

if [ ${#selected[@]} -eq 0 ]; then
  if [ -t 0 ]; then
    menu
  elif [ "$action" = uninstall ]; then
    for ((i = 0; i < ${#port_names[@]}; i++)); do selected[i]=$i; done
  else
    usage >&2
    exit 2
  fi
fi

# Every flag must be accepted by at least one selected Port.
for f in ${flags[@]+"${flags[@]}"}; do
  case $f in --*) ;; *) continue ;; esac
  ok=0
  for i in "${selected[@]}"; do
    port_accepts "$i" "$f" && ok=1
  done
  [ "$ok" -eq 1 ] || die "flag $f is accepted by none of the selected Ports (try --help)"
done

# --- run ------------------------------------------------------------------
if [ "$dry" -eq 1 ]; then
  export PHOSGLOW_DRY_RUN=1
  echo "Dry run: nothing will change."
else
  unset PHOSGLOW_DRY_RUN
fi

for i in "${selected[@]}"; do
  name=${port_names[i]}
  echo "== $name: $action =="
  "$BASH" "$here/ports/$name/install.sh" "$action" ${flags[@]+"${flags[@]}"} \
    || die "$name: $action failed"
done
