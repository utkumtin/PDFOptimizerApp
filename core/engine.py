"""Asynchronous Ghostscript optimization engine.

Design principles:
  - Never block the UI thread. All GS work runs in a QProcess.
  - Throttle progress signals so the UI stays at ~20 fps, not thousands of signals/sec.
  - Write to a temp file, then atomic-rename on success. Users never see a half-written PDF.
  - When a tiny PDF finishes in <400ms, pad the elapsed time so the progress bar
    actually animates instead of teleporting from 0 to 100 (Apple-style perceived smoothness).
  - Pre-detect page count with a fast GS pass so progress percentage is accurate.
  - Queue multiple files and process them sequentially to avoid memory spikes.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, QProcess, Signal, QTimer, QElapsedTimer

from .file_utils import (
    validate_pdf,
    check_disk_space,
    generate_output_path,
    generate_temp_path,
    format_file_size,
    compute_savings,
)

# Minimum time (ms) the user should "see" a file being processed.
# Prevents the progress bar from instantly snapping 0→100 on small PDFs.
MINIMUM_VISIBLE_DURATION_MS = 400

# Maximum frequency (ms) at which we emit progress_updated.
PROGRESS_THROTTLE_MS = 50


@dataclass
class OptimizationTask:
    """All the info needed to optimize a single PDF."""

    input_path: str
    output_path: str = ""
    quality_preset: str = "/ebook"
    grayscale: bool = False
    total_pages: int = 0           # filled by page-count pre-pass
    original_size: int = 0         # filled before processing
    optimized_size: int = 0        # filled after processing


@dataclass
class OptimizationResult:
    """Result of a single file optimization."""

    task: OptimizationTask
    success: bool
    error_message: str = ""
    savings_text: str = ""
    savings_percent: float = 0.0


class GhostscriptWorker(QObject):
    """Handles a single PDF optimization through two QProcess phases.

    Phase 1 — page count (fast, no output file).
    Phase 2 — actual optimization (writes to temp file, then atomic rename).
    """

    # Per-file signals
    page_count_ready = Signal(int)                  # total pages detected
    progress_updated = Signal(int, int)             # current_page, total_pages
    file_finished = Signal(OptimizationResult)

    # Internal state
    _STATE_IDLE = 0
    _STATE_COUNTING = 1
    _STATE_OPTIMIZING = 2

    def __init__(self, gs_path: str):
        super().__init__()
        self.gs_path = gs_path
        self._state = self._STATE_IDLE
        self._task: OptimizationTask | None = None
        self._temp_path = ""
        self._accumulated_output = ""
        self._last_page = 0
        self._cancelled = False

        # Throttle timer — limits how often we emit progress_updated
        self._throttle_timer = QElapsedTimer()

        # Elapsed timer — tracks total visible processing time
        self._elapsed = QElapsedTimer()

        # QProcess for page counting (phase 1)
        self._count_process = QProcess()
        self._count_process.setProcessChannelMode(QProcess.MergedChannels)
        self._count_process.readyReadStandardOutput.connect(self._on_count_stdout)
        self._count_process.finished.connect(self._on_count_finished)

        # QProcess for actual optimization (phase 2)
        self._opt_process = QProcess()
        self._opt_process.setProcessChannelMode(QProcess.MergedChannels)
        self._opt_process.readyReadStandardOutput.connect(self._on_opt_stdout)
        self._opt_process.finished.connect(self._on_opt_finished)

    @property
    def is_busy(self) -> bool:
        return self._state != self._STATE_IDLE

    def start(self, task: OptimizationTask) -> None:
        """Begin the two-phase optimization for the given task."""
        if self.is_busy:
            return

        self._task = task
        self._task.original_size = os.path.getsize(task.input_path)
        self._cancelled = False
        self._last_page = 0
        self._accumulated_output = ""

        if not task.output_path:
            task.output_path = generate_output_path(task.input_path)

        self._temp_path = generate_temp_path(task.output_path)
        self._elapsed.start()

        # Phase 1: fast page count
        self._state = self._STATE_COUNTING
        self._count_process.start(self.gs_path, [
            "-dNODISPLAY",
            "-dQUIET",
            "-c",
            f"({task.input_path}) (r) file runpdfbegin pdfpagecount = quit",
        ])

    def cancel(self) -> None:
        """Immediately kill whichever phase is running and clean up."""
        self._cancelled = True

        for proc in (self._count_process, self._opt_process):
            if proc.state() == QProcess.Running:
                proc.kill()
                proc.waitForFinished(1000)

        self._cleanup_temp()
        self._finish_with_error("Cancelled by user")

    # ------------------------------------------------------------------
    # Phase 1 — page count
    # ------------------------------------------------------------------

    def _on_count_stdout(self) -> None:
        data = self._count_process.readAllStandardOutput()
        self._accumulated_output += bytes(data).decode("utf-8", errors="replace")

    def _on_count_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        if self._cancelled:
            return

        total_pages = 0
        if exit_code == 0:
            match = re.search(r"(\d+)", self._accumulated_output.strip())
            if match:
                total_pages = int(match.group(1))

        self._task.total_pages = total_pages
        self._accumulated_output = ""

        if total_pages > 0:
            self.page_count_ready.emit(total_pages)

        # ---> Tiny delay before heavy work — let the UI settle
        QTimer.singleShot(30, self._start_optimization)

    # ------------------------------------------------------------------
    # Phase 2 — actual optimization
    # ------------------------------------------------------------------

    def _start_optimization(self) -> None:
        if self._cancelled:
            return

        self._state = self._STATE_OPTIMIZING
        self._throttle_timer.start()

        task = self._task
        args = [
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
            f"-dPDFSETTINGS={task.quality_preset}",
            "-dNOPAUSE",
            "-dBATCH",
            # Don't pass -dQUIET here; we need page output for progress
        ]

        if task.grayscale:
            args.extend([
                "-sColorConversionStrategy=Gray",
                "-dProcessColorModel=/DeviceGray",
            ])

        args.extend([f"-sOutputFile={self._temp_path}", task.input_path])
        self._opt_process.start(self.gs_path, args)

    def _on_opt_stdout(self) -> None:
        data = self._opt_process.readAllStandardOutput()
        output = bytes(data).decode("utf-8", errors="replace")

        # Parse all page markers in this chunk
        for match in re.finditer(r"Page\s+(\d+)", output):
            self._last_page = int(match.group(1))

        # Throttle: emit at most every PROGRESS_THROTTLE_MS
        if self._throttle_timer.elapsed() >= PROGRESS_THROTTLE_MS:
            self._throttle_timer.restart()
            self.progress_updated.emit(self._last_page, self._task.total_pages)

    def _on_opt_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        if self._cancelled:
            return

        if exit_code != 0:
            self._cleanup_temp()
            self._finish_with_error(f"Ghostscript exited with code {exit_code}")
            return

        # Atomic rename: temp -> final output
        try:
            if os.path.exists(self._task.output_path):
                os.remove(self._task.output_path)
            os.rename(self._temp_path, self._task.output_path)
        except OSError as e:
            self._cleanup_temp()
            self._finish_with_error(f"Failed to write output file: {e}")
            return

        self._task.optimized_size = os.path.getsize(self._task.output_path)
        savings_text, savings_pct = compute_savings(
            self._task.original_size, self._task.optimized_size
        )

        result = OptimizationResult(
            task=self._task,
            success=True,
            savings_text=savings_text,
            savings_percent=savings_pct,
        )

        # Apple trick: ensure the user sees the progress bar for at least
        # MINIMUM_VISIBLE_DURATION_MS. If the file was tiny and GS finished
        # almost instantly, pad the remaining time before emitting the signal.
        elapsed = self._elapsed.elapsed()
        remaining = MINIMUM_VISIBLE_DURATION_MS - elapsed
        if remaining > 0:
            QTimer.singleShot(int(remaining), lambda: self._emit_finished(result))
        else:
            self._emit_finished(result)

    def _emit_finished(self, result: OptimizationResult) -> None:
        # Emit final 100% progress so the bar fills completely
        if self._task.total_pages > 0:
            self.progress_updated.emit(self._task.total_pages, self._task.total_pages)

        self._state = self._STATE_IDLE
        self.file_finished.emit(result)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _cleanup_temp(self) -> None:
        if self._temp_path and os.path.exists(self._temp_path):
            try:
                os.remove(self._temp_path)
            except OSError:
                pass

    def _finish_with_error(self, message: str) -> None:
        result = OptimizationResult(
            task=self._task,
            success=False,
            error_message=message,
        )
        self._state = self._STATE_IDLE
        self.file_finished.emit(result)


class OptimizationQueue(QObject):
    """Processes a list of PDFs sequentially through a single GhostscriptWorker.

    Sequential processing avoids memory spikes from parallel GS instances
    and keeps CPU contention predictable.
    """

    # Emitted per file
    file_started = Signal(int, str)                 # index, filename
    file_progress = Signal(int, int, int)           # index, current_page, total_pages
    file_completed = Signal(int, OptimizationResult)

    # Emitted for the entire queue
    queue_started = Signal(int)                     # total file count
    queue_finished = Signal(list)                   # list[OptimizationResult]

    def __init__(self, gs_path: str):
        super().__init__()
        self._worker = GhostscriptWorker(gs_path)
        self._worker.page_count_ready.connect(self._on_page_count)
        self._worker.progress_updated.connect(self._on_progress)
        self._worker.file_finished.connect(self._on_file_finished)

        self._tasks: list[OptimizationTask] = []
        self._results: list[OptimizationResult] = []
        self._current_index = -1
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def total_files(self) -> int:
        return len(self._tasks)

    def enqueue(
        self,
        file_paths: list[str],
        quality_preset: str = "/ebook",
        grayscale: bool = False,
    ) -> list[str]:
        """Validate and enqueue files. Returns a list of validation errors (empty = all ok)."""
        errors = []
        self._tasks.clear()

        for path in file_paths:
            is_valid, error = validate_pdf(path)
            if not is_valid:
                errors.append(error)
                continue

            output_dir = os.path.dirname(path)
            if not check_disk_space(output_dir):
                errors.append(f"Low disk space for: {os.path.basename(path)}")
                continue

            self._tasks.append(OptimizationTask(
                input_path=path,
                quality_preset=quality_preset,
                grayscale=grayscale,
            ))

        return errors

    def start(self) -> None:
        """Begin processing the queue."""
        if self._running or not self._tasks:
            return

        self._running = True
        self._results.clear()
        self._current_index = -1
        self.queue_started.emit(len(self._tasks))
        self._process_next()

    def cancel(self) -> None:
        """Cancel the current file and abandon the rest of the queue."""
        if not self._running:
            return

        self._running = False
        self._worker.cancel()
        self.queue_finished.emit(self._results)

    def _process_next(self) -> None:
        self._current_index += 1
        if self._current_index >= len(self._tasks):
            self._running = False
            self.queue_finished.emit(self._results)
            return

        task = self._tasks[self._current_index]
        filename = os.path.basename(task.input_path)
        self.file_started.emit(self._current_index, filename)

        # Small breathing room between files so the UI can repaint the new state
        QTimer.singleShot(60, lambda: self._worker.start(task))

    def _on_page_count(self, total: int) -> None:
        self.file_progress.emit(self._current_index, 0, total)

    def _on_progress(self, current_page: int, total_pages: int) -> None:
        self.file_progress.emit(self._current_index, current_page, total_pages)

    def _on_file_finished(self, result: OptimizationResult) -> None:
        self._results.append(result)
        self.file_completed.emit(self._current_index, result)

        if self._running:
            self._process_next()
