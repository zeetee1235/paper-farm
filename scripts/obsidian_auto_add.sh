#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/obsidian_auto_add.sh [--once]

Description:
  Watches the default Obsidian inbox and automatically processes incoming PDFs.
  Internally calls: scripts/agent_package_batch.sh

Options:
  --once    Run one scan/process cycle and exit.

Environment:
  LOOP_INTERVAL_SEC  Poll interval for watch mode (default: 20)

Default folders:
  inbox   = obsidian/vault/00_Inbox_PDFs
  output  = obsidian/vault/10_Papers
  archive = obsidian/vault/00_Inbox_PDFs/_processed
EOF
}

once=0
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi
if [[ "${1:-}" == "--once" ]]; then
  once=1
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
INTERVAL="${LOOP_INTERVAL_SEC:-20}"
BATCH_SCRIPT="$ROOT_DIR/scripts/agent_package_batch.sh"

if [[ ! -x "$BATCH_SCRIPT" ]]; then
  echo "ERROR: Missing executable batch script: $BATCH_SCRIPT" >&2
  exit 1
fi

run_cycle() {
  echo "[obsidian-auto-add] $(date '+%Y-%m-%d %H:%M:%S') scan start"
  "$BATCH_SCRIPT"
  echo "[obsidian-auto-add] $(date '+%Y-%m-%d %H:%M:%S') scan done"
}

if [[ "$once" -eq 1 ]]; then
  run_cycle
  exit 0
fi

echo "[obsidian-auto-add] watch mode started (interval=${INTERVAL}s)"
while true; do
  run_cycle
  sleep "$INTERVAL"
done
