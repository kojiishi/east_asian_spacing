#!/bin/bash
SCRIPTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
ROOTDIR="$(cd "$SCRIPTDIR/.." &>/dev/null && pwd)"
PYDIR="$(cd "$ROOTDIR/east_asian_spacing" &>/dev/null && pwd)"
BUILDER=${BUILDER:-builder.py}
LOG=${LOG:-build/log/build.log}
DUMPDIR=${DUMPDIR:-build/dump}
GLYPHSDIR=${GLYPHSDIR:-build/dump}
REFDIR=${REFDIR:-references/}
mkdir -p "$(dirname $LOG)"
mkdir -p "$GLYPHSDIR"

BUILDER_ARGS=(-p --glyph-out="$GLYPHSDIR")
DUMP_ARGS=(-o="$DUMPDIR" --ref="$REFDIR" -)
time (set -x; "$PYDIR/$BUILDER" "${BUILDER_ARGS[@]}" "$@") |
     (set -x; "$PYDIR/dump.py" "${DUMP_ARGS[@]}" $DUMPOPTS) |
     tee "$LOG"
