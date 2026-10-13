#!/bin/bash
cd "$(dirname "$0")/.."
BREW_PREFIX="$( (brew --prefix || ls -d /opt/homebrew /usr/local 2>/dev/null) 2>/dev/null | head -1)"
export PATH="$BREW_PREFIX/opt/postgresql@16/bin:$PATH"
for f in .localdev/web.pid .localdev/worker.pid; do [ -f "$f" ] && kill "$(cat "$f")" 2>/dev/null; rm -f "$f"; done
pg_ctl -D .localdev/pgdata -m fast stop
