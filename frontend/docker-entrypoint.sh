#!/bin/sh
set -e

API_BASE_VALUE="${API_BASE:-http://localhost:8000}"

sed "s|%%API_BASE%%|${API_BASE_VALUE}|g" \
  /usr/share/nginx/html/index.html.template > /usr/share/nginx/html/index.html

exec "$@"
