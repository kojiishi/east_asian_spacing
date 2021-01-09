#!/bin/bash
# SRCDIR=${SRCDIR:-noto-cjk-chws/}
SRCDIR=${SRCDIR:-./}
OUTDIR=${OUTDIR:-$SRCDIR}
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

# Create tablelists.
tablelist() {
  (set -x; python3 Dump.py $*)
}
tablelist -n >${OUTDIR}tablelist.txt \
  ${SRCDIR}NotoSansCJK-Regular.ttc \
  ${SRCDIR}NotoSerifCJK-Regular.ttc
tablelist -n >${OUTDIR}tablelist-chws.txt \
  ${OUTDIR}NotoSansCJK-Regular-chws.ttc \
  ${OUTDIR}NotoSerifCJK-Regular-chws.ttc

# Diff TTX dumps.
ttxdiff() {
  (set -x; ttx -x CFF -y $2 -o $TTXDIR$1-$2.ttx $SRCDIR$1.ttc)
  (set -x; ttx -x CFF -y $2 -o $TTXDIR$1-chws-$2.ttx $OUTDIR$1-chws.ttc)
  (set -x; diff -u $TTXDIR$1-$2.ttx $TTXDIR$1-chws-$2.ttx > $TTXDIR$1-$2.diff)
}
ttxdiff-all() {
  mkdir -p $TTXDIR
  for i in {0..8}; do
    ttxdiff NotoSansCJK-Regular $i
  done
  for i in {0..3}; do
    ttxdiff NotoSerifCJK-Regular $i
  done
}
if [[ -n "$TTXDIR" ]]; then
  ttxdiff-all
fi
