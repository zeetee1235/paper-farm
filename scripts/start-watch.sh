#!/usr/bin/env bash
# ============================================================
# start-watch.sh
# Start the Zotero → paper-farm → Obsidian auto-watch daemon
#
# Steps:
#   1. Start ollama server if not running
#   2. Wait until ollama is ready
#   3. Pull model if missing
#   4. Start paper-farm watch
#   5. Clean shutdown on Ctrl+C
#
# Usage:
#   bash scripts/start-watch.sh
#   bash scripts/start-watch.sh --verbose
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG="$PROJECT_ROOT/paper-farm.toml"
LOG_DIR="$PROJECT_ROOT/logs"
OLLAMA_LOG="$LOG_DIR/ollama.log"
WATCH_LOG="$LOG_DIR/paper-farm.log"
VERBOSE=""
OLLAMA_PID=""

# ── argument parsing ────────────────────────────────────────
for arg in "$@"; do
  case "$arg" in
    --verbose|-v) VERBOSE="--verbose" ;;
  esac
done

# ── utility functions ───────────────────────────────────────
log()  { echo "[$(date '+%H:%M:%S')] $*"; }
info() { log "✓ $*"; }
warn() { log "⚠ $*"; }
err()  { log "✗ $*" >&2; }

# ── setup ───────────────────────────────────────────────────
mkdir -p "$LOG_DIR"

if [ ! -f "$CONFIG" ]; then
  err "Config file not found: $CONFIG"
  err "Run first: cd $PROJECT_ROOT && uv run paper-farm init-config"
  exit 1
fi

# ── shutdown handler ────────────────────────────────────────
cleanup() {
  echo ""
  log "Shutdown signal received — cleaning up..."
  if [ -n "$OLLAMA_PID" ] && kill -0 "$OLLAMA_PID" 2>/dev/null; then
    log "Stopping ollama server (PID $OLLAMA_PID)"
    kill "$OLLAMA_PID" 2>/dev/null || true
  fi
  log "paper-farm watch stopped."
  exit 0
}
trap cleanup INT TERM

# ── ollama check / start ────────────────────────────────────
OLLAMA_BIN="$(command -v ollama 2>/dev/null || echo "")"
if [ -z "$OLLAMA_BIN" ]; then
  err "ollama not found. Check your PATH."
  err "  export PATH=\"\$HOME/.local/bin:\$PATH\""
  exit 1
fi

if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
  info "ollama server already running"
else
  log "Starting ollama server... (log: $OLLAMA_LOG)"
  "$OLLAMA_BIN" serve >> "$OLLAMA_LOG" 2>&1 &
  OLLAMA_PID=$!

  READY=0
  for i in $(seq 1 20); do
    if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
      READY=1
      break
    fi
    sleep 1
  done

  if [ "$READY" -eq 0 ]; then
    err "ollama server not responding (timeout 20s)"
    err "Check log: $OLLAMA_LOG"
    exit 1
  fi
  info "ollama server ready (PID $OLLAMA_PID)"
fi

# ── model check ─────────────────────────────────────────────
MODEL=$(grep -E '^\s*model\s*=' "$CONFIG" | head -1 | sed 's/.*=\s*"\(.*\)"/\1/' || true)
if [ -n "$MODEL" ]; then
  if ! "$OLLAMA_BIN" list 2>/dev/null | grep -q "$MODEL"; then
    warn "Model '$MODEL' not found locally. Pulling..."
    "$OLLAMA_BIN" pull "$MODEL"
    info "Model downloaded: $MODEL"
  else
    info "Model ready: $MODEL"
  fi
fi

# ── start paper-farm watch ──────────────────────────────────
info "Watcher started — papers added to Zotero will be processed automatically"
info "Obsidian output: $(grep -E 'obsidian_vault' "$CONFIG" | head -1 | sed 's/.*=\s*"\(.*\)"/\1/' || echo '(check config)')"
log  "Log: $WATCH_LOG  (Ctrl+C to stop)"
echo ""

cd "$PROJECT_ROOT"
uv run paper-farm $VERBOSE watch --config "$CONFIG" 2>&1 | tee -a "$WATCH_LOG"
