#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME="myerpv2" # For the service name

# Remote SSH config
REMOTE_HOST="ubuntu@43.205.224.85"
SSH_KEY="/home/venkatesh/Downloads/aws/LightsailDefaultKey-ap-south-1.pem"
REMOTE_BACKEND_DIR="/home/ubuntu/myerpv2/backend"

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"   # backend/
VENV_DIR="$PROJECT_DIR/.venv"
SERVICE_NAME="$PROJECT_NAME-gunicorn.service"

echo "==> Checking git status (must be clean)"
if [ -n "$(git status --porcelain)" ]; then
  echo "Uncommitted/untracked changes present. Commit/stash before deploying."
  exit 1
fi

source "$VENV_DIR/bin/activate"
echo "==> Freezing venv to requirements.txt"
pip freeze > requirements.txt
git add requirements.txt 
git commit -m "Update requirements.txt" || true

echo "==> Pushing to remote"
git push origin main -f

echo "==> SSH to server"
ssh -i "$SSH_KEY" "$REMOTE_HOST" bash <<EOF
  set -eu
  cd "$REMOTE_BACKEND_DIR"
  echo "[Remote] Running sync.sh..."
  bash sync.sh
EOF

echo "==> ✅ Remote sync completed successfully"