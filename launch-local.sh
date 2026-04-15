#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/apps/backend"
FRONTEND_DIR="$ROOT_DIR/apps/frontend"
BACKEND_ENV_FILE="$BACKEND_DIR/.env"
BACKEND_ENV_TEMPLATE="$BACKEND_DIR/.env.example"

OLLAMA_MODEL="${OLLAMA_MODEL:-gemma3:4b}"
OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
FRONTEND_BASE_URL="${FRONTEND_BASE_URL:-http://localhost:${FRONTEND_PORT}}"
BACKEND_ORIGIN="${BACKEND_ORIGIN:-http://127.0.0.1:${BACKEND_PORT}}"

PIDS=()
OLLAMA_STARTED_BY_SCRIPT=0

info() {
  printf '[info] %s\n' "$1"
}

warn() {
  printf '[warn] %s\n' "$1"
}

error() {
  printf '[error] %s\n' "$1" >&2
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    error "Missing required command: $1"
    exit 1
  fi
}

append_env_if_missing() {
  local key="$1"
  local value="$2"

  if ! grep -Eq "^[# ]*${key}=" "$BACKEND_ENV_FILE"; then
    printf '\n%s=%s\n' "$key" "$value" >> "$BACKEND_ENV_FILE"
  fi
}

replace_or_append_env() {
  local key="$1"
  local value="$2"

  if grep -Eq "^[# ]*${key}=" "$BACKEND_ENV_FILE"; then
    perl -0pi -e "s@^[# ]*\\Q${key}\\E=.*\$@${key}=${value}@m" "$BACKEND_ENV_FILE"
  else
    printf '\n%s=%s\n' "$key" "$value" >> "$BACKEND_ENV_FILE"
  fi
}

cleanup() {
  local exit_code=$?

  if ((${#PIDS[@]} > 0)); then
    info "Stopping frontend and backend..."
    for pid in "${PIDS[@]}"; do
      if kill -0 "$pid" >/dev/null 2>&1; then
        kill "$pid" >/dev/null 2>&1 || true
      fi
    done
    wait "${PIDS[@]}" 2>/dev/null || true
  fi

  if [[ $OLLAMA_STARTED_BY_SCRIPT -eq 1 ]] && [[ -n "${OLLAMA_PID:-}" ]]; then
    info "Stopping Ollama service started by this script..."
    kill "$OLLAMA_PID" >/dev/null 2>&1 || true
    wait "$OLLAMA_PID" 2>/dev/null || true
  fi

  exit "$exit_code"
}

trap cleanup EXIT INT TERM

require_command ollama
require_command uv
require_command npm
require_command curl
require_command perl

if [[ ! -f "$BACKEND_ENV_FILE" ]]; then
  info "Creating backend .env from template..."
  cp "$BACKEND_ENV_TEMPLATE" "$BACKEND_ENV_FILE"
fi

replace_or_append_env "LLM_PROVIDER" "ollama"
replace_or_append_env "LLM_MODEL" "$OLLAMA_MODEL"
replace_or_append_env "LLM_API_BASE" "$OLLAMA_HOST"
replace_or_append_env "HOST" "$BACKEND_HOST"
replace_or_append_env "PORT" "$BACKEND_PORT"
replace_or_append_env "FRONTEND_BASE_URL" "$FRONTEND_BASE_URL"
append_env_if_missing "CORS_ORIGINS" "[\"http://localhost:${FRONTEND_PORT}\",\"http://127.0.0.1:${FRONTEND_PORT}\"]"

if curl -fsS "$OLLAMA_HOST/api/tags" >/dev/null 2>&1; then
  info "Ollama is already running."
else
  info "Starting Ollama service..."
  ollama serve >/tmp/resume-matcher-ollama.log 2>&1 &
  OLLAMA_PID=$!
  OLLAMA_STARTED_BY_SCRIPT=1

  for _ in {1..30}; do
    if curl -fsS "$OLLAMA_HOST/api/tags" >/dev/null 2>&1; then
      info "Ollama is ready."
      break
    fi
    sleep 1
  done

  if ! curl -fsS "$OLLAMA_HOST/api/tags" >/dev/null 2>&1; then
    error "Ollama did not become ready. Check /tmp/resume-matcher-ollama.log"
    exit 1
  fi
fi

info "Ensuring Ollama model '$OLLAMA_MODEL' is available..."
ollama list | awk 'NR > 1 {print $1}' | grep -Fx "$OLLAMA_MODEL" >/dev/null 2>&1 || ollama pull "$OLLAMA_MODEL"

if [[ ! -d "$BACKEND_DIR/.venv" ]]; then
  info "Installing backend dependencies with uv..."
  (cd "$BACKEND_DIR" && uv sync)
fi

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  info "Installing frontend dependencies with npm..."
  (cd "$FRONTEND_DIR" && npm install)
fi

info "Starting backend on port $BACKEND_PORT..."
(
  cd "$BACKEND_DIR"
  uv run uvicorn app.main:app --reload --host "$BACKEND_HOST" --port "$BACKEND_PORT"
) &
BACKEND_PID=$!
PIDS+=("$BACKEND_PID")

info "Waiting for backend health check..."
for _ in {1..30}; do
  if curl -fsS "$BACKEND_ORIGIN/api/v1/health" >/dev/null 2>&1; then
    info "Backend is ready."
    break
  fi
  if ! kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    error "Backend exited during startup."
    exit 1
  fi
  sleep 1
done

if ! curl -fsS "$BACKEND_ORIGIN/api/v1/health" >/dev/null 2>&1; then
  error "Backend did not become ready on $BACKEND_ORIGIN."
  exit 1
fi

info "Starting frontend on port $FRONTEND_PORT..."
(
  cd "$FRONTEND_DIR"
  BACKEND_ORIGIN="$BACKEND_ORIGIN" npm run dev -- --port "$FRONTEND_PORT"
) &
FRONTEND_PID=$!
PIDS+=("$FRONTEND_PID")

cat <<EOF

Resume Matcher is launching:
  Frontend: $FRONTEND_BASE_URL
  Backend:  $BACKEND_ORIGIN
  Ollama:   $OLLAMA_HOST
  Model:    $OLLAMA_MODEL

Press Ctrl+C to stop everything.
EOF

wait "${PIDS[@]}"
