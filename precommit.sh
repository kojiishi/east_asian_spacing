#!/bin/bash
set -e

yapf -ir -vv .
pytest -v
# tox -p
pytype src/east_asian_spacing
