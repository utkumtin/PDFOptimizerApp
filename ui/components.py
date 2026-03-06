import os

from PySide6.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QVBoxLayout, QPushButton,
    QProgressBar, QCheckBox, QFrame, QButtonGroup, QSizePolicy,
)
from PySide6.QtCore import (
    Qt, Signal, QPropertyAnimation, QEasingCurve, QSize,
)
from PySide6.QtGui import QIcon

from core.file_utils import format_file_size, estimate_savings

_RESOURCES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources")
_TRASH_ICON_PATH = os.path.join(_RESOURCES_DIR, "trash.svg")

QUALITY_PRESETS = [
    ("/screen",   "Low",     "Smallest file size"),
    ("/ebook",    "Medium",  "Good balance"),
    ("/printer",  "High",    "Print quality"),
    ("/prepress", "Maximum", "Prepress quality"),
]


# Card container — Apple-style grouped section

class CardWidget(QFrame):
    """A rounded white container that groups related controls, like macOS Settings cards."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._layout = QVBoxLayout()
        self._layout.setContentsMargins(16, 14, 16, 14)
        self._layout.setSpacing(10)
        self.setLayout(self._layout)

    def add_widget(self, widget: QWidget) -> None:
        self._layout.addWidget(widget)

    def add_layout(self, layout) -> None:
        self._layout.addLayout(layout)

    def add_separator(self) -> None:
        line = QFrame()
        line.setObjectName("cardSeparator")
        line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(1)
        self._layout.addWidget(line)


# File list — shows dropped PDF files with size, estimate, trash

class FileListWidget(QWidget):
    """Displays a list of PDF files with estimated savings and a remove button."""

    file_removed = Signal(str)  # emits the path of the removed file

    def __init__(self):
        super().__init__()
        self.setObjectName("fileList")

        self._layout = QVBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(3)
        self.setLayout(self._layout)

        self._paths: list[str] = []
        self._preset: str = "/ebook"

    def set_files(self, paths: list[str], preset: str = "/ebook") -> None:
        self._paths = list(paths)
        self._preset = preset
        self._rebuild()

    def update_preset(self, preset: str) -> None:
        self._preset = preset
        self._rebuild()

    def remove_file(self, path: str) -> None:
        if path in self._paths:
            self._paths.remove(path)
            self._rebuild()
            self.file_removed.emit(path)

    def current_paths(self) -> list[str]:
        return list(self._paths)

    def clear(self) -> None:
        self._paths.clear()
        self._clear_rows()

    def _clear_rows(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _rebuild(self) -> None:
        self._clear_rows()

        for path in self._paths:
            name = os.path.basename(path)
            size = os.path.getsize(path) if os.path.isfile(path) else 0
            _, savings_text, savings_pct = estimate_savings(size, self._preset)

            # Row container
            row_widget = QWidget()
            row_widget.setObjectName("fileRow")
            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(10, 6, 6, 6)
            row_layout.setSpacing(8)

            # File name
            name_label = QLabel(f"\U0001F4C4  {name}")
            name_label.setObjectName("fileName")
            name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

            # Original size
            size_label = QLabel(format_file_size(size))
            size_label.setObjectName("fileSize")

            # Estimated savings
            est_label = QLabel(f"\u2248\u2009\u2212{savings_text} ({savings_pct:.0f}%)")
            est_label.setObjectName("fileEstimate")
            est_label.setToolTip("Estimated savings — actual results may vary")

            # Trash button
            trash_btn = QPushButton()
            trash_btn.setIcon(QIcon(_TRASH_ICON_PATH))
            trash_btn.setIconSize(QSize(16, 16))
            trash_btn.setObjectName("trashButton")
            trash_btn.setFixedSize(28, 28)
            trash_btn.setCursor(Qt.PointingHandCursor)
            trash_btn.setToolTip("Remove from list")
            # Capture path by default argument to avoid closure issues
            trash_btn.clicked.connect(lambda _checked, p=path: self.remove_file(p))

            row_layout.addWidget(name_label)
            row_layout.addWidget(size_label)
            row_layout.addWidget(est_label)
            row_layout.addWidget(trash_btn)
            row_widget.setLayout(row_layout)

            self._layout.addWidget(row_widget)


# Quality selector — segmented toggle buttons

class QualitySelector(QWidget):
    """A row of mutually-exclusive buttons for quality presets (segmented control)."""

    preset_changed = Signal(str)  # emits the gs preset string like "/ebook"

    def __init__(self):
        super().__init__()

        self._buttons: list[QPushButton] = []
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        header = QLabel("Quality")
        header.setObjectName("sliderHeader")

        self._description = QLabel()
        self._description.setObjectName("presetDescription")

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(0)

        for i, (preset, short_name, description) in enumerate(QUALITY_PRESETS):
            btn = QPushButton(short_name)
            btn.setCheckable(True)
            btn.setObjectName("qualityButton")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumHeight(32)

            # Position-based rounding: first, middle, last
            if i == 0:
                btn.setProperty("position", "first")
            elif i == len(QUALITY_PRESETS) - 1:
                btn.setProperty("position", "last")
            else:
                btn.setProperty("position", "middle")

            self._group.addButton(btn, i)
            self._buttons.append(btn)
            button_row.addWidget(btn)

        # Default: Medium (/ebook)
        self._buttons[1].setChecked(True)
        self._update_description(1)

        self._group.idClicked.connect(self._on_selection_changed)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(header)
        layout.addLayout(button_row)
        layout.addWidget(self._description)
        self.setLayout(layout)

    def _on_selection_changed(self, button_id: int) -> None:
        self._update_description(button_id)
        preset, _, _ = QUALITY_PRESETS[button_id]
        self.preset_changed.emit(preset)

    def _update_description(self, index: int) -> None:
        _, _, description = QUALITY_PRESETS[index]
        self._description.setText(description)

    def current_preset(self) -> str:
        checked_id = self._group.checkedId()
        if checked_id < 0:
            checked_id = 1
        preset, _, _ = QUALITY_PRESETS[checked_id]
        return preset


# Grayscale checkbox

class GrayscaleCheckbox(QCheckBox):
    """Toggle for converting PDF to grayscale during optimization."""

    def __init__(self):
        super().__init__("Convert to grayscale")
        self.setObjectName("grayscaleCheckbox")


# Buttons

class OptimizeButton(QPushButton):
    """Primary action button."""

    def __init__(self):
        super().__init__("Optimize")
        self.setObjectName("optimizeButton")
        self.setMinimumWidth(160)
        self.setMinimumHeight(36)


class CancelButton(QPushButton):
    """Secondary button to cancel ongoing optimization."""

    def __init__(self):
        super().__init__("Cancel")
        self.setObjectName("cancelButton")
        self.setMinimumWidth(100)
        self.setMinimumHeight(36)
        self.hide()


# Animated progress bar

class SmoothProgressBar(QProgressBar):
    """A progress bar that smoothly animates to the target value.

    Instead of snapping from 30 to 50, it glides there over ~200ms.
    This is the Apple trick: perceived smoothness through gentle easing.
    """

    def __init__(self):
        super().__init__()
        self.setTextVisible(False)
        self.setObjectName("smoothProgress")

        self._animation = QPropertyAnimation(self, b"value")
        self._animation.setDuration(200)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)

    def animate_to(self, target: int) -> None:
        if self._animation.state() == QPropertyAnimation.Running:
            self._animation.stop()

        self._animation.setStartValue(self.value())
        self._animation.setEndValue(target)
        self._animation.start()

    def snap_to(self, value: int) -> None:
        if self._animation.state() == QPropertyAnimation.Running:
            self._animation.stop()
        self.setValue(value)


# Progress indicator

class ProgressIndicator(QWidget):
    """Progress bar with status label and accumulating result list."""

    def __init__(self):
        super().__init__()

        self.bar = SmoothProgressBar()

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")

        # Container for per-file result rows
        self._results_widget = QWidget()
        self._results_layout = QVBoxLayout()
        self._results_layout.setContentsMargins(0, 0, 0, 0)
        self._results_layout.setSpacing(2)
        self._results_widget.setLayout(self._results_layout)
        self._results_widget.hide()

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.bar)
        layout.addWidget(self.status_label)
        layout.addWidget(self._results_widget)
        self.setLayout(layout)

    def set_progress(self, current: int, total: int) -> None:
        if total <= 0:
            self.bar.setMaximum(0)
            return

        self.bar.setMaximum(total)
        self.bar.animate_to(current)

    def finish_progress(self) -> None:
        """Snap the bar to 100% and stop any running animation."""
        self.bar.setMaximum(100)
        self.bar.snap_to(100)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def add_result(
        self, filename: str, original: str, optimized: str, percent: float
    ) -> None:
        label = QLabel()
        label.setObjectName("sizeLabel")

        if percent >= 0:
            label.setText(
                f"\U0001F4C4  {filename}:  "
                f"{original}  \u2192  {optimized}  (saved {percent:.0f}%)"
            )
            label.setProperty("grew", False)
        else:
            label.setText(
                f"\U0001F4C4  {filename}:  "
                f"{original}  \u2192  {optimized}  "
                f"(grew {abs(percent):.0f}% \u2014 already optimized?)"
            )
            label.setProperty("grew", True)

        label.style().polish(label)
        self._results_layout.addWidget(label)
        self._results_widget.show()

    def clear_results(self) -> None:
        while self._results_layout.count():
            item = self._results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._results_widget.hide()

    def reset(self) -> None:
        self.bar.setMaximum(100)
        self.bar.snap_to(0)
        self.status_label.setText("Ready")
        self.clear_results()
