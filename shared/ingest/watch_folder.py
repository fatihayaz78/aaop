"""File system watcher for log source folders using watchdog.

Watches all source folders under {base_path}/{tenant_id}/ and triggers
sync + delete on new/modified files.
"""

from __future__ import annotations

import asyncio
import os
import threading
import time

import structlog

from shared.ingest.source_config import FOLDER_TO_SOURCE

logger = structlog.get_logger(__name__)

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    _WATCHDOG_AVAILABLE = True
except ImportError:
    _WATCHDOG_AVAILABLE = False
    logger.warning("watchdog_not_installed", detail="pip install watchdog to enable folder watching")

    # Stubs for when watchdog is not installed
    class FileSystemEventHandler:  # type: ignore[no-redef]
        pass

    class Observer:  # type: ignore[no-redef]
        pass


class LogFileHandler(FileSystemEventHandler):
    """Handles file creation/modification events in source folders."""

    def __init__(self, tenant_id: str, sync_engine, loop: asyncio.AbstractEventLoop | None = None) -> None:
        super().__init__()
        self._tenant_id = tenant_id
        self._sync_engine = sync_engine
        self._loop = loop
        self._debounce_timers: dict[str, float] = {}
        self._debounce_seconds = 2.0
        self._lock = threading.Lock()

    def _get_source_name(self, file_path: str) -> str | None:
        """Extract source name from file path using folder→source mapping."""
        parts = file_path.replace("\\", "/").split("/")
        for part in reversed(parts):
            if part in FOLDER_TO_SOURCE:
                return FOLDER_TO_SOURCE[part]
        return None

    def _is_valid_file(self, path: str) -> bool:
        return path.endswith(".jsonl.gz") or path.endswith(".json") or path.endswith(".gz")

    def _handle_event(self, event) -> None:
        if event.is_directory:
            return
        path = event.src_path
        if not self._is_valid_file(path):
            return

        # Debounce: wait 2s after last event for this file
        with self._lock:
            self._debounce_timers[path] = time.time()

        def _delayed_process():
            time.sleep(self._debounce_seconds)
            with self._lock:
                last_event = self._debounce_timers.get(path, 0)
            if time.time() - last_event < self._debounce_seconds:
                return  # another event came in, skip

            source_name = self._get_source_name(path)
            if not source_name:
                logger.warning("watch_unknown_folder", path=path)
                return

            logger.info("watch_file_detected", file=path, source=source_name)
            # Trigger sync in the event loop if available
            try:
                if self._loop and self._loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        self._trigger_sync(source_name), self._loop,
                    )
                else:
                    logger.warning("watch_no_event_loop", source=source_name)
            except Exception as exc:
                logger.warning("watch_trigger_error", error=str(exc))

        threading.Thread(target=_delayed_process, daemon=True).start()

    async def _trigger_sync(self, source_name: str) -> None:
        """Trigger sync for the detected source."""
        try:
            from shared.ingest.source_config import SourceConfig
            # We need to look up the config — use a minimal approach
            row = await self._sync_engine._sqlite.fetch_one(
                "SELECT * FROM data_source_configs WHERE tenant_id = ? AND source_name = ?",
                (self._tenant_id, source_name),
            )
            if row:
                config = SourceConfig(**dict(row))
                await self._sync_engine.sync_source(
                    self._tenant_id, config, delete_after_import=True,
                )
        except Exception as exc:
            logger.warning("watch_sync_error", source=source_name, error=str(exc))

    def on_created(self, event) -> None:
        self._handle_event(event)

    def on_modified(self, event) -> None:
        self._handle_event(event)


class LogFolderWatcher:
    """Watches all source folders for a tenant and triggers sync on new files."""

    def __init__(self, base_path: str, tenant_id: str, sync_engine) -> None:
        self._base_path = base_path
        self._tenant_id = tenant_id
        self._sync_engine = sync_engine
        self._observer: Observer | None = None
        self._active = False

    def start(self) -> None:
        if not _WATCHDOG_AVAILABLE:
            logger.warning("watcher_skipped", reason="watchdog not installed")
            return

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = None

        handler = LogFileHandler(self._tenant_id, self._sync_engine, loop)
        self._observer = Observer()

        # Watch each source folder
        tenant_path = os.path.join(self._base_path, self._tenant_id)
        watched_count = 0

        for folder_name in FOLDER_TO_SOURCE:
            folder_path = os.path.join(tenant_path, folder_name)
            if os.path.isdir(folder_path):
                self._observer.schedule(handler, folder_path, recursive=True)
                watched_count += 1

        if watched_count > 0:
            self._observer.start()
            self._active = True
            logger.info("watcher_started", path=tenant_path, folders=watched_count)
        else:
            logger.warning("watcher_no_folders", path=tenant_path)

    def stop(self) -> None:
        if self._observer and self._active:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._active = False
            logger.info("watcher_stopped")

    @property
    def is_active(self) -> bool:
        return self._active

    def get_folder_status(self) -> list[dict]:
        """Return status of all watched folders."""
        tenant_path = os.path.join(self._base_path, self._tenant_id)
        statuses = []
        for folder_name, source_name in FOLDER_TO_SOURCE.items():
            folder_path = os.path.join(tenant_path, folder_name)
            exists = os.path.isdir(folder_path)
            file_count = 0
            if exists:
                for _root, _dirs, files in os.walk(folder_path):
                    file_count += sum(1 for f in files if f.endswith((".jsonl.gz", ".json", ".gz")))
            statuses.append({
                "folder": folder_name,
                "source_name": source_name,
                "exists": exists,
                "file_count": file_count,
            })
        return statuses
