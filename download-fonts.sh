#!/bin/bash
#
# Download fonts for testing.
#
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
FONT_DIR="$ROOT_DIR/fonts"
SCRIPTS_DIR="$ROOT_DIR/scripts"

GIT_URL=https://raw.githubusercontent.com
FONT_REPO="$GIT_URL/googlefonts/noto-cjk/main"
FONT_URL_PATH=Sans/OTF/Japanese/NotoSansCJKjp-Regular.otf
FONT_NAME=$(basename "$FONT_URL_PATH")
FONT_PATH="$FONT_DIR/$FONT_NAME"
if [[ -f "$FONT_PATH" && "$1" != '-f' ]]; then
  exit
fi
FONT_URL=$FONT_REPO/$FONT_URL_PATH
(set -x; curl -o "$FONT_PATH" --create-dirs "$FONT_URL")

"$SCRIPTS_DIR/build-noto-cjk.sh" "$FONT_PATH"
