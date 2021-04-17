#!/bin/bash
OUTDIR=${OUTDIR:-build/}
SUFFIX=${SUFFIX:--chws-subset}
#FEATURES=${FEATURES:-chws,fwid}
FEATURES=${FEATURES:-chws}
if [[ -z "$DROPTABLES" ]]; then
  DROPTABLES=vhea,vmtx,VORG
  # GSUB table will be empty, but `pyftsubset` keeps an empty table.
  if [[ $FEATURES != *fwid* ]]; then
    DROPTABLES=${DROPTABLES},GSUB
  fi
fi

# Make sure directory names end with a slash to make joining easier.
ensure-end-slash() {
  if [[ -z "$1" || "$1" == */ ]]; then
    echo "$1"
  else
    echo "$1/"
  fi
}
OUTDIR=$(ensure-end-slash $OUTDIR)

if [[ -z $UNICODES ]]; then
  UNICODES=build/subset-unicodes.txt
  cat >$UNICODES <<EOF
# IDEOGRAPHIC SPACE
3000
# IDEOGRAPHIC COMMA, IDEOGRAPHIC FULL STOP
3001,3002
# LEFT ANGLE BRACKET
3008-3011,3014-301B
# REVERSED DOUBLE PRIME QUOTATION MARK
301D-301F
# KATAKANA MIDDLE DOT
30FB
# FULLWIDTH LEFT/RIGHT PARENTHESIS
FF08,FF09
# FULLWIDTH COMMA, FULLWIDTH FULL STOP
FF0C,FF0E
# ULLWIDTH COLON/SEMICOLON
FF1A,FF1B
# FULLWIDTH LEFT SQUARE BRACKET
FF3B,FF3D
# FULLWIDTH LEFT CURLY BRACKET
FF5B,FF5D
# FULLWIDTH LEFT WHITE PARENTHESIS
FF5F,FF60
EOF
  if [[ $FEATURES == *fwid* ]]; then
    cat >>$UNICODES <<EOF
# LEFT SINGLE QUOTATION MARK
2018-201F
EOF
  fi
fi

# Analyze argments.
for ARG in "$@"; do
  FTSUBSET_ARGS=()
  FTSUBSET_ARGS+=("--unicodes-file=$UNICODES")
  FTSUBSET_ARGS+=("--drop-tables+=$DROPTABLES")
  FTSUBSET_ARGS+=("--layout-features=$FEATURES")

  # Compute the output file name.
  BASENAME=$(basename $ARG)
  BASENAME_WO_EXT=${BASENAME%.*}
  FTSUBSET_ARGS+=('--flavor=woff2' '--with-zopfli')
  SUBSET_EXT=.woff
  # EXT=${NAME/$NAME_WO_EXT/}
  SUBSET_PATH=$OUTDIR$BASENAME_WO_EXT$SUFFIX$SUBSET_EXT
  FTSUBSET_ARGS+=(--output-file="$SUBSET_PATH" "$ARG")

  (set -x; pyftsubset "${FTSUBSET_ARGS[@]}")
  ls -l "$ARG" "$SUBSET_PATH"
done
