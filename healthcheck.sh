#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8888}"
curl -fsS "http://127.0.0.1:${PORT}/ping" >/dev/null
