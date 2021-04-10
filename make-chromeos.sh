#!/bin/bash
export LOG=build/log/chromeos.log
export REFDIR=reference/chromeos
SRCDIR=${SRCDIR:-fonts/g/noto-cjk/chromeos/noto-cjk-20190409}
./make-noto-cjk.sh "$SRCDIR" $*
