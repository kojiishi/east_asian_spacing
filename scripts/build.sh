#!/bin/bash
SCRIPTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
PYDIR="$(cd "$SCRIPTDIR/.." &>/dev/null && pwd)"
BUILDER=${BUILDER:-Builder.py}
LOG=${LOG:-build/log/build.log}
GLYPHSDIR=${GLYPHSDIR:-build/dump}

SRCDIR=$1
if [[ -z "$SRCDIR" ]]; then
  echo "Usage: $0 source-dir" >&2
  exit 1
fi
shift
mkdir -p "$(dirname $LOG)"
mkdir -p "$GLYPHSDIR"

time "$PYDIR/$BUILDER" --print --glyphs "$GLYPHSDIR" "$SRCDIR" $* |
     "$PYDIR/diff-ref.sh" "$SRCDIR" |
     tee "$LOG"
