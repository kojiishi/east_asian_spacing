#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." &>/dev/null && pwd)"
PY_DIR="$(cd "$ROOT_DIR/east_asian_spacing" &>/dev/null && pwd)"
BUILDER_NAME=${BUILDER_NAME:-builder.py}
BUILDER=${BUILDER:-$PY_DIR/$BUILDER_NAME}
BUILD_DIR=${BUILD_DIR:-build}
LOG_NAME=${LOG_NAME:-build.log}
LOG=${LOG:-$BUILD_DIR/log/$LOG_NAME}
DUMP_DIR=${DUMP_DIR:-$BUILD_DIR/dump}
GLYPHS_DIR=${GLYPHS_DIR:-$BUILD_DIR/dump}
REF_DIR=${REF_DIR:-$ROOT_DIR/references/$REF_NAME}
mkdir -p "$(dirname $LOG)"
mkdir -p "$GLYPHS_DIR"

BUILDER_ARGS=(-p -g="$GLYPHS_DIR")
DUMP_ARGS=(-o="$DUMP_DIR" -r="$REF_DIR" -)
time (set -x; "$BUILDER" "${BUILDER_ARGS[@]}" "$@") |
     (set -x; "$PY_DIR/dump.py" "${DUMP_ARGS[@]}" $DUMPOPTS) |
     tee "$LOG"
