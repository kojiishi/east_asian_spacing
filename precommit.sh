#!/bin/bash
set -e

yapf -ir -vv east_asian_spacing tests
# pytest -v
tox -p
pytype east_asian_spacing
