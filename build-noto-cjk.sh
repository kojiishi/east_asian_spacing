#!/bin/bash
# SRCDIR=${SRCDIR:-noto-cjk-chws/}
SRCDIR=${SRCDIR:-fonts/}
OUTDIR=${OUTDIR:-build/}
# TTXDIR=${TTXDIR:-${OUTDIR}ttx/}

# Make sure directory names end with a slash to make joining easier.
ensure-end-slash() {
  if [[ -z "$1" || "$1" == */ ]]; then
    echo "$1"
  else
    echo "$1/"
  fi
}
SRCDIR=$(ensure-end-slash $SRCDIR)
OUTDIR=$(ensure-end-slash $OUTDIR)
TTXDIR=$(ensure-end-slash $TTXDIR)

# Build fonts.
build() {
  (set -x; python3 Builder.py -o $OUTDIR $*)
}
build-all() {
  mkdir -p $OUTDIR
  build ${SRCDIR}NotoSansCJK-Regular.ttc --face-index=0,1,2,3,4 $*
  build ${SRCDIR}NotoSerifCJK-Regular.ttc --language=,KOR,ZHS $*
}
if [[ "$BUILD" != "N" ]]; then
  build-all $*
fi

./diff-ref.sh ${OUTDIR}NotoSansCJK-Regular-chws.ttc \
              ${SRCDIR}NotoSansCJK-Regular.ttc
./diff-ref.sh ${OUTDIR}NotoSerifCJK-Regular-chws.ttc \
              ${SRCDIR}NotoSerifCJK-Regular.ttc
