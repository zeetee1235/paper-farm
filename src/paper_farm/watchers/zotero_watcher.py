"""Zotero storage folder watcher — queue-based processing.

Architecture
------------
  Scanner thread  : polls Zotero storage every N seconds, enqueues new PDFs
  Worker (main)   : dequeues and runs full pipeline one paper at a time

Any PDF added to Zotero *while* a paper is processing is picked up on the
next scanner tick and placed in the queue automatically.

Queue status is written to .queue_status.json for the monitor script.
"""

from __future__ import annotations

import logging
import queue
import sqlite3
import threading
import time
from pathlib import Path

from paper_farm.config import Settings
from paper_farm.pipeline.service import PipelineService
from paper_farm.utils.jsonio import write_json, read_json

log = logging.getLogger(__name__)

_STATE_FILENAME        = ".zotero_watcher_state.json"
_QUEUE_STATUS_FILENAME = ".queue_status.json"


class ZoteroWatcher:
    """Polls Zotero storage and runs the pipeline on new PDFs."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.service = PipelineService(settings)
        self._state_path        = settings.project_root / _STATE_FILENAME
        self._queue_status_path = settings.project_root / _QUEUE_STATUS_FILENAME

        # Queue state (run_forever mode only)
        self._work_queue: queue.Queue[tuple[Path, dict]] = queue.Queue()
        self._queued_paths: set[str] = set()   # paths already queued (dedup)
        self._lock = threading.Lock()

        # Monitor-facing state
        self._processing: str | None = None    # filename currently being worked
        self._pending_names: list[str] = []    # filenames waiting in queue
        self._failed: list[str] = []           # recently failed filenames
        self._completed_session: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_forever(self) -> None:
        """Block and process the queue indefinitely."""
        storage  = self.settings.watcher.zotero_storage
        interval = self.settings.watcher.poll_interval

        log.info("Zotero watcher started.")
        log.info("  Storage  : %s", storage)
        log.info("  Obsidian : %s", self.settings.obsidian_papers_root)
        log.info("  LLM      : %s (%s)", self.settings.llm.backend, self.settings.llm.model)
        log.info("  Language : %s", self.settings.summary.language)
        log.info("  Interval : %ds", interval)

        if not storage.exists():
            log.error("Zotero storage path not found: %s", storage)
            log.error("Check [watcher] zotero_storage in paper-farm.toml.")
            return

        # Scanner thread: discovers new PDFs → enqueue
        scanner = threading.Thread(
            target=self._scanner_loop,
            args=(storage, interval),
            daemon=True,
            name="zotero-scanner",
        )
        scanner.start()

        # Worker loop on the main thread
        self._flush_queue_status()
        while True:
            try:
                pdf, metadata = self._work_queue.get(timeout=2)
            except queue.Empty:
                continue

            self._set_processing(pdf.name)
            state = self._load_state()
            try:
                paper_id = self.service.run(pdf, **metadata)
                state[str(pdf)] = paper_id
                self._save_state(state)
                with self._lock:
                    self._queued_paths.discard(str(pdf))
                    self._pending_names = [n for n in self._pending_names if n != pdf.name]
                    self._processing = None
                    self._completed_session += 1
                    self._failed = [f for f in self._failed if f != pdf.name]
                log.info("Done: %s → %s  (queue remaining: %d)", pdf.name, paper_id, self._work_queue.qsize())
            except Exception:
                log.exception("Pipeline failed: %s", pdf.name)
                with self._lock:
                    self._queued_paths.discard(str(pdf))
                    self._pending_names = [n for n in self._pending_names if n != pdf.name]
                    self._processing = None
                    if pdf.name not in self._failed:
                        self._failed.append(pdf.name)
            finally:
                self._flush_queue_status()
                self._work_queue.task_done()

    def scan_once(self) -> list[str]:
        """Single synchronous scan — for sync.sh / --once flag."""
        storage = self.settings.watcher.zotero_storage
        if not storage.exists():
            log.warning("Zotero storage not found: %s", storage)
            return []
        return self._scan_sync(storage)

    # ------------------------------------------------------------------
    # Scanner thread
    # ------------------------------------------------------------------

    def _scanner_loop(self, storage: Path, interval: int) -> None:
        while True:
            self._enqueue_new_pdfs(storage)
            time.sleep(interval)

    def _enqueue_new_pdfs(self, storage: Path) -> None:
        """Find unprocessed PDFs and add them to the work queue."""
        state = self._load_state()
        for pdf in sorted(storage.rglob("*.pdf")):
            pdf_str = str(pdf)
            paper_id = state.get(pdf_str)
            if self._is_done(paper_id):
                continue
            with self._lock:
                if pdf_str in self._queued_paths:
                    continue
                self._queued_paths.add(pdf_str)
                self._pending_names.append(pdf.name)

            metadata = self._fetch_zotero_metadata(pdf)
            self._work_queue.put((pdf, metadata))
            log.info("Queued: %s  (queue size: %d)", pdf.name, self._work_queue.qsize())
            self._flush_queue_status()

    # ------------------------------------------------------------------
    # Synchronous scan (scan_once / sync.sh)
    # ------------------------------------------------------------------

    def _scan_sync(self, storage: Path) -> list[str]:
        state = self._load_state()
        newly_processed: list[str] = []
        for pdf in sorted(storage.rglob("*.pdf")):
            pdf_str = str(pdf)
            paper_id = state.get(pdf_str)
            if self._is_done(paper_id):
                log.debug("Skipping (already done): %s", pdf.name)
                continue
            log.info("Processing: %s", pdf.name)
            metadata = self._fetch_zotero_metadata(pdf)
            try:
                paper_id = self.service.run(pdf, **metadata)
                state[pdf_str] = paper_id
                self._save_state(state)
                log.info("Done: %s → %s", pdf.name, paper_id)
                newly_processed.append(paper_id)
            except Exception:
                log.exception("Pipeline failed: %s", pdf.name)
        return newly_processed

    # ------------------------------------------------------------------
    # Queue status  (written to disk so monitor.sh can read it)
    # ------------------------------------------------------------------

    def _set_processing(self, name: str) -> None:
        with self._lock:
            self._processing = name
        self._flush_queue_status()

    def _flush_queue_status(self) -> None:
        with self._lock:
            status = {
                "processing":       self._processing,
                "pending":          list(self._pending_names),
                "queue_size":       len(self._pending_names),
                "failed":           list(self._failed),
                "completed_session": self._completed_session,
            }
        try:
            write_json(self._queue_status_path, status)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_done(self, paper_id: str | None) -> bool:
        if not paper_id:
            return False
        summary_md = self.settings.obsidian_papers_root / paper_id / "summary.md"
        return summary_md.exists()

    def _fetch_zotero_metadata(self, pdf: Path) -> dict:
        item_key = pdf.parent.name
        zotero_dir = self.settings.watcher.zotero_storage.parent
        db_path = zotero_dir / "zotero.sqlite"
        if not db_path.exists():
            return {}
        try:
            return _query_zotero_db(db_path, item_key)
        except Exception:
            log.debug("Zotero SQLite lookup failed (item_key=%s)", item_key, exc_info=True)
            return {}

    def _load_state(self) -> dict[str, str | None]:
        if self._state_path.exists():
            try:
                data = read_json(self._state_path)
                raw = data.get("processed", {})
                if isinstance(raw, list):
                    return {path: None for path in raw}
                return dict(raw)
            except Exception:
                pass
        return {}

    def _save_state(self, state: dict[str, str | None]) -> None:
        write_json(self._state_path, {"processed": state})


# ---------------------------------------------------------------------------
# Zotero SQLite helpers
# ---------------------------------------------------------------------------

def _query_zotero_db(db_path: Path, item_key: str) -> dict:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        cur = con.execute(
            """
            SELECT ia.parentItemID
            FROM items i
            JOIN itemAttachments ia ON ia.itemID = i.itemID
            WHERE i.key = ?
            """,
            (item_key,),
        )
        row = cur.fetchone()
        if row is None:
            return {}
        return _load_item_metadata(con, row["parentItemID"])
    finally:
        con.close()


def _load_item_metadata(con: sqlite3.Connection, item_id: int) -> dict:
    cur = con.execute(
        """
        SELECT f.fieldName, idv.value
        FROM itemData id
        JOIN itemDataValues idv ON id.valueID = idv.valueID
        JOIN fields f ON id.fieldID = f.fieldID
        WHERE id.itemID = ?
        """,
        (item_id,),
    )
    fields: dict[str, str] = {r["fieldName"]: r["value"] for r in cur.fetchall()}

    cur = con.execute(
        """
        SELECT c.firstName, c.lastName
        FROM itemCreators ic
        JOIN creators c ON ic.creatorID = c.creatorID
        JOIN creatorTypes ct ON ic.creatorTypeID = ct.creatorTypeID
        WHERE ic.itemID = ? AND ct.creatorType = 'author'
        ORDER BY ic.orderIndex
        """,
        (item_id,),
    )
    authors = []
    for r in cur.fetchall():
        name = f"{r['lastName']} {r['firstName']}".strip()
        if name:
            authors.append(name)

    metadata: dict = {}
    if title := fields.get("title"):
        metadata["title"] = title
    if date := fields.get("date"):
        try:
            metadata["year"] = int(str(date)[:4])
        except ValueError:
            pass
    if authors:
        metadata["authors"] = authors
    if doi := fields.get("DOI"):
        metadata["doi"] = doi
    if venue := (fields.get("publicationTitle") or fields.get("conferenceName") or fields.get("journalAbbreviation")):
        metadata["venue"] = venue

    return metadata
