#!/bin/bash
SCRIPTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
export LOG=build/log/chromeos.log
export REFDIR=reference/chromeos
SRCDIR=${SRCDIR:-fonts/g/noto-cjk/chromeos/noto-cjk-20190409}
"$SCRIPTDIR/build-noto-cjk.sh" "$SRCDIR" $*
