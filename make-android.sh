#!/bin/bash
export LOG=build/log/andoid.log
export REFDIR=reference/android
SRCDIR=${SRCDIR:-fonts/g/noto-cjk/android/20210103}
./make-noto-cjk.sh "$SRCDIR" $*
