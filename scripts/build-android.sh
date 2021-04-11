#!/bin/bash
SCRIPTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
export LOG=build/log/andoid.log
export REFDIR=reference/android
SRCDIR=${SRCDIR:-fonts/g/noto-cjk/android/20210103}
"$SCRIPTDIR/build-noto-cjk.sh" "$SRCDIR" $*
