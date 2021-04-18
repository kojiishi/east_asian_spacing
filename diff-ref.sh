#!/bin/bash
#
# Usage: $0 source target...
#
# If `source` is a directory, this tool can handle multiple `target`s.
# If `source` is a file, there can be only one `target`.
#
# This script checks differences in fonts by doing following steps:
# 1. Creates table lists and TTX dumps for source and target.
# 2. Creates diff of these files between source and target.
# 3. Compare the diff files with the ones in the reference directory.
#
OUTDIR=${OUTDIR:-build/dump}
REFDIR=${REFDIR:-reference/}

# Make sure directory names end with a slash to make joining easier.
ensure-end-slash() {
  if [[ -z "$1" || "$1" == */ ]]; then
    echo "$1"
  else
    echo "$1/"
  fi
}
OUTDIR=$(ensure-end-slash $OUTDIR)
REFDIR=$(ensure-end-slash $REFDIR)

create-diff () {
  SRC=$1
  DSTPATH=$2
  DSTBASENAME=$(basename "$DSTPATH")

  # Check if glyph id file exists.
  GLYPHSPATH=$OUTDIR$DSTBASENAME-glyphs
  if [[ -f "$GLYPHSPATH" ]]; then
    CHECKPATHS+=("$GLYPHSPATH")
  fi

  # Create table lists, TTXs, and their diffs.
  mapfile -t DIFFS < <(set -x;
      python3 Dump.py "$DSTPATH" -o "$OUTDIR" --diff "$SRC" $DUMPOPTS)
  CHECKPATHS+=("${DIFFS[@]}")
}

# Analyze argments.
# * If it starts with '-', add to DUMPOPTS.
# * The first argment is set to SRC.
# * The rests are set to DSTS.
CHECKPATHS=()
DUMPOPTS=${DUMPOPTS:-}
SRC=
for ARG in "$@"; do
  if [[ "$ARG" == \-* ]]; then
    DUMPOPTS="$DUMPOPTS $ARG"
    continue
  fi
  if [[ -z "$SRC" ]]; then
    SRC=$ARG
    continue
  fi
  create-diff "$SRC" "$ARG"
done

# If no arguments, read the paths from stdin.
if [[ -z "$SRC" ]]; then
  while IFS=$'\t' read SRC DST; do
    create-diff "$SRC" "$DST"
  done
fi

# Diff all diff files with reference files.
echo "Produced ${#CHECKPATHS[@]} diff files, comparing with references."
for CHECKPATH in ${CHECKPATHS[@]}; do
  REFDIFFNAME=$REFDIR$(basename $CHECKPATH)
  if [[ -f $REFDIFFNAME ]]; then
    (set -x; diff -u "$REFDIFFNAME" "$CHECKPATH")
  else
    echo "No reference file for $CHECKPATH in $REFDIR"
  fi
done
