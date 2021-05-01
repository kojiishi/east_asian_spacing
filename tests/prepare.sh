#!/bin/bash
TESTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
ROOTDIR="$(cd "$TESTDIR/.." &>/dev/null && pwd)"
FONTDIR="$ROOTDIR/fonts"
mkdir -p "$FONTDIR"
FONT_REPO=googlefonts/noto-cjk
FONT_NAME=NotoSansCJKjp-Regular.otf
if [[ ! -f "$FONTDIR/$FONT_NAME" ]]; then
  (cd "$FONTDIR"
    curl -O "https://raw.githubusercontent.com/$FONT_REPO/main/Sans/OTF/Japanese/$FONT_NAME")
fi
