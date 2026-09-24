#!/usr/bin/env bash

set -e
set -x

FASTAPI_ENV=development python scripts/init_test_db.py
FASTAPI_ENV=development coverage run -m pytest tests/
coverage report
coverage html --title "${@-coverage}"
