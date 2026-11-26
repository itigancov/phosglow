#!/bin/bash
# Run every Phosglow check: freshness, the unit tests, plugin validation.
# One command, no flags; the same locally and in CI. Works with macOS
# /bin/bash 3.2. Prints PASS, FAIL or SKIP per step and a summary; exits 1 if
# any step failed. All checking logic is Python: this script only glues steps.
#
# PHOSGLOW_ROOT: the repo to check (default: the repo this script lives in).
# Point it at a throwaway copy to see a check fail on purpose.

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="${PHOSGLOW_ROOT:-$(dirname "$here")}"
export PHOSGLOW_ROOT="$root"
export PYTHONDONTWRITEBYTECODE=1  # never write into the tree under test

passed=0 failed=0 skipped=0

report() {  # STATUS NAME [REASON]
  printf '%-4s  %s%s\n' "$1" "$2" "${3:+ ($3)}"
  case $1 in
    PASS) passed=$((passed + 1)) ;;
    FAIL) failed=$((failed + 1)) ;;
    SKIP) skipped=$((skipped + 1)) ;;
  esac
}

step() {  # NAME COMMAND...
  local name=$1
  shift
  echo "== $name"
  if "$@"; then report PASS "$name"; else report FAIL "$name"; fi
}

finish() {
  echo
  echo "$passed passed, $failed failed, $skipped skipped"
  [ "$failed" -eq 0 ]
  exit
}

# --- Python 3.11+ (tomllib) -------------------------------------------------
py_version=$(python3 --version 2>&1)
case $py_version in
  "Python "[0-9]*) ;;
  *) report FAIL python "python3 not found; Phosglow needs Python 3.11+"; finish ;;
esac
py_version=${py_version#Python }
py_major=${py_version%%.*}
py_minor=${py_version#*.}
py_minor=${py_minor%%[!0-9]*}
if [ "$py_major" -lt 3 ] || { [ "$py_major" -eq 3 ] && [ "$py_minor" -lt 11 ]; }; then
  report FAIL python "found Python $py_version; Phosglow needs Python 3.11+ (tomllib)"
  finish
fi

# --- steps --------------------------------------------------------------------
step freshness python3 "$root/tools/check_fresh.py"
step "unit tests" python3 -m unittest discover -s "$root/tests"

if command -v claude >/dev/null 2>&1; then
  validate_plugin() {
    local ok=0
    claude plugin validate --strict "$root/ports/claude-code" || ok=1
    claude plugin validate --strict "$root" || ok=1
    return $ok
  }
  step "plugin validation" validate_plugin
else
  report SKIP "plugin validation" "claude CLI not on PATH"
fi

finish
