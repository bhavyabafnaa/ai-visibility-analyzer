#!/bin/sh
set -eu

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
    python -m alembic -c /app/alembic.ini upgrade head
fi

exec "$@"
