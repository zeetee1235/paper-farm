#!/usr/bin/env bash
# ============================================================
# sync.sh
# One-shot scan: run pipeline only for unprocessed papers
#
# Skip criteria (both must be true to skip):
#   1. PDF path exists in .zotero_watcher_state.json
#   2. Obsidian summary.md actually exists for that paper_id
#
# If summary.md is missing, the paper is re-processed even if
# it appears in the state file.
#
# Usage:
#   bash scripts/sync.sh              # use default config
#   bash scripts/sync.sh --verbose    # verbose logging
#   bash scripts/sync.sh --dry-run    # list pending papers only (no run)
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG="$PROJECT_ROOT/paper-farm.toml"
VERBOSE=""
DRY_RUN=0

# ── argument parsing ────────────────────────────────────────
for arg in "$@"; do
  case "$arg" in
    --verbose|-v) VERBOSE="--verbose" ;;
    --dry-run|-n) DRY_RUN=1 ;;
    --config=*) CONFIG="${arg#--config=}" ;;
  esac
done

# ── utility functions ───────────────────────────────────────
log()  { echo "[$(date '+%H:%M:%S')] $*"; }
info() { log "✓ $*"; }
warn() { log "⚠ $*"; }
err()  { log "✗ $*" >&2; }

# ── config check ────────────────────────────────────────────
if [ ! -f "$CONFIG" ]; then
  err "Config file not found: $CONFIG"
  exit 1
fi

ZOTERO_STORAGE=$(grep -E '^\s*zotero_storage\s*=' "$CONFIG" \
  | head -1 | sed 's/.*=\s*"\(.*\)"/\1/' | sed "s|~|$HOME|g" || true)
OBSIDIAN_VAULT=$(grep -E '^\s*obsidian_vault\s*=' "$CONFIG" \
  | head -1 | sed 's/.*=\s*"\(.*\)"/\1/' | sed "s|~|$HOME|g" || true)
STATE_FILE="$PROJECT_ROOT/.zotero_watcher_state.json"

log "Zotero storage : ${ZOTERO_STORAGE:-'(could not read from config)'}"
log "Obsidian vault : ${OBSIDIAN_VAULT:-'(could not read from config)'}"

if [ ! -d "${ZOTERO_STORAGE:-}" ]; then
  warn "Zotero storage folder not found — launch Zotero once to create it."
fi

# ── dry-run: list pending papers ────────────────────────────
if [ "$DRY_RUN" -eq 1 ]; then
  log "[dry-run] Pending PDFs:"
  COUNT=0
  while IFS= read -r -d '' pdf; do
    pdf_str="$pdf"
    if [ -f "$STATE_FILE" ] && python3 -c "
import json, sys
state = json.load(open('$STATE_FILE')).get('processed', {})
pdf = '$pdf_str'
paper_id = state.get(pdf) if isinstance(state, dict) else None
if paper_id:
    import pathlib
    summary = pathlib.Path('${OBSIDIAN_VAULT:-/nonexistent}') / paper_id / 'summary.md'
    if summary.exists():
        sys.exit(0)   # done → skip
sys.exit(1)           # not done → process
" 2>/dev/null; then
      : # skip
    else
      echo "  → $pdf"
      COUNT=$((COUNT + 1))
    fi
  done < <(find "${ZOTERO_STORAGE:-/nonexistent}" -name "*.pdf" -print0 2>/dev/null | sort -z)
  log "Pending: ${COUNT} paper(s)"
  exit 0
fi

# ── ollama check ─────────────────────────────────────────────
BACKEND=$(grep -E '^\s*backend\s*=' "$CONFIG" | head -1 | sed 's/.*=\s*"\(.*\)"/\1/' || true)
if [ "${BACKEND:-}" = "ollama" ]; then
  if ! curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
    err "ollama server is not running."
    err "Start it with: ollama serve"
    err "Or use start-watch.sh which starts it automatically."
    exit 1
  fi
  info "ollama server confirmed"
fi

# ── run ──────────────────────────────────────────────────────
log "Scanning for unprocessed papers..."
cd "$PROJECT_ROOT"
RESULT=$(uv run paper-farm $VERBOSE watch --config "$CONFIG" --once 2>&1)
echo "$RESULT"

COUNT=$(echo "$RESULT" | python3 -c "
import sys, json
try:
    lines = sys.stdin.read().strip()
    for line in lines.splitlines():
        line = line.strip()
        if line.startswith('['):
            ids = json.loads(line)
            print(len(ids))
            sys.exit(0)
    print(0)
except Exception:
    print(0)
" 2>/dev/null || echo "0")

echo ""
if [ "$COUNT" -gt 0 ]; then
  info "Done: ${COUNT} paper(s) saved to Obsidian."
else
  info "Nothing to process — all papers already completed."
fi
