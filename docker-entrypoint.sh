#!/bin/sh
set -eu

: "${YPBRIEF_ENV_FILE:=/app/data/key.env}"
export YPBRIEF_ENV_FILE

mkdir -p /app/data /app/exports /app/logs "$(dirname "$YPBRIEF_ENV_FILE")"

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
  echo "Created $YPBRIEF_ENV_FILE"
  echo "Initial YPBRIEF_ACCESS_PASSWORD: $password"
  echo "Bootstrapped from /app/key.env.example with Docker runtime defaults."
  echo "Save this password, then configure YouTube, LLM, proxy, and delivery settings in the Web UI."
fi

exec "$@"
