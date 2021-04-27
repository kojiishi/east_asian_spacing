#!/bin/bash
SCRIPTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
ROOTDIR="$(cd "$SCRIPTDIR/.." &>/dev/null && pwd)"
PYDIR="$(cd "$ROOTDIR/east_asian_spacing" &>/dev/null && pwd)"
BUILDER=${BUILDER:-builder.py}
LOG=${LOG:-build/log/build.log}
GLYPHSDIR=${GLYPHSDIR:-build/dump}
mkdir -p "$(dirname $LOG)"
mkdir -p "$GLYPHSDIR"

BUILDER_ARGS=('--path-out=-' '--glyph-out' "$GLYPHSDIR")
time (set -x; "$PYDIR/$BUILDER" "${BUILDER_ARGS[@]}" "$@") |
     (set -x; "$SCRIPTDIR/diff-ref.sh") |
     tee "$LOG"
