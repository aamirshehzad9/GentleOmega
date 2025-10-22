#!/usr/bin/env bash
set -euo pipefail
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
docker compose -f "$DIR/compose.yml" build
[ "${1:-}" = "up" ] && docker compose -f "$DIR/compose.yml" up -d