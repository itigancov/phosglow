# Shared helpers for the installers. Source this file; bash 3.2, no other deps.
#
# In dry-run (PHOSGLOW_DRY_RUN=1) every helper that changes a file only
# prints what it would do. print_snippet always prints.

PHOSGLOW_BLOCK_START="# >>> phosglow >>>"
PHOSGLOW_BLOCK_END="# <<< phosglow <<<"

_dry() { [ "${PHOSGLOW_DRY_RUN:-}" = 1 ]; }

# copy_file SRC DST: create DST's directory, overwrite DST.
copy_file() {
  if _dry; then echo "would copy $1 -> $2"; return 0; fi
  mkdir -p "$(dirname "$2")" || return 1
  cp "$1" "$2" || return 1
  echo "copied $2"
}

# remove_file FILE: delete FILE if it exists.
remove_file() {
  [ -e "$1" ] || return 0
  if _dry; then echo "would remove $1"; return 0; fi
  rm -f "$1" || return 1
  echo "removed $1"
}

# add_block FILE CONTENT: append a marked block (blank line, start marker,
# CONTENT, end marker) to FILE, creating it if needed. An existing block is
# replaced, so repeated runs give the same result. Works for any config
# format with `#` comments.
add_block() {
  local file=$1 content=$2
  if _dry; then
    echo "would add to $file:"
    printf '  %s\n' "$PHOSGLOW_BLOCK_START"
    printf '%s\n' "$content" | sed 's/^/  /'
    printf '  %s\n' "$PHOSGLOW_BLOCK_END"
    return 0
  fi
  _strip_block "$file" || return 1
  mkdir -p "$(dirname "$file")" || return 1
  # The leading newline is the blank line, or, when the last line has no
  # newline of its own, the newline that ends it. _strip_block tells the two
  # apart by looking at the line before the start marker.
  printf '\n%s\n%s\n%s\n' "$PHOSGLOW_BLOCK_START" "$content" "$PHOSGLOW_BLOCK_END" >> "$file" || return 1
  echo "updated $file"
}

# remove_block FILE: remove the marked block and the blank line before it.
# A file left empty is deleted (it was created by add_block).
remove_block() {
  local file=$1
  [ -f "$file" ] || return 0
  if _dry; then
    if grep -qxF "$PHOSGLOW_BLOCK_START" "$file"; then echo "would remove the phosglow block from $file"; fi
    return 0
  fi
  if grep -qxF "$PHOSGLOW_BLOCK_START" "$file"; then
    _strip_block "$file" || return 1
    echo "removed the phosglow block from $file"
    if [ ! -s "$file" ]; then rm -f "$file" && echo "removed empty $file"; fi
  fi
}

# print_snippet TITLE TEXT: framed text for the user to act on by hand.
print_snippet() {
  printf '\n%s\n' "== $1 =="
  printf '%s\n' "$2"
  printf '%s\n\n' "=="
}

# _strip_block FILE: the removal itself; no messages, no deleting.
_strip_block() {
  local file=$1
  [ -f "$file" ] || return 0
  grep -qxF "$PHOSGLOW_BLOCK_START" "$file" || return 0
  local lines=() line i=0 s=-1 e=-1 last_nl=1
  while IFS= read -r line || { [ -n "$line" ] && last_nl=0; }; do
    lines[i]=$line
    if [ "$s" -lt 0 ] && [ "$line" = "$PHOSGLOW_BLOCK_START" ]; then s=$i; fi
    if [ "$s" -ge 0 ] && [ "$e" -lt 0 ] && [ "$line" = "$PHOSGLOW_BLOCK_END" ]; then e=$i; fi
    i=$((i + 1))
  done < "$file"
  [ "$s" -ge 0 ] && [ "$e" -ge 0 ] || return 0
  local n=$i keep_to=$s strip_nl=0
  if [ "$s" -gt 0 ]; then
    if [ -z "${lines[s-1]}" ]; then
      keep_to=$((s - 1))
    elif [ "$e" -eq $((n - 1)) ]; then
      strip_nl=1
    fi
  fi
  : > "$file" || return 1
  local j out_last=-1
  for ((j = 0; j < n; j++)); do
    if [ "$j" -ge "$keep_to" ] && [ "$j" -le "$e" ]; then continue; fi
    out_last=$j
  done
  for ((j = 0; j < n; j++)); do
    if [ "$j" -ge "$keep_to" ] && [ "$j" -le "$e" ]; then continue; fi
    if [ "$j" -eq "$out_last" ] && { [ "$strip_nl" -eq 1 ] || { [ "$last_nl" -eq 0 ] && [ "$j" -eq $((n - 1)) ]; }; }; then
      printf '%s' "${lines[j]}" >> "$file"
    else
      printf '%s\n' "${lines[j]}" >> "$file"
    fi
  done
}
