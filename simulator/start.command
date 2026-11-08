#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo 'First follow simulator/README.md to create .venv and install requirements.lock.'
  exit 1
fi
export PYTHONPATH="$PWD/src"
exec .venv/bin/python -m belleq_sim serve --port 8010
