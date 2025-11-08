#!/bin/bash
set -e
git stash --include-untracked
git pull --ff
chmod +x *.sh
source .venv/bin/activate
pip install -r requirements.txt 
python3 manage.py migrate
deactivate
sudo systemctl restart myerpv2-gunicorn.service