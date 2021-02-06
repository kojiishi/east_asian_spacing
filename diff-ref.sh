#!/bin/bash
#
# Usage: $0 target [source]
#
# This script checks differences in fonts by doing following steps:
# 1. Creates table lists and TTX dumps for source and target.
# 2. Creates diff of these files between source and target.
# 3. Compare the diff files with the ones in the reference directory.
#
OUTDIR=${OUTDIR:-build/}
DIFFDIR=${DIFFDIR:-$OUTDIR}
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
REFDIR=$(ensure-end-slash $REFDIR)
mkdir -p $OUTDIR
mkdir -p $SRCOUTDIR
mkdir -p $DIFFDIR

DSTPATH=$1
DSTBASENAME=$(basename $DSTPATH)
DSTOUTPATH=$OUTDIR$DSTBASENAME

SRCPATH=$2
if [[ -z "$SRCPATH" ]]; then
  SRCBASENAME=${DSTBASENAME/-chws/}
  for SRCDIR in $(dirname $DSTPATH) fonts .; do
    SRCPATH=$SRCDIR/$SRCBASENAME
    if [[ $DSTPATH != $SRCPATH && -f $SRCPATH ]]; then
      break
    fi
  done
elif [[ -d "$SRCPATH" ]]; then
  SRCDIR=$(ensure-end-slash $SRCPATH)
  SRCBASENAME=${DSTBASENAME/-chws/}
  SRCPATH=$SRCDIR$SRCBASENAME
else
  SRCBASENAME=$(basename $SRCPATH)
fi
SRCOUTPATH=$SRCOUTDIR$SRCBASENAME

DIFFOUTPATH=$DIFFDIR$SRCBASENAME
CHECKPATHS=()

# Create tablelists.
tablelist() {
  (set -x; python3 Dump.py -n $1) | \
    grep -v '^File: ' >$2
}
SRCTABLELISTPATH=$SRCOUTPATH-tablelist.txt
tablelist $SRCPATH $SRCTABLELISTPATH 
DSTTABLELISTPATH=$DSTOUTPATH-tablelist.txt
tablelist $DSTPATH $DSTTABLELISTPATH 
DIFFTABLELISTPATH=$DIFFOUTPATH-tablelist.diff
# Ignore first 2 lines (diff -u header).
(set -x; diff -u $SRCTABLELISTPATH $DSTTABLELISTPATH) | \
  tail -n +3 >$DIFFTABLELISTPATH
CHECKPATHS+=($DIFFTABLELISTPATH)

# Create TTX.
dump-ttx() {
  # Exclude CFF, post, and/or glyp tables for faster executions.
  # EXCLUDE=CFF
  (set -x; ttx -y $3 -x "$EXCLUDE" -o - $1) | \
    grep -v '<checkSumAdjustment value=' | \
    grep -v '<modified value=' >$2
}

TTC=$(grep '^Font [0-9][0-9]*:' $SRCTABLELISTPATH | wc -l)
for i in $(seq 0 $(expr $TTC - 1)); do
  # Source doesn't change often, dump only if it does not exist.
  SRCTTXPATH=$SRCOUTPATH-$i.ttx
  if [[ ! -f $SRCTTXPATH ]]; then
    dump-ttx $SRCPATH $SRCTTXPATH $i
  fi
  DSTTTXPATH=$DSTOUTPATH-$i.ttx
  dump-ttx $DSTPATH $DSTTTXPATH $i
  DIFFTTXPATH=$DIFFOUTPATH-$i.ttx.diff
  # Ignore first 2 lines (diff -u header) and line numbers.
  (set -x; diff -u $SRCTTXPATH $DSTTTXPATH) | \
    tail -n +3 | sed -e 's/^@@ -.*/@@/' >$DIFFTTXPATH
  CHECKPATHS+=($DIFFTTXPATH)
done

# Diff all files with reference files.
echo "Produced ${#CHECKPATHS[@]} diff files, comparing with references."
for CHECKPATH in ${CHECKPATHS[@]}; do
  REFDIFFNAME=$REFDIR$(basename $CHECKPATH)
  if [[ -f $REFDIFFNAME ]]; then
    (set -x; diff -u $REFDIFFNAME $CHECKPATH)
  else
    echo "No reference file for $CHECKPATH in $REFDIR"
  fi
done
