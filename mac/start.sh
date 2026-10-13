#!/bin/bash
# Local preview: PostgreSQL (data in .localdev/pgdata, port 5433) + Django on http://localhost:8000 + PDF worker.
cd "$(dirname "$0")/.."
BREW_PREFIX="$( (brew --prefix || ls -d /opt/homebrew /usr/local 2>/dev/null) 2>/dev/null | head -1)"
export PATH="$BREW_PREFIX/opt/postgresql@16/bin:$BREW_PREFIX/bin:$PATH"
set -a; . ./.env; set +a
export LC_ALL=C
pg_ctl -D .localdev/pgdata status >/dev/null 2>&1 || pg_ctl -D .localdev/pgdata -l .localdev/postgres.log -o "-p 5433 -c listen_addresses=127.0.0.1 -c unix_socket_directories=/tmp" -w start
. .venv/bin/activate
python manage.py migrate --noinput && python manage.py createcachetable && python manage.py seed_master_admin || exit 1
nohup python manage.py runserver 127.0.0.1:8000 --noreload > .localdev/web.log 2>&1 &
echo $! > .localdev/web.pid
nohup python manage.py process_documents > .localdev/worker.log 2>&1 &
echo $! > .localdev/worker.pid
echo "Preview running at http://localhost:8000/fr/"
