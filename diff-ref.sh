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
OUTDIR=${OUTDIR:-build/}
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
SRCOUTDIR=${OUTDIR}src/
DSTOUTDIR=${OUTDIR}out/
DIFFOUTDIR=${OUTDIR}diff/
REFDIR=$(ensure-end-slash $REFDIR)
mkdir -p $SRCOUTDIR
mkdir -p $DSTOUTDIR
mkdir -p $DIFFOUTDIR

SRCDIR=$1
shift
if [[ -d "$SRCDIR" ]]; then
  SRCDIR=$(ensure-end-slash $SRCDIR)
  SRCPATH=
else
  if [[ $# -ne 1 ]]; then
    echo "There must be one target" >&2
    exit 1
  fi
  SRCPATH=$SRCDIR
  SRCDIR=
fi

tablelist() {
  (set -x; python3 Dump.py -n "$1" --ttx "$3") | \
    grep -v '^File: ' >"$2"
}

dump-ttx() {
  # Exclude CFF, post, and/or glyp tables for faster executions.
  # EXCLUDE=CFF
  (set -x; ttx -y $3 -x "$EXCLUDE" -o - "$1") | \
    grep -v '<checkSumAdjustment value=' | \
    grep -v '<modified value=' >"$2"
}

CHECKPATHS=()
for DSTPATH in "$@"; do
  DSTBASENAME=$(basename "$DSTPATH")
  DSTOUTPATH=$DSTOUTDIR$DSTBASENAME

  if [[ -n "$SRCDIR" ]]; then
    SRCBASENAME=$DSTBASENAME
    SRCPATH=$SRCDIR$SRCBASENAME
  else
    SRCBASENAME=$(basename $SRCPATH)
  fi
  SRCOUTPATH=$SRCOUTDIR$SRCBASENAME
  DIFFOUTPATH=$DIFFOUTDIR$SRCBASENAME

  # Check if glyph id file exists.
  GIDSPATH=${DSTOUTPATH}-gids.txt
  if [[ -f "$GIDSPATH" ]]; then
    CHECKPATHS+=("$GIDSPATH")
  fi

  # Create table lists.
  DUMPJOBS=()
  SRCTABLELISTPATH=$SRCOUTPATH.tables
  SRCTTXPATH=$SRCOUTPATH.ttx
  tablelist "$SRCPATH" "$SRCTABLELISTPATH" "$SRCTTXPATH" &
  DUMPJOBS+=($!)
  DSTTABLELISTPATH=$DSTOUTPATH.tables
  DSTTTXPATH=$DSTOUTPATH.ttx
  tablelist "$DSTPATH" "$DSTTABLELISTPATH" "$DSTTTXPATH" &
  DUMPJOBS+=($!)
  wait ${DUMPJOBS[@]}

  # Diff table lists.
  DIFFTABLELISTPATH=$DIFFOUTPATH.tables.diff
  # Ignore first 2 lines (diff -u header).
  (set -x; diff -u "$SRCTABLELISTPATH" "$DSTTABLELISTPATH") | \
    tail -n +3 >"$DIFFTABLELISTPATH"
  CHECKPATHS+=("$DIFFTABLELISTPATH")

  # Diff TTX files.
  TTC=$(grep '^Font [0-9][0-9]*:' "$SRCTABLELISTPATH" | wc -l)
  for i in $(seq 0 $(expr $TTC - 1)); do
    if [[ $TTC -eq 1 ]]; then
      TTXFILES=("$SRCTTXPATH" "$DSTTTXPATH")
    else
      TTXFILES=("$SRCOUTPATH-$i.ttx" "$DSTOUTPATH-$i.ttx")
    fi
    mapfile -t TTX_TABLES < <(cat "${TTXFILES[@]}" |\
        perl -ne '/src="(.*)"/ && print "$1\n"' |\
        sort | uniq)
    for TTX_TABLE in ${TTX_TABLES[@]}; do
      DIFF_TTX_TABLE=$DIFFOUTDIR${TTX_TABLE}.diff
      (set -x; diff -u "$SRCOUTDIR$TTX_TABLE" "$DSTOUTDIR$TTX_TABLE") |\
          tail -n +3 | sed -e 's/^@@ -.*/@@/' >"$DIFF_TTX_TABLE"
      if [[ ! -s "$DIFF_TTX_TABLE" ]]; then
        rm "$DIFF_TTX_TABLE"
        continue
      fi
      if [[ "$TTX_TABLE" == *_h_e_a_d.ttx ]]; then
        DIFF_COUNT=$(tail -n +3 "$DIFF_TTX_TABLE" |\
            grep -v '<checkSumAdjustment value=' |\
            grep -v '<modified value=' |\
            grep '^[-+]' | wc -l)
        if [[ $DIFF_COUNT -eq 0 ]]; then
          rm "$DIFF_TTX_TABLE"
          continue
        fi
      fi
      echo "Differences found in $TTX_TABLE"
      CHECKPATHS+=("$DIFF_TTX_TABLE")
    done
  done
done

# Wait until all jobs are done.
NJOBS=$(jobs | wc -l)
echo "Waiting for $NJOBS jobs to complete..."
wait
echo "All $NJOBS jobs completed."

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
