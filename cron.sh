#!/usr/bin/env bash
set -eu
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
source $PROJECT_DIR/.venv/bin/activate
python3 manage.py monthly_gst devaki
