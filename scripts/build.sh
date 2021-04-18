#!/bin/bash
SCRIPTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
PYDIR="$(cd "$SCRIPTDIR/.." &>/dev/null && pwd)"
BUILDER=${BUILDER:-Builder.py}
LOG=${LOG:-build/log/build.log}
GLYPHSDIR=${GLYPHSDIR:-build/dump}
BUILDER_ARGS=('--path-out=-' '--glyph-out' "$GLYPHSDIR")
time (set -x; "$PYDIR/$BUILDER" "${BUILDER_ARGS[@]}" "$@") |
     (set -x; "$PYDIR/diff-ref.sh") |
     tee "$LOG"
