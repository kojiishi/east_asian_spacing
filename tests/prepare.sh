#!/bin/bash
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
ROOT_DIR="$(cd "$TEST_DIR/.." &>/dev/null && pwd)"
FONT_DIR="$ROOT_DIR/fonts"
GIT_URL=https://raw.githubusercontent.com
FONT_REPO=$GIT_URL/googlefonts/noto-cjk
FONT_PATH=Sans/OTF/Japanese/NotoSansCJKjp-Regular.otf
FONT_NAME=$(basename "$FONT_PATH")
if [[ ! -f "$FONT_DIR/$FONT_NAME" ]]; then
  (set -x;
    curl -o "$FONT_DIR/$FONT_NAME" --create-dirs "$FONT_REPO/main/$FONT_PATH")
fi
