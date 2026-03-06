import os

from PySide6.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QLabel,
    QFileDialog, QMessageBox, QApplication,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QKeySequence

from .components import (
    CardWidget, FileListWidget,
    QualitySelector, GrayscaleCheckbox,
    OptimizeButton, CancelButton,
    ProgressIndicator,
)
from core.engine import OptimizationQueue, OptimizationResult
from core.file_utils import format_file_size


# Drop zone — PDF icon + file list with removal

class DropZone(QWidget):
    """A drop target that shows either an empty prompt or a file list."""

    files_changed = Signal(list)   # emitted when files are added or removed

    def __init__(self):
        super().__init__()
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(160)

        # Empty state
        self._icon_label = QLabel("\U0001F4C4")
        self._icon_label.setObjectName("dropIcon")
        self._icon_label.setAlignment(Qt.AlignCenter)

        self._hint_label = QLabel("Drop PDF files here or click to browse")
        self._hint_label.setObjectName("dropHint")
        self._hint_label.setAlignment(Qt.AlignCenter)

        empty_layout = QVBoxLayout()
        empty_layout.setAlignment(Qt.AlignCenter)
        empty_layout.setSpacing(8)
        empty_layout.addStretch()
        empty_layout.addWidget(self._icon_label)
        empty_layout.addWidget(self._hint_label)
        empty_layout.addStretch()

        self._empty_state = QWidget()
        self._empty_state.setLayout(empty_layout)

        # File list state
        self._file_list = FileListWidget()
        self._file_list.file_removed.connect(self._on_file_removed)

        self._add_more_label = QLabel("click or drop to add more files")
        self._add_more_label.setObjectName("addMoreHint")
        self._add_more_label.setAlignment(Qt.AlignCenter)

        list_layout = QVBoxLayout()
        list_layout.setContentsMargins(4, 4, 4, 4)
        list_layout.setSpacing(6)
        list_layout.addWidget(self._file_list)
        list_layout.addWidget(self._add_more_label)

        self._list_state = QWidget()
        self._list_state.setLayout(list_layout)
        self._list_state.hide()

        # Root
        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._empty_state)
        root.addWidget(self._list_state)
        self.setLayout(root)

    @property
    def file_list(self) -> FileListWidget:
        return self._file_list

    def show_files(self, paths: list[str], preset: str = "/ebook") -> None:
        self._file_list.set_files(paths, preset)
        self._empty_state.hide()
        self._list_state.show()

    def show_empty(self) -> None:
        self._file_list.clear()
        self._list_state.hide()
        self._empty_state.show()

    def update_preset(self, preset: str) -> None:
        """Re-estimate savings when quality preset changes."""
        if self._list_state.isVisible():
            self._file_list.update_preset(preset)

    def _on_file_removed(self, path: str) -> None:
        remaining = self._file_list.current_paths()
        if not remaining:
            self.show_empty()
        self.files_changed.emit(remaining)

    def mousePressEvent(self, event):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select PDF Files", "", "PDF Files (*.pdf)"
        )
        if paths:
            # Merge with existing files (avoid duplicates)
            existing = set(self._file_list.current_paths())
            merged = list(existing | set(paths))
            self.show_files(merged, self._file_list._preset)
            self.files_changed.emit(merged)

    def dragEnterEvent(self, event):
        if not event.mimeData().hasUrls():
            event.ignore()
            return

        urls = event.mimeData().urls()
        if all(url.toLocalFile().lower().endswith(".pdf") for url in urls):
            event.acceptProposedAction()
            self.setProperty("dragOver", True)
            self.style().polish(self)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setProperty("dragOver", False)
        self.style().polish(self)
        event.accept()

    def dropEvent(self, event):
        self.setProperty("dragOver", False)
        self.style().polish(self)

        urls = event.mimeData().urls()
        new_paths = [url.toLocalFile() for url in urls]

        # Merge with existing
        existing = set(self._file_list.current_paths())
        merged = list(existing | set(new_paths))
        self.show_files(merged, self._file_list._preset)
        self.files_changed.emit(merged)
        event.acceptProposedAction()


# Main window

