#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/agent_package_batch.sh [<pdf_or_dir> ...]

Description:
  For each PDF, run:
    ingest -> extract -> normalize -> summarize --mode agent-pr
  Then print the paper_id and generated agent.md path.
  If no argument is given, process PDFs under PDF_INBOX_DIR.

  It also syncs files for Obsidian:
    <OBSIDIAN_SYNC_DIR>/<paper_id>/
      - paper.pdf
      - note.agent.md (if exists)
      - agent.md
      - metadata.json

Environment:
  PFM_PYTHON             Python executable (default: .venv/bin/python if exists, else python3)
  PDF_INBOX_DIR          Default input folder when no args (default: obsidian/vault/00_Inbox_PDFs)
  OBSIDIAN_SYNC_DIR      Obsidian sync target directory (default: obsidian/vault/10_Papers)
  PDF_ARCHIVE_DIR        Processed PDF archive folder (default: obsidian/vault/00_Inbox_PDFs/_processed)
  ARCHIVE_PROCESSED      Move processed PDFs to archive in no-arg mode (default: 1)
  DOCSTRUCT_DPI          Passed through to pipeline (optional)
  DOCSTRUCT_TIMEOUT_SEC  Passed through to pipeline (optional)

Examples:
  scripts/agent_package_batch.sh
  scripts/agent_package_batch.sh test.pdf
  scripts/agent_package_batch.sh /papers/dir1 /papers/dir2/file.pdf
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PDF_INBOX_DIR="${PDF_INBOX_DIR:-$ROOT_DIR/obsidian/vault/00_Inbox_PDFs}"
OBSIDIAN_SYNC_DIR="${OBSIDIAN_SYNC_DIR:-$ROOT_DIR/obsidian/vault/10_Papers}"
PDF_ARCHIVE_DIR="${PDF_ARCHIVE_DIR:-$ROOT_DIR/obsidian/vault/00_Inbox_PDFs/_processed}"
ARCHIVE_PROCESSED="${ARCHIVE_PROCESSED:-1}"

if [[ -n "${PFM_PYTHON:-}" ]]; then
  PYTHON_BIN="$PFM_PYTHON"
elif [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
else
  PYTHON_BIN="python3"
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "ERROR: Python executable not found: $PYTHON_BIN" >&2
  exit 1
fi

declare -a PDFS=()
using_default_inbox=0
if [[ "$#" -eq 0 ]]; then
  using_default_inbox=1
  if [[ ! -d "$PDF_INBOX_DIR" ]]; then
    echo "ERROR: PDF inbox directory does not exist: $PDF_INBOX_DIR" >&2
    exit 1
  fi
  while IFS= read -r file; do
    PDFS+=("$file")
  done < <(find "$PDF_INBOX_DIR" -type f \( -iname "*.pdf" \) | sort)
else
  for input in "$@"; do
    if [[ -d "$input" ]]; then
      while IFS= read -r file; do
        PDFS+=("$file")
      done < <(find "$input" -type f \( -iname "*.pdf" \) | sort)
    elif [[ -f "$input" ]]; then
      PDFS+=("$input")
    else
      echo "WARN: Skipping missing path: $input" >&2
    fi
  done
fi

if [[ "${#PDFS[@]}" -eq 0 ]]; then
  echo "INFO: No PDF files found."
  exit 0
fi

cd "$ROOT_DIR"
mkdir -p "$OBSIDIAN_SYNC_DIR"
if [[ "$using_default_inbox" -eq 1 && "$ARCHIVE_PROCESSED" == "1" ]]; then
  mkdir -p "$PDF_ARCHIVE_DIR"
fi

echo "python=$PYTHON_BIN"
echo "inbox=$PDF_INBOX_DIR"
echo "obsidian_sync=$OBSIDIAN_SYNC_DIR"
if [[ "$using_default_inbox" -eq 1 ]]; then
  echo "archive=$PDF_ARCHIVE_DIR"
fi
echo "count=${#PDFS[@]}"
echo

for pdf in "${PDFS[@]}"; do
  echo "==> Processing: $pdf"

  paper_id="$("$PYTHON_BIN" -m paper_farm.cli ingest "$pdf" | tail -n 1)"
  paper_dir="$ROOT_DIR/data/papers/$paper_id"
  agent_pkg_dir="$paper_dir/agent_package"
  agent_md="$agent_pkg_dir/agent.md"
  extracted_json="$paper_dir/extracted.json"
  cleaned_json="$paper_dir/cleaned.json"

  if [[ -f "$extracted_json" && -f "$cleaned_json" && -f "$agent_md" ]]; then
    echo "reuse=1 (existing artifacts)"
  else
    "$PYTHON_BIN" -m paper_farm.cli extract "$paper_id" >/dev/null
    "$PYTHON_BIN" -m paper_farm.cli normalize "$paper_id" >/dev/null
    "$PYTHON_BIN" -m paper_farm.cli summarize "$paper_id" --mode agent-pr >/dev/null
  fi

  if [[ ! -f "$agent_md" ]]; then
    echo "ERROR: agent.md not found for paper_id=$paper_id" >&2
    exit 1
  fi

  # Sync files for Obsidian usage.
  obsidian_paper_dir="$OBSIDIAN_SYNC_DIR/$paper_id"
  mkdir -p "$obsidian_paper_dir"
  cp -f "$paper_dir/original.pdf" "$obsidian_paper_dir/paper.pdf"
  cp -f "$paper_dir/metadata.json" "$obsidian_paper_dir/metadata.json"
  cp -f "$agent_md" "$obsidian_paper_dir/agent.md"
  if [[ -f "$agent_pkg_dir/note.agent.md" ]]; then
    cp -f "$agent_pkg_dir/note.agent.md" "$obsidian_paper_dir/note.agent.md"
  fi

  echo "paper_id=$paper_id"
  echo "agent_md=$agent_md"
  echo "obsidian_dir=$obsidian_paper_dir"

  if [[ "$using_default_inbox" -eq 1 && "$ARCHIVE_PROCESSED" == "1" ]]; then
    src_abs="$(cd -- "$(dirname -- "$pdf")" && pwd)/$(basename -- "$pdf")"
    archive_abs="$(cd -- "$(dirname -- "$PDF_ARCHIVE_DIR")" && pwd)/$(basename -- "$PDF_ARCHIVE_DIR")"
    if [[ "$src_abs" != "$archive_abs/"* ]]; then
      archived_pdf="$PDF_ARCHIVE_DIR/${paper_id}__$(basename -- "$pdf")"
      mv -f "$pdf" "$archived_pdf"
      echo "archived_pdf=$archived_pdf"
    fi
  fi
  echo
done
