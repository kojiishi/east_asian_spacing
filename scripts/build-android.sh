#!/bin/bash
SCRIPTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
export LOG=build/log/andoid.log
export REFDIR=references/android
"$SCRIPTDIR/build-noto-cjk.sh" $*
