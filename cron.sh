#!/usr/bin/env bash
set -eu
PROJECT_DIR="/home/ubuntu/myerpv2/backend"
source $PROJECT_DIR/.venv/bin/activate
python3 manage.py monthly_gst devaki
