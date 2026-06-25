#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8888}"
XTTS_PORT="${XTTS_PORT:-8889}"
XTTS_DIR="${XTTS_DIR:-auto}"
LOG_DIR="${LOG_DIR:-auto}"

if [ "${XTTS_DIR}" = "auto" ]; then
  if [ -d /runpod-volume/skyrimnet-tts ]; then
    XTTS_DIR="/runpod-volume/skyrimnet-tts"
  elif [ -d /workspace/skyrimnet-tts ]; then
    XTTS_DIR="/workspace/skyrimnet-tts"
  else
    XTTS_DIR="/runpod-volume/skyrimnet-tts"
  fi
fi

if [ "${LOG_DIR}" = "auto" ]; then
  if [ -d /runpod-volume ]; then
    LOG_DIR="/runpod-volume/logs"
  else
    LOG_DIR="/workspace/logs"
  fi
fi

PYTHON_BIN="${XTTS_DIR}/.venv/bin/python"

echo "[start] SkyrimNet XTTS worker"
echo "[start] PORT=${PORT}"
echo "[start] XTTS_PORT=${XTTS_PORT}"
echo "[start] XTTS_DIR=${XTTS_DIR}"
echo "[start] LOG_DIR=${LOG_DIR}"

mkdir -p "${LOG_DIR}"

if [ ! -d /runpod-volume ] && [ ! -d /workspace ]; then
  echo "[error] No RunPod volume mount found." >&2
  echo "[error] Serverless Network Volumes usually mount at /runpod-volume." >&2
  echo "[error] Pods usually mount Network Volumes at /workspace." >&2
  exit 20
fi

if [ ! -d "${XTTS_DIR}" ]; then
  echo "[error] ${XTTS_DIR} not found." >&2
  echo "[error] Attach the correct Network Volume: unique_silver_turkey_volume in EU-RO-1." >&2
  echo "[debug] /runpod-volume contents:" >&2
  ls -la /runpod-volume >&2 || true
  echo "[debug] /workspace contents:" >&2
  ls -la /workspace >&2 || true
  exit 21
fi

if [ ! -x "${PYTHON_BIN}" ]; then
  echo "[error] ${PYTHON_BIN} not found or not executable." >&2
  echo "[error] The XTTS virtualenv is missing on the mounted volume." >&2
  exit 22
fi

echo "[start] Stopping Jupyter if it owns port ${PORT}..."
pkill -f "jupyter-lab.*--port=${PORT}" 2>/dev/null || true
pkill -f "jupyter.*--port=${PORT}" 2>/dev/null || true

if command -v ss >/dev/null 2>&1; then
  owner="$(ss -ltnp 2>/dev/null | grep ":${PORT} " || true)"
  if [ -n "${owner}" ]; then
    echo "[warn] Port ${PORT} is already in use before XTTS start:"
    echo "${owner}"
  fi
fi

cd "${XTTS_DIR}"
echo "[start] Launching SkyrimNet XTTS..."
"${PYTHON_BIN}" -u -m skyrimnet-xtts --server 127.0.0.1 --port "${XTTS_PORT}" &
xtts_pid="$!"

cleanup() {
  kill "${xtts_pid}" 2>/dev/null || true
}
trap cleanup EXIT

echo "[start] Launching RunPod load balancer proxy..."
export PROXY_PORT="${PORT}"
export PROXY_TARGET="http://127.0.0.1:${XTTS_PORT}"
exec "${PYTHON_BIN}" -u /app/proxy_server.py
