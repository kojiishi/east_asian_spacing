#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." &>/dev/null && pwd)"
PY_DIR="$(cd "$ROOT_DIR/east_asian_spacing" &>/dev/null && pwd)"
BUILDER=${BUILDER:-$PY_DIR/builder.py}
BUILD_DIR=${BUILD_DIR:-build}
LOG_NAME=${LOG_NAME:-build.log}
LOG=${LOG:-$BUILD_DIR/log/$LOG_NAME}
DIFF_DIR=${DIFF_DIR:-$BUILD_DIR/diff}
GLYPHS_DIR=${GLYPHS_DIR:-$BUILD_DIR/diff}
REF_DIR=${REF_DIR:-$ROOT_DIR/references/$REF_NAME}
mkdir -p "$(dirname $LOG)"
mkdir -p "$GLYPHS_DIR"

BUILDER_ARGS=(-p -g="$GLYPHS_DIR")
DUMP_ARGS=(-o="$DIFF_DIR" -r="$REF_DIR" -)
time (set -x; "$BUILDER" "${BUILDER_ARGS[@]}" "$@") |
     (set -x; "$PY_DIR/dump.py" "${DUMP_ARGS[@]}" $DUMPOPTS) |
     tee "$LOG"
