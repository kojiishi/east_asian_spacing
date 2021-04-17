#!/bin/bash
SCRIPTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
PYDIR="$(cd "$SCRIPTDIR/.." &>/dev/null && pwd)"
BUILDER=${BUILDER:-Builder.py}
LOG=${LOG:-build/log/build.log}
GLYPHSDIR=${GLYPHSDIR:-build/dump}

# Analyze argments.
SRCDIR=
BUILDER_ARGS=('--print' '--glyphs' "$GLYPHSDIR")
for ARG in "$@"; do
  if [[ "$ARG" == \-* ]]; then
    BUILDER_ARGS+=("$ARG")
    continue
  fi
  if [[ -z "$SRCDIR" ]]; then
    SRCDIR=$ARG
    continue
  fi
  BUILDER_ARGS+=("$ARG")
done
mkdir -p "$(dirname $LOG)"
mkdir -p "$GLYPHSDIR"

time (set -x; "$PYDIR/$BUILDER" "$SRCDIR" "${BUILDER_ARGS[@]}") |
     (set -x; "$PYDIR/diff-ref.sh" "$SRCDIR") |
     tee "$LOG"
