#!/bin/bash
SCRIPTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
export LOG=build/log/chromeos.log
export REFDIR=references/chromeos
"$SCRIPTDIR/build-noto-cjk.sh" $*
