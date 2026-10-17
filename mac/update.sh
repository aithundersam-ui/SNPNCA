#!/bin/bash
# Update the local preview to the latest version on GitHub. Keeps the database
# and uploaded files. Run: ./mac/update.sh
set -uo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || { echo "No .env file in $(pwd)."; exit 1; }
set -a; . ./.env; set +a  # the site's settings (secret key, database...)
export LC_ALL=C

echo "==> 1/5 Stopping the site"
./mac/stop.sh >/dev/null 2>&1 || true

echo "==> 2/5 Downloading the latest version"
git pull --ff-only origin main || { echo "git pull failed: see the message above."; exit 1; }

echo "==> 3/5 Updating the Python packages"
.venv/bin/pip install -q -r requirements.txt || exit 1

echo "==> 4/5 Translations and the free translator (about 1 GB the first time)"
.venv/bin/python manage.py compilemessages --ignore=.venv >/dev/null
if .venv/bin/pip install -q -r requirements-translate.txt && .venv/bin/python manage.py install_translation_models; then
  echo "Automatic translation is ready."
else
  echo "Automatic translation could not be installed; the site works without it."
fi

echo "==> 5/5 Starting the site (this also updates the database)"
./mac/start.sh
