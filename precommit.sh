#!/bin/bash
set -e

yapf -ir -vv .
pytest -v
# tox -p
pytype east_asian_spacing
