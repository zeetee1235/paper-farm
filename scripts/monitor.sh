#!/usr/bin/env bash
# ============================================================
# monitor.sh  —  paper-farm pipeline live monitor
#
# Usage:
#   bash scripts/monitor.sh         # live (default 5s refresh)
#   bash scripts/monitor.sh 10      # refresh every 10s
#   bash scripts/monitor.sh --once  # print once and exit
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$(dirname "$SCRIPT_DIR")" && pwd)"

LIVE=1
INTERVAL=5

for arg in "$@"; do
  case "$arg" in
    --once|-1) LIVE=0 ;;
    [0-9]*) INTERVAL="$arg" ;;
  esac
done

# ── Python 렌더러 (unicode 너비 정확 계산) ─────────────────
render() {
  python3 - "$PROJECT_ROOT" "$INTERVAL" "$LIVE" <<'PYEOF'
import sys, json, datetime, pathlib, subprocess, unicodedata, urllib.request, re, tomllib

PROJECT_ROOT = pathlib.Path(sys.argv[1])
INTERVAL     = int(sys.argv[2])
LIVE         = sys.argv[3] == "1"
CONFIG            = PROJECT_ROOT / "paper-farm.toml"
STATE_FILE        = PROJECT_ROOT / ".zotero_watcher_state.json"
QUEUE_STATUS_FILE = PROJECT_ROOT / ".queue_status.json"
WATCH_LOG         = PROJECT_ROOT / "logs" / "paper-farm.log"

W = 70   # 내부 표시 너비 (보이는 컬럼 수)

# ── ANSI 색상 ───────────────────────────────────────────────
R   = "\033[0m"
B   = "\033[1m"
DIM = "\033[2m"
GRN = "\033[32m"
RED = "\033[31m"
YLW = "\033[33m"
CYN = "\033[36m"
MGN = "\033[35m"

def vlen(s: str) -> int:
    """Visible column width: strip ANSI, count CJK as 2."""
    s = re.sub(r"\033\[[0-9;]*m", "", s)
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)

def pad(s: str, width: int) -> str:
    p = width - vlen(s)
    return s + " " * max(p, 0)

def row(content: str) -> str:
    return f"{B}║{R}{pad(content, W)}{B}║{R}"

def divrow(label: str) -> str:
    """Thin divider row inside a section."""
    inner = f" {DIM}{'─' * (W - 2)}{R}"
    return f"{B}║{R}{pad(inner, W)}{B}║{R}"

def sep(left="╠", mid="═", right="╣") -> str:
    return f"{B}{left}{mid * W}{right}{R}"

config_data: dict = {}
if CONFIG.exists():
    try:
        config_data = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:
        config_data = {}

def read_config(section: str, key: str, default=""):
    value = config_data.get(section, {}).get(key, default)
    if isinstance(value, str) and value.startswith("~"):
        return str(pathlib.Path(value).expanduser())
    return value

# ── 경로 ────────────────────────────────────────────────────
configured_root = read_config("paths", "project_root", str(PROJECT_ROOT))
PROJECT_ROOT = pathlib.Path(configured_root).expanduser()
CONFIG            = PROJECT_ROOT / "paper-farm.toml"
STATE_FILE        = PROJECT_ROOT / ".zotero_watcher_state.json"
QUEUE_STATUS_FILE = PROJECT_ROOT / ".queue_status.json"
WATCH_LOG         = PROJECT_ROOT / "logs" / "paper-farm.log"

zotero_storage  = pathlib.Path(read_config("watcher", "zotero_storage", "~/Zotero/storage"))
obsidian_vault  = pathlib.Path(read_config("paths", "obsidian_vault",
    str(PROJECT_ROOT / "obsidian" / "vault" / "papers")))
backend = read_config("llm", "backend", "rule-based")
model   = read_config("llm", "model", "llama3:8b")
base_url = read_config("llm", "base_url", "http://localhost:11434")

raw_pdf_root  = PROJECT_ROOT / "data" / "raw_pdf"
parsed_root   = PROJECT_ROOT / "data" / "parsed"
summary_root  = PROJECT_ROOT / "data" / "summary"
legacy_raw_pdf_root = PROJECT_ROOT / "papers" / "raw_pdf"
legacy_parsed_root  = PROJECT_ROOT / "parsed" / "paper_struct"
legacy_summary_root = PROJECT_ROOT / "summary"

# ── 시스템 상태 ──────────────────────────────────────────────
ollama_ok = False
ollama_models = ""
try:
    with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=1) as r:
        d = json.loads(r.read())
        ollama_models = ", ".join(m["name"] for m in d.get("models", []))
        ollama_ok = True
except Exception:
    pass

watch_pid = ""
try:
    out = subprocess.check_output(["pgrep", "-f", "paper-farm.*watch"], text=True).strip()
    watch_pid = out.splitlines()[0] if out else ""
except Exception:
    pass

# ── pipeline stages ──────────────────────────────────────────
#  state: { zotero_pdf_path: paper_id | None }
#  stages: ingest → parse → summarize → obsidian

