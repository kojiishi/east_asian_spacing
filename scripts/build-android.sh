#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
export LOG_NAME=andoid.log
export REF_NAME=android
"$SCRIPT_DIR/build-noto-cjk.sh" $*
