#!/usr/bin/env bash
set -eu
git pull -ff

PYTHON="python3.10"
PROJECT_NAME="myerpv2" #For the service name
DB_NAME="myerpv2all"


PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
SERVICE_NAME="$PROJECT_NAME-gunicorn.service"
SERVICE_PATH="/etc/systemd/system/$SERVICE_NAME"

#Cron job details
JOB_TAG="monthly_gst"
CRON_SCHEDULE="0 23 3 * *" # At 23:00 on day-of-month 3
CRON_CMD="$PROJECT_DIR/cron.sh devaki > $PROJECT_DIR/cron.log 2>&1"

echo "==> Checking for $PYTHON"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "Error: $PYTHON not found. Install Python 3.10 and re-run."
  exit 1
fi

echo "==> Creating virtual environment ($VENV_DIR) if missing"
if [ ! -d "$VENV_DIR" ]; then
  if ! "$PYTHON" -m venv "$VENV_DIR" 2>/dev/null; then
    echo "python3.10 venv module not available. Attempting to install..."
    if command -v apt-get >/dev/null 2>&1; then
      sudo apt-get update -y
      sudo apt-get install -y python3.10-venv
      "$PYTHON" -m venv "$VENV_DIR" || true
    fi
  fi
  if [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "Falling back to virtualenv..."
    "$PYTHON" -m pip install --user --upgrade pip virtualenv
    VENV_BIN="${HOME}/.local/bin/virtualenv"
    if [ ! -x "$VENV_BIN" ]; then
      VENV_BIN="$(command -v virtualenv || true)"
    fi
    if [ -z "${VENV_BIN:-}" ]; then
      echo "Error: virtualenv not found and venv failed. Install one of them and retry."
      exit 1
    fi
    "$VENV_BIN" -p "$PYTHON" "$VENV_DIR"
  fi
else
  echo "Virtualenv exists, skipping creation."
fi

echo "==> Activating virtual environment"
source $VENV_DIR/bin/activate

echo "==> Upgrading pip/setuptools/wheel"
python -m pip install --upgrade pip setuptools wheel

echo "==> Installing requirements.txt"
if [ -f "$PROJECT_DIR/requirements.txt" ]; then
  if ! pip install -r "$PROJECT_DIR/requirements.txt"; then
    echo "Error: requirements installation failed."
    exit 1
  fi
else
  echo "Warning: requirements.txt not found. Skipping."
fi

echo "==> Ensuring gunicorn is installed"
pip install gunicorn

echo "==> Ensuring PostgreSQL database '$DB_NAME' exists"
if ! command -v psql >/dev/null 2>&1; then
  echo "Error: psql not found. Install PostgreSQL client tools and retry."
  exit 1
fi
export PGPASSWORD="Ven2004"
DB_EXISTS="$(psql -h localhost -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" || echo "")"
IS_NEW_DB=0
if [ "$DB_EXISTS" != "1" ]; then
  echo "Creating database $DB_NAME..."
  psql -h localhost -U postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE $DB_NAME"
  IS_NEW_DB=1
else
  echo "Database already exists. Skipping creation."
fi

#SET DATESTYLE
psql -h localhost -U postgres -v ON_ERROR_STOP=1 -c "ALTER DATABASE $DB_NAME SET datestyle TO 'ISO, DMY'"

chmod +x *.sh
#Add monthly cron job
echo "==> Setting up cron job :($JOB_TAG)"
(sudo crontab -l 2>/dev/null | grep -v "$JOB_TAG"; echo "$CRON_SCHEDULE $CRON_CMD # $JOB_TAG") | sudo crontab -

# Django migrations
echo "==> Applying Django migrations"
python manage.py migrate --noinput

export DJANGO_SUPERUSER_PASSWORD=1
python3 manage.py createsuperuser \
  --noinput \
  --username admin \
  --email "venkateshks2304@gmail.com" \
  || echo "Superuser already exists or creation failed, continuing..."

if [ "$IS_NEW_DB" == "1" ]; then
  echo "Dumping initial data into $DB_NAME..."
  psql -h localhost -U postgres -d "$DB_NAME" -f "dump.sql"
fi
unset PGPASSWORD

echo "==> Creating or updating systemd service ($SERVICE_NAME)"
sudo bash -c "cat > '$SERVICE_PATH'" <<EOF
[Unit]
Description=Gunicorn for $PROJECT_NAME Django project
After=network.target

[Service]
Type=simple
User=$(whoami)
Group=$(id -gn)
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$VENV_DIR/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin
ExecStart=$VENV_DIR/bin/gunicorn -c gunicorn.py
Restart=on-failure
KillSignal=SIGQUIT
TimeoutStopSec=5
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

echo "==> Reloading and restarting systemd service"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo "==> Setup complete."
sudo systemctl status "$SERVICE_NAME" --no-pager || true
