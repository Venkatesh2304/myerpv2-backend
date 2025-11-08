#!/usr/bin/env bash
set -eu

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  echo "ERROR: must be run as root (sudo). Exiting." >&2
  exit 1
fi

PROJECT_DIR="/home/ubuntu/myerpv2/backend"
cd $PROJECT_DIR
source .venv/bin/activate
systemd-run --scope -p CPUQuota=20% python3 manage.py monthly_gst $@
