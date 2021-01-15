#!/bin/bash
#
# Usage: $0 source target
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
REFDIR=$(ensure-end-slash $REFDIR)
mkdir -p $OUTDIR
mkdir -p $DIFFDIR

SRCNAME=$1
SRCBASENAME=$(basename $SRCNAME)
SRCOUTNAME=$OUTDIR$SRCBASENAME
DSTNAME=$2
DSTBASENAME=$(basename $DSTNAME)
DSTOUTNAME=$OUTDIR$DSTBASENAME
DIFFOUTNAME=$DIFFDIR$DSTBASENAME
CHECKNAMES=()

# Create tablelists.
tablelist() {
  (set -x; python3 Dump.py -n $1) | \
    grep -v '^File: ' >$2
}
SRCTABLELISTNAME=$SRCOUTNAME-tablelist.txt
tablelist $SRCNAME $SRCTABLELISTNAME 
DSTTABLELISTNAME=$DSTOUTNAME-tablelist.txt
tablelist $DSTNAME $DSTTABLELISTNAME 
DIFFTABLELISTNAME=$DIFFOUTNAME-tablelist.diff
# Ignore first 2 lines (diff -u header).
(set -x; diff -u $SRCTABLELISTNAME $DSTTABLELISTNAME) | \
  tail -n +3 >$DIFFTABLELISTNAME
CHECKNAMES+=($DIFFTABLELISTNAME)

# Create TTX.
dump-ttx() {
  # Exclude CFF, post, and/or glyp tables for faster executions.
  # EXCLUDE=CFF
  (set -x; ttx -y $3 -x "$EXCLUDE" -o - $1) | \
    grep -v '<checkSumAdjustment value=' | \
    grep -v '<modified value=' >$2
}

TTC=$(grep '^Font [0-9][0-9]*:' $SRCTABLELISTNAME | wc -l)
for i in $(seq 0 $(expr $TTC - 1)); do
  # Source doesn't change often, dump only if it does not exist.
  SRCTTXNAME=$SRCOUTNAME-$i.ttx
  if [[ ! -f $SRCTTXNAME ]]; then
    dump-ttx $SRCNAME $SRCTTXNAME $i
  fi
  DSTTTXNAME=$DSTOUTNAME-$i.ttx
  dump-ttx $DSTNAME $DSTTTXNAME $i
  DIFFTTXNAME=$DIFFOUTNAME-$i.diff
  # Ignore first 2 lines (diff -u header) and line numbers.
  (set -x; diff -u $SRCTTXNAME $DSTTTXNAME) | \
    tail -n +3 | sed -e 's/^@@ -.*/@@/' >$DIFFTTXNAME
  CHECKNAMES+=($DIFFTTXNAME)
done

# Diff all files with reference files.
echo "Produced ${#CHECKNAMES[@]} diff files, comparing with references."
for CHECKNAME in ${CHECKNAMES[@]}; do
  REFDIFFNAME=$REFDIR$(basename $CHECKNAME)
  if [[ -f $REFDIFFNAME ]]; then
    (set -x; diff -u $REFDIFFNAME $CHECKNAME)
  else
    echo "No reference file for $CHECKNAME in $REFDIR"
  fi
done