STAGES = [
    ("I", "ingest",    "ingest"),
    ("P", "parse",     "parse"),
    ("S", "summarize", "summarize"),
    ("O", "obsidian",  "export"),
]

def stage_done(paper_id: str, stage: str) -> bool:
    if stage == "ingest":
        return (
            (raw_pdf_root / f"{paper_id}.pdf").exists()
            or (legacy_raw_pdf_root / f"{paper_id}.pdf").exists()
        )
    if stage == "parse":
        return (
            (parsed_root / f"{paper_id}.json").exists()
            or (legacy_parsed_root / f"{paper_id}.json").exists()
        )
    if stage == "summarize":
        return (
            (summary_root / f"{paper_id}.json").exists()
            or (legacy_summary_root / f"{paper_id}.json").exists()
        )
    if stage == "obsidian":
        return (obsidian_vault / paper_id / "summary.md").exists()
    return False

def current_stage_label(paper_id: str) -> str:
    for _, key, label in STAGES:
        if not stage_done(paper_id, key):
            return label
    return "done"

def stage_bar(paper_id: str) -> str:
    parts = []
    all_done = True
    for sym, key, _ in STAGES:
        done = stage_done(paper_id, key)
        if done:
            parts.append(f"{GRN}{B}{sym}{R}")
        else:
            parts.append(f"{DIM}·{R}")
            all_done = False
    color = GRN if all_done else YLW
    return f"{color}[{R}" + " ".join(parts) + f"{color}]{R}"

# queue status file
queue_status = {"processing": None, "pending": [], "queue_size": 0, "failed": [], "completed_session": 0}
if QUEUE_STATUS_FILE.exists():
    try:
        queue_status = json.loads(QUEUE_STATUS_FILE.read_text())
    except Exception:
        pass

processing_name = queue_status.get("processing")
pending_names   = set(queue_status.get("pending", []))
failed_names    = set(queue_status.get("failed", []))
completed_sess  = queue_status.get("completed_session", 0)
queue_size      = queue_status.get("queue_size", 0)

# state file
papers: list[dict] = []
if STATE_FILE.exists():
    try:
        data = json.loads(STATE_FILE.read_text())
        processed = data.get("processed", {})
        for pdf_path, paper_id in processed.items():
            filename = pathlib.Path(pdf_path).name
            short = filename[:45] + "…" if len(filename) > 46 else filename
            papers.append({
                "zotero_pdf": pdf_path,
                "paper_id":   paper_id,
                "filename":   short,
                "raw_name":   filename,
            })
    except Exception:
        pass

# stats
total_tracked = len(papers)
ingested   = sum(1 for p in papers if p["paper_id"] and stage_done(p["paper_id"], "ingest"))
parsed     = sum(1 for p in papers if p["paper_id"] and stage_done(p["paper_id"], "parse"))
summarized = sum(1 for p in papers if p["paper_id"] and stage_done(p["paper_id"], "summarize"))
completed  = sum(1 for p in papers if p["paper_id"] and stage_done(p["paper_id"], "obsidian"))

total_zotero = 0
if zotero_storage.is_dir():
    total_zotero = sum(1 for _ in zotero_storage.rglob("*.pdf"))

log_lines: list[str] = []
if WATCH_LOG.exists():
    all_log_lines = WATCH_LOG.read_text(errors="replace").splitlines()[-200:]
    important = [
        line for line in all_log_lines
        if (
            "ERROR" in line
            or "Traceback" in line
            or "Exception" in line
            or "failed" in line.lower()
            or "timeout" in line.lower()
        )
    ]
    log_lines = (important or all_log_lines)[-8:]

queue_age = None
if QUEUE_STATUS_FILE.exists():
    try:
        queue_age = max(0, int(datetime.datetime.now().timestamp() - QUEUE_STATUS_FILE.stat().st_mtime))
    except Exception:
        queue_age = None

# ── output ───────────────────────────────────────────────────
now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

print()
print(sep("╔", "═", "╗"))
print(row(f"{B}{CYN}  paper-farm monitor{R}   {DIM}{now}{R}"))
print(sep())

# system status
print(row(f"  {B}[ System ]{R}"))
if ollama_ok:
    s = f"{GRN}✓ running{R}"
    e = f"  {DIM}{ollama_models}{R}" if ollama_models else ""
else:
    s = f"{RED}✗ stopped{R}"
    e = f"  {DIM}run: ollama serve{R}"
print(row(f"  ollama server  : {s}{e}"))

if watch_pid:
    s = f"{GRN}✓ running{R}";  e = f"  {DIM}PID {watch_pid}{R}"
else:
    s = f"{YLW}⚠ stopped{R}";  e = f"  {DIM}run: start-watch.sh{R}"
print(row(f"  watch process  : {s}{e}"))

llm_str = f"{DIM}{backend}{R}"
if backend == "ollama":
    llm_str += f"  {DIM}({model}){R}"
print(row(f"  LLM            : {llm_str}"))

print(sep())

# progress
print(row(f"  {B}[ Progress ]{R}"))
bar_w = 20
def stat_bar(n, total, color):
    if total == 0: return f"{DIM}{'─'*bar_w}{R}"
    filled = round(n / total * bar_w)
    return f"{color}{'█'*filled}{R}{DIM}{'░'*(bar_w-filled)}{R}"

