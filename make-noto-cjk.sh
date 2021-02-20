#!/bin/bash
#
# Usages:
# % make-noto-cjk.sh
# Uses source files in `fonts` directory.
#
# % SRCDIR=noto-cjk/chromeos/noto-cjk-20190409 make-noto-cjk.sh
# Uses the source files in the specified directory.
#
# % BUILD=N make-noto-cjk.sh
# Skip building.
#
# % DIFF=N make-noto-cjk.sh
# Skip diffing.
#
SRCDIR=${SRCDIR:-fonts/}
OUTDIR=${OUTDIR:-build/}
WEIGHTS=${WEIGHTS:-Regular Bold Light}

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
GIDSDIR=${GIDSDIR:-${OUTDIR}chws/}
GIDSDIR=$(ensure-end-slash $GIDSDIR)

OUTFILES=()

# Build fonts.
build() {
  SRCFILE=$1
  shift
  if [[ ! -f "$SRCFILE" ]]; then return; fi
  BASENAME=$(basename $SRCFILE)
  OUTFILE=$OUTDIR$BASENAME
  OUTFILES+=($OUTFILE)
  if [[ "$BUILD" == "N" ]]; then return; fi
  GIDSPATH=$GIDSDIR$BASENAME-gids.txt
  (set -x; python3 Builder.py \
      --gids-file "$GIDSPATH" \
      -o "$OUTDIR" "$SRCFILE" $*)
}

build-all() {
  mkdir -p "$OUTDIR"
  mkdir -p "$GIDSDIR"
  for WEIGHT in $WEIGHTS; do
    build ${SRCDIR}NotoSansCJK-$WEIGHT.ttc --face-index=0,1,2,3,4 $*
    build ${SRCDIR}NotoSerifCJK-$WEIGHT.ttc --language=,KOR,ZHS $*
  done
}

build-all $*

echo "OUTFILES=${#OUTFILES[@]} (${OUTFILES[@]})"

if [[ "$DIFF" != "N" ]]; then
  ./diff-ref.sh $SRCDIR ${OUTFILES[@]}
fi
