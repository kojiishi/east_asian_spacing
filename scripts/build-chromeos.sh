#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
export LOG_NAME=chromeos.log
export REF_NAME=chromeos
"$SCRIPT_DIR/build-noto-cjk.sh" $*
