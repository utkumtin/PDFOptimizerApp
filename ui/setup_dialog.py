from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QWidget, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal

from core.dependency_manager import (
    is_homebrew_installed,
    is_ghostscript_installed,
    DependencyInstaller,
)


class _StatusRow(QWidget):
    """A single row showing dependency name, status icon, and install button."""

    install_requested = Signal()

    def __init__(self, name: str):
        super().__init__()
        self._name = name

        self.icon_label = QLabel()
        self.icon_label.setFixedWidth(24)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setObjectName("statusIcon")

        self.name_label = QLabel(name)
        self.name_label.setObjectName("depName")

        self.status_label = QLabel()
        self.status_label.setObjectName("depStatus")

        self.install_button = QPushButton("Install")
        self.install_button.setObjectName("installButton")
        self.install_button.setFixedWidth(80)
        self.install_button.clicked.connect(self.install_requested.emit)
        self.install_button.hide()

        row = QHBoxLayout()
        row.setContentsMargins(12, 8, 12, 8)
        row.addWidget(self.icon_label)
        row.addWidget(self.name_label)
        row.addStretch()
        row.addWidget(self.status_label)
        row.addWidget(self.install_button)
        self.setLayout(row)

    def mark_found(self, path: str) -> None:
        self.icon_label.setText("\u2705")
        self.status_label.setText(path)
        self.status_label.setProperty("found", True)
        self.style().polish(self.status_label)
        self.install_button.hide()

    def mark_missing(self) -> None:
        self.icon_label.setText("\u274C")
        self.status_label.setText("Not found")
        self.status_label.setProperty("found", False)
        self.style().polish(self.status_label)
        self.install_button.show()

    def mark_installing(self) -> None:
        self.install_button.setEnabled(False)
        self.install_button.setText("...")
        self.status_label.setText("Installing...")


class SetupDialog(QDialog):
    """Pre-flight dialog that checks Homebrew and Ghostscript availability."""

    dependencies_satisfied = Signal(str)  # gs_path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PDF Optimizer — Setup")
        self.setMinimumWidth(520)
        self.setModal(True)
        self.setObjectName("setupDialog")

        self._installer = DependencyInstaller()
        self._installer.output_received.connect(self._append_output)
        self._installer.install_finished.connect(self._on_install_finished)

        # --- Header ---
        header = QLabel("Dependency Check")
        header.setObjectName("setupHeader")

        description = QLabel(
            "PDF Optimizer requires Ghostscript to compress PDF files.\n"
            "Ghostscript is installed via Homebrew, the macOS package manager."
        )
        description.setObjectName("setupDescription")
        description.setWordWrap(True)

        # --- Status rows ---
        self._brew_row = _StatusRow("Homebrew")
        self._brew_row.setObjectName("depRow")
        self._brew_row.install_requested.connect(self._install_homebrew)

        self._gs_row = _StatusRow("Ghostscript")
        self._gs_row.setObjectName("depRow")
        self._gs_row.install_requested.connect(self._install_ghostscript)

        # --- Terminal output ---
        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        self._output.setObjectName("terminalOutput")
        self._output.setFixedHeight(160)
        self._output.hide()

        # --- Buttons ---
        self._continue_button = QPushButton("Continue")
        self._continue_button.setObjectName("optimizeButton")
        self._continue_button.setMinimumWidth(120)
        self._continue_button.setEnabled(False)
        self._continue_button.clicked.connect(self._on_continue)

        self._recheck_button = QPushButton("Re-check")
        self._recheck_button.setObjectName("recheckButton")
        self._recheck_button.clicked.connect(self.run_checks)

        self._quit_button = QPushButton("Quit")
        self._quit_button.setObjectName("quitButton")
        self._quit_button.clicked.connect(self.reject)

        button_row = QHBoxLayout()
        button_row.addWidget(self._quit_button)
        button_row.addStretch()
        button_row.addWidget(self._recheck_button)
        button_row.addWidget(self._continue_button)

        # --- Layout ---
        layout = QVBoxLayout()
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(header)
        layout.addWidget(description)
        layout.addWidget(self._brew_row)
        layout.addWidget(self._gs_row)
        layout.addWidget(self._output)
        layout.addStretch()
        layout.addLayout(button_row)
        self.setLayout(layout)

        self._gs_path: str | None = None

    def run_checks(self) -> None:
        """Detect Homebrew and Ghostscript, update the UI accordingly."""
        brew_path = is_homebrew_installed()
        if brew_path:
            self._brew_row.mark_found(brew_path)
        else:
            self._brew_row.mark_missing()

        gs_path = is_ghostscript_installed()
        if gs_path:
            self._gs_row.mark_found(gs_path)
            self._gs_path = gs_path
        else:
            self._gs_row.mark_missing()
            self._gs_path = None

        all_ok = brew_path is not None and gs_path is not None
        self._continue_button.setEnabled(all_ok)

    # --- Install actions ---

    def _install_homebrew(self) -> None:
        self._brew_row.mark_installing()
        self._output.clear()
        self._output.show()
        self._installer.install_homebrew()

    def _install_ghostscript(self) -> None:
        self._gs_row.mark_installing()
        self._output.clear()
        self._output.show()
        self._installer.install_ghostscript()

    # --- Slots ---

    def _append_output(self, text: str) -> None:
        self._output.moveCursor(self._output.textCursor().End)
        self._output.insertPlainText(text)
        self._output.ensureCursorVisible()

    def _on_install_finished(self, success: bool, target: str) -> None:
        if success:
            self._append_output(f"\n{target} installed successfully.\n")
        else:
            self._append_output(f"\n{target} installation failed. Try installing manually.\n")

        # Re-check both dependencies after any install attempt
        self.run_checks()

    def _on_continue(self) -> None:
        if self._gs_path:
            self.dependencies_satisfied.emit(self._gs_path)
        self.accept()
