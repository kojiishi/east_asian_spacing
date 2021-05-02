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
REFDIR=${REFDIR:-references/}
SCRIPTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
ROOTDIR="$(cd "$SCRIPTDIR/.." &>/dev/null && pwd)"
PYDIR="$(cd "$ROOTDIR/east_asian_spacing" &>/dev/null && pwd)"

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

  # Create table lists, TTXs, and their diffs.
  while IFS= read DIFF; do
    CHECKPATHS+=("$DIFF")
  done < <(set -x;
    python3 "$PYDIR/dump.py" "$DSTPATH" -o "$OUTDIR" --diff "$SRC" $DUMPOPTS)
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

  # Check if glyph id file exists.
  DSTBASENAME=$(basename "$ARG")
  GLYPHSPATH=$OUTDIR$DSTBASENAME-glyphs
  if [[ -f "$GLYPHSPATH" ]]; then
    CHECKPATHS+=("$GLYPHSPATH")
  fi
done

# If no arguments, read the paths from stdin.
if [[ -z "$SRC" ]]; then
  while IFS=$'\t' read SRC DST GLYPHS; do
    create-diff "$SRC" "$DST"

    if [[ -n "$GLYPHS" ]]; then
      CHECKPATHS+=("$GLYPHS")
    fi
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