class MainWindow(QMainWindow):
    """Primary application window with Apple-like card layout."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Optimizer")
        self.setMinimumSize(520, 480)
        self.resize(600, 560)
        self.setAcceptDrops(True)

        self.gs_path: str = ""
        self._pending_files: list[str] = []
        self._queue: OptimizationQueue | None = None

        self._build_menu_bar()
        self._build_ui()
        self._center_on_screen()

    def _build_menu_bar(self) -> None:
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")

        open_action = QAction("Open PDF...", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self._open_file_dialog)
        file_menu.addAction(open_action)

    def _build_ui(self) -> None:
        # --- Drop zone card ---
        self.drop_zone = DropZone()
        self.drop_card = CardWidget()
        self.drop_card.add_widget(self.drop_zone)

        # --- Settings card ---
        self.quality_selector = QualitySelector()
        self.grayscale_checkbox = GrayscaleCheckbox()

        self.settings_card = CardWidget()
        self.settings_card.add_widget(self.quality_selector)
        self.settings_card.add_separator()
        self.settings_card.add_widget(self.grayscale_checkbox)

        # --- Buttons ---
        self.optimize_button = OptimizeButton()
        self.optimize_button.setEnabled(False)
        self.cancel_button = CancelButton()

        button_row = QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.optimize_button)
        button_row.addStretch()

        # --- Progress card ---
        self.progress_indicator = ProgressIndicator()
        self.progress_card = CardWidget()
        self.progress_card.add_widget(self.progress_indicator)

        # --- Connections ---
        self.drop_zone.files_changed.connect(self._on_files_changed)
        self.quality_selector.preset_changed.connect(self._on_preset_changed)
        self.optimize_button.clicked.connect(self._on_optimize_clicked)
        self.cancel_button.clicked.connect(self._on_cancel_clicked)

        # --- Root layout ---
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(20, 12, 20, 20)
        root_layout.setSpacing(12)

        root_layout.addWidget(self.drop_card)
        root_layout.addWidget(self.settings_card)
        root_layout.addLayout(button_row)
        root_layout.addWidget(self.progress_card)
        root_layout.addStretch()

        container = QWidget()
        container.setObjectName("windowBody")
        container.setLayout(root_layout)
        self.setCentralWidget(container)

    def _center_on_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = (geo.width() - self.width()) // 2
            y = (geo.height() - self.height()) // 2
            self.move(x, y)

    # File handling

    def _open_file_dialog(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select PDF Files", "", "PDF Files (*.pdf)"
        )
        if paths:
            self.drop_zone.show_files(paths, self.quality_selector.current_preset())
            self._on_files_changed(paths)

    def _on_files_changed(self, paths: list[str]) -> None:
        self._pending_files = paths
        self.optimize_button.setEnabled(len(paths) > 0)
        self.progress_indicator.reset()

    def _on_preset_changed(self, preset: str) -> None:
        self.drop_zone.update_preset(preset)

    # Optimization flow

    def _on_optimize_clicked(self) -> None:
        if not self._pending_files or not self.gs_path:
            return

        self._queue = OptimizationQueue(self.gs_path)

        errors = self._queue.enqueue(
            self._pending_files,
            quality_preset=self.quality_selector.current_preset(),
            grayscale=self.grayscale_checkbox.isChecked(),
        )

        if errors:
            QMessageBox.warning(
                self,
                "Validation Issues",
                "Some files were skipped:\n\n" + "\n".join(errors),
            )

        if self._queue.total_files == 0:
            return

        self._queue.file_started.connect(self._on_file_started)
        self._queue.file_progress.connect(self._on_file_progress)
        self._queue.file_completed.connect(self._on_file_completed)
        self._queue.queue_finished.connect(self._on_queue_finished)

        self._set_processing_state(True)
        self._queue.start()

    def _on_cancel_clicked(self) -> None:
        if self._queue and self._queue.is_running:
            self._queue.cancel()

    # Queue signal handlers

    def _on_file_started(self, index: int, filename: str) -> None:
        total = self._queue.total_files
        if total > 1:
            self.progress_indicator.set_status(
                f"Optimizing {filename}\u2026  ({index + 1} of {total})"
            )
        else:
            self.progress_indicator.set_status(f"Optimizing {filename}\u2026")

        self.progress_indicator.set_progress(0, 0)

    def _on_file_progress(self, _index: int, current: int, total: int) -> None:
        self.progress_indicator.set_progress(current, total)

    def _on_file_completed(self, _index: int, result: OptimizationResult) -> None:
        if not result.success:
            return

        task = result.task
        filename = os.path.basename(task.input_path)
        self.progress_indicator.add_result(
            filename,
            format_file_size(task.original_size),
            format_file_size(task.optimized_size),
            result.savings_percent,
        )

    def _on_queue_finished(self, results: list[OptimizationResult]) -> None:
        self._set_processing_state(False)
        self.progress_indicator.finish_progress()

        succeeded = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        if not results:
            self.progress_indicator.set_status("Cancelled")
            return

        if failed and not succeeded:
            self.progress_indicator.set_status("All files failed")
            errors = "\n".join(r.error_message for r in failed)
            QMessageBox.warning(self, "Optimization Failed", errors)
            return

        if len(succeeded) == 1:
            status = "Done \u2014 file saved"
        else:
            status = f"Done \u2014 {len(succeeded)} file(s) optimized"

        if failed:
            status += f", {len(failed)} failed"

        self.progress_indicator.set_status(status)

        self._pending_files.clear()
        self.drop_zone.show_empty()
        self.optimize_button.setEnabled(False)

    # UI state

    def _set_processing_state(self, processing: bool) -> None:
        self.optimize_button.setVisible(not processing)
        self.cancel_button.setVisible(processing)
        self.drop_zone.setEnabled(not processing)
        self.settings_card.setEnabled(not processing)
