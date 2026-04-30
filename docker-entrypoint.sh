#!/bin/sh
set -eu

: "${YPBRIEF_ENV_FILE:=/app/data/key.env}"
export YPBRIEF_ENV_FILE

mkdir -p /app/data /app/exports /app/logs "$(dirname "$YPBRIEF_ENV_FILE")"

: "${YPBRIEF_LOG_FILE:=/app/logs/ypbrief.log}"
export YPBRIEF_LOG_FILE
mkdir -p "$(dirname "$YPBRIEF_LOG_FILE")"
touch "$YPBRIEF_LOG_FILE"

log_message() {
  printf '%s\n' "$*" | tee -a "$YPBRIEF_LOG_FILE"
}

if [ ! -f "$YPBRIEF_ENV_FILE" ]; then
  password="$(python - <<'PY'
import secrets
print(secrets.token_urlsafe(24))
PY
)"
  cp /app/key.env.example "$YPBRIEF_ENV_FILE"
  YPBRIEF_ENV_FILE="$YPBRIEF_ENV_FILE" YPBRIEF_ACCESS_PASSWORD="$password" python - <<'PY'
from pathlib import Path
import os

path = Path(os.environ["YPBRIEF_ENV_FILE"])
updates = {
    "YPBRIEF_ACCESS_PASSWORD": os.environ["YPBRIEF_ACCESS_PASSWORD"],
    "YPBRIEF_DB_PATH": "/app/data/ypbrief.db",
    "YPBRIEF_EXPORT_DIR": "/app/exports",
    "YPBRIEF_LOG_DIR": "/app/logs",
    "SCHEDULER_ENABLED": "true",
}
lines = path.read_text(encoding="utf-8").splitlines()
remaining = dict(updates)
output: list[str] = []
for line in lines:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in line:
        output.append(line)
        continue
    key = line.split("=", 1)[0].strip()
    if key in remaining:
        output.append(f"{key}={remaining.pop(key)}")
    else:
        output.append(line)
if remaining:
    if output and output[-1].strip():
        output.append("")
    for key, value in remaining.items():
        output.append(f"{key}={value}")
path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
PY
  log_message "Created $YPBRIEF_ENV_FILE"
  log_message "Initial YPBRIEF_ACCESS_PASSWORD: $password"
  log_message "Bootstrapped from /app/key.env.example with Docker runtime defaults."
  log_message "Save this password, then configure YouTube, LLM, proxy, and delivery settings in the Web UI."
fi

if [ "${YPBRIEF_LOG_TO_FILE:-true}" = "true" ]; then
  exec python - "$@" <<'PY'
from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import sys


command = sys.argv[1:]
if not command:
    raise SystemExit("No command provided")

log_path = Path(os.environ.get("YPBRIEF_LOG_FILE", "/app/logs/ypbrief.log"))
log_path.parent.mkdir(parents=True, exist_ok=True)

process: subprocess.Popen[str] | None = None


def forward_signal(signum, frame):
    if process is not None and process.poll() is None:
        process.send_signal(signum)


signal.signal(signal.SIGTERM, forward_signal)
signal.signal(signal.SIGINT, forward_signal)

with log_path.open("a", encoding="utf-8", errors="replace", buffering=1) as log:
    log.write("\n" + "=" * 78 + "\n")
    log.write(f"Running: {' '.join(command)}\n")
    log.write("=" * 78 + "\n")
    log.flush()
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        log.write(line)
        log.flush()
    raise SystemExit(process.wait())
PY
fi

exec "$@"