print(row(f"  Zotero total    : {B}{total_zotero}{R}  ({total_tracked} tracked)"))
print(row(f"  ingest          : {stat_bar(ingested,   total_tracked, GRN)}  {GRN}{ingested}{R}/{total_tracked}"))
print(row(f"  parse           : {stat_bar(parsed,     total_tracked, CYN)}  {CYN}{parsed}{R}/{total_tracked}"))
print(row(f"  summarize       : {stat_bar(summarized, total_tracked, YLW)}  {YLW}{summarized}{R}/{total_tracked}"))
print(row(f"  obsidian        : {stat_bar(completed,  total_tracked, MGN)}  {MGN}{completed}{R}/{total_tracked}"))

if processing_name or queue_size > 0:
    proc_str = f"  {YLW}⟳ processing{R}" if processing_name else ""
    wait_str = f"  {DIM}queued: {queue_size}{R}" if queue_size > 0 else ""
    done_str = f"  {GRN}session done: {completed_sess}{R}" if completed_sess > 0 else ""
    print(row(f"  queue           :{proc_str}{wait_str}{done_str}"))
elif queue_age is not None:
    freshness = f"{GRN}fresh{R}" if queue_age <= INTERVAL * 3 else f"{YLW}stale{R}"
    print(row(f"  queue status    : {freshness}  {DIM}{queue_age}s ago{R}"))

print(sep())

# per-paper pipeline detail
print(row(f"  {B}[ Pipeline ]{R}   {DIM}[I]=ingest  [P]=parse  [S]=summarize  [O]=obsidian{R}"))
print(divrow(""))

if papers:
    def sort_key(p):
        raw_name = p.get("raw_name", "")
        if raw_name == processing_name:
            return (-2, 0, p["filename"])
        if raw_name in failed_names:
            return (-1, 0, p["filename"])
        if not p["paper_id"]:
            return (2, "")
        done_count = sum(stage_done(p["paper_id"], k) for _, k, _ in STAGES)
        return (0 if done_count == 4 else 1, -done_count, p["filename"])

    for p in sorted(papers, key=sort_key):
        pid      = p["paper_id"]
        fname    = p["filename"]
        raw_name = p.get("raw_name", fname)

        if not pid:
            if raw_name == processing_name:
                bar   = f"{YLW}[ · · · · ]{R}"
                label = f"{YLW}⟳ processing{R}"
            elif raw_name in pending_names:
                bar   = f"{CYN}[ · · · · ]{R}"
                label = f"{CYN}queued{R}"
            elif raw_name in failed_names:
                bar   = f"{RED}[ · · · · ]{R}"
                label = f"{RED}✗ failed{R}"
            else:
                bar   = f"{DIM}[ · · · · ]{R}"
                label = f"{DIM}pending{R}"
            name_w = W - 4 - vlen(bar) - vlen(label) - 2
            short_name = fname[:name_w] + "…" if vlen(fname) > name_w else fname
            print(row(f"  {bar} {DIM}{short_name}{R} {label}"))
        else:
            bar = stage_bar(pid)
            cur = current_stage_label(pid)
            if cur == "done":
                status_str = f"{GRN}done{R}"
            elif raw_name == processing_name:
                status_str = f"{YLW}⟳ {cur}ing{R}"
            else:
                status_str = f"{YLW}→{cur}{R}"
            name_w = W - 4 - vlen(bar) - vlen(status_str) - 3
            short_id = pid[:name_w] + "…" if len(pid) > name_w else pid
            print(row(f"  {bar} {short_id}  {status_str}"))
else:
    print(row(f"  {DIM}(no state file — run start-watch.sh first){R}"))

print(sep())

# recent log
print(row(f"  {B}[ Recent Log ]{R}"))
if log_lines:
    for line in log_lines:
        color = RED if (
            "ERROR" in line
            or "Traceback" in line
            or "Exception" in line
            or "failed" in line.lower()
            or "timeout" in line.lower()
        ) else DIM
        plain = re.sub(r"\033\[[0-9;]*m", "", line)
        trimmed = plain[:W - 4]
        print(row(f"  {color}{trimmed}{R}"))
else:
    print(row(f"  {DIM}(no log — run start-watch.sh first){R}"))

print(sep())

# paths
print(row(f"  {B}[ Paths ]{R}"))
home = str(pathlib.Path.home())
short_z = str(zotero_storage).replace(home, "~")
short_o = str(obsidian_vault).replace(home, "~")
print(row(f"  {DIM}Zotero  : {short_z}{R}"))
print(row(f"  {DIM}Obsidian: {short_o}{R}"))

print(sep("╚", "═", "╝"))

if LIVE:
    print(f"  {DIM}Refreshing every {INTERVAL}s  |  Ctrl+C to quit{R}")

PYEOF
}

# ── 실행 ──────────────────────────────────────────────────
if [ "$LIVE" -eq 1 ]; then
  trap 'echo ""; exit 0' INT TERM
  while true; do
    clear
    render
    sleep "$INTERVAL"
  done
else
  render
fi
