#!/bin/bash
SRCDIR=$1
if [[ -z "$SRCDIR" ]]; then
  echo "Usage: $0 source-dir" >&2
  exit 1
fi
shift
LOG=${LOG:-build/log/noto-cjk.log}
mkdir -p "$(dirname $LOG)"
time ./NotoCJKBuilder.py "$SRCDIR" $* |
     ./diff-ref.sh "$SRCDIR" $* |
     tee "$LOG"
