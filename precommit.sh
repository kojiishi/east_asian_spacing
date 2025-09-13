#!/bin/bash
if [[ -z "$VIRTUAL_ENV" ]]; then
  echo "Activating the virtual environment and rerunning..."
  uv run "$0" "$@"
  exit $?
fi

set -e

yapf -ir -vv .
pytest -v
# tox -p

# `pytype` supports 3.8-3.12 (May 15, 2025)
# https://github.com/google/pytype/#requirements
uvx --python 3.12 --with fonttools,uharfbuzz pytype src/east_asian_spacing
