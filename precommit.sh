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
pytype src/east_asian_spacing
