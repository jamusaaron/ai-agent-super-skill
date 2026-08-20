#!/usr/bin/env bash
# Idempotent dependency refresh for the AI Agent Super-Skill dev environment.
#
# Runs after the repository is checked out. Installs the Python dependencies used
# by the runnable examples, then compiles every example to catch syntax errors
# early. Safe to run repeatedly.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Installing Python dependencies"
python3 -m pip install --user --upgrade --quiet -r requirements.txt

echo "==> Byte-compiling examples"
python3 -m compileall -q examples

echo "==> Install complete"
