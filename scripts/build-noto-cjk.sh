#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
export BUILDER_NAME=noto_cjk_builder.py
export LOG_NAME=${LOG_NAME:-noto-cjk.log}
"$SCRIPT_DIR/build.sh" $*
