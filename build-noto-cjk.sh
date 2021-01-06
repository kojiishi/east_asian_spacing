#!/bin/bash
FONTDIR=${FONTDIR:-noto-cjk-chws/}
build() {
  (set -x; python3 Builder.py $*)
}
build ${FONTDIR}NotoSansCJK-Regular.ttc --face-index=0,1,2,3,4 $*
build ${FONTDIR}NotoSerifCJK-Regular.ttc --language=,KOR,ZHS $*
