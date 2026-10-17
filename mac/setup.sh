#!/bin/bash
# First-time setup of the local preview on a Mac, after cloning the repository.
# Needs the .env file in the project folder (it is not in git). Run once: ./mac/setup.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> 1/6 Checking .env and Homebrew"
[ -f .env ] || { echo "No .env file in $(pwd). Copy it here from the old Mac, then run this again."; exit 1; }
if ! command -v brew >/dev/null 2>&1; then
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$b" ] && eval "$("$b" shellenv)"; done
fi
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is not installed. Install it with this command, then run this script again:"
  echo '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
  exit 1
fi
BREW_PREFIX="$(brew --prefix)"

echo "==> 2/6 Installing Python, PostgreSQL, Tesseract and gettext (this can take several minutes)"
brew install python@3.12 postgresql@16 tesseract tesseract-lang gettext
export PATH="$BREW_PREFIX/opt/postgresql@16/bin:$BREW_PREFIX/bin:$PATH"
export LC_ALL=C  # PostgreSQL refuses to start on some Macs without it

echo "==> 3/6 Installing the Python packages"
[ -d .venv ] || "$BREW_PREFIX/bin/python3.12" -m venv .venv
.venv/bin/pip install -q -r requirements.txt

echo "==> 4/6 Creating the local database (data in .localdev, port 5433)"
set -a; . ./.env; set +a
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is not set in .env}"
mkdir -p .localdev private_media
if [ ! -d .localdev/pgdata ]; then
  PWFILE="$(mktemp)"
  printf '%s' "$POSTGRES_PASSWORD" > "$PWFILE"
  initdb -D .localdev/pgdata -U snpnca --pwfile="$PWFILE" --auth=scram-sha-256 --locale=C -E UTF-8 >/dev/null
  rm -f "$PWFILE"
fi
pg_ctl -D .localdev/pgdata status >/dev/null 2>&1 || pg_ctl -D .localdev/pgdata -l .localdev/postgres.log -o "-p 5433 -c listen_addresses=127.0.0.1 -c unix_socket_directories=/tmp" -w start
PGPASSWORD="$POSTGRES_PASSWORD" createdb -h 127.0.0.1 -p 5433 -U snpnca snpnca 2>/dev/null || true

echo "==> 5/6 Creating the tables, translations and the Master Admin"
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py createcachetable
.venv/bin/python manage.py compilemessages --ignore=.venv >/dev/null
.venv/bin/python manage.py seed_master_admin
echo "Installing the free translator (about 1 GB, only once)..."
if .venv/bin/pip install -q -r requirements-translate.txt && .venv/bin/python manage.py install_translation_models; then
  echo "Automatic translation is ready."
else
  echo "Automatic translation could not be installed; the site works without it."
fi
pg_ctl -D .localdev/pgdata -m fast stop

echo "==> 6/6 Starting the site"
./mac/start.sh
