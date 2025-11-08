#!/usr/bin/env bash
set -eu
PROJECT_DIR="/home/ubuntu/myerpv2/backend"
cd $PROJECT_DIR
source .venv/bin/activate
systemd-run --scope -p CPUQuota=20% python3 manage.py monthly_gst devakixx
