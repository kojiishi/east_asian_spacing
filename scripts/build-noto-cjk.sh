#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
export LOG_NAME=${LOG_NAME:-noto-cjk.log}
"$SCRIPT_DIR/build.sh" $*
