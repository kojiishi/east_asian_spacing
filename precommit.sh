#!/bin/bash
set -e

yapf -ir -vv east_asian_spacing tests "$@"
pytest
pytype east_asian_spacing
