#!/bin/bash
SCRIPTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
export BUILDER=noto_cjk_builder.py
export LOG=${LOG:-build/log/noto-cjk.log}
"$SCRIPTDIR/build.sh" $*
