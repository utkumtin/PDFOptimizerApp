import sys
import os

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from core.dependency_manager import is_homebrew_installed, is_ghostscript_installed
from ui.main_window import MainWindow
from ui.setup_dialog import SetupDialog


def load_stylesheet() -> str:
    style_path = os.path.join(os.path.dirname(__file__), "resources", "style.qss")
    if os.path.isfile(style_path):
        with open(style_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def main() -> None:
    # macOS Retina / High-DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("PDF Optimizer")
    app.setOrganizationName("PDFOptimizer")
    app.setApplicationDisplayName("PDF Optimizer")

    # System font: macOS will resolve -apple-system to SF Pro
    app.setFont(QFont(".AppleSystemUIFont", 13))

    # macOS: keep app running when last window closes (standard macOS behavior)
    app.setQuitOnLastWindowClosed(True)

    stylesheet = load_stylesheet()
    if stylesheet:
        app.setStyleSheet(stylesheet)

    # Fast path: skip the setup dialog if everything is already installed
    gs_path = is_ghostscript_installed()
    brew_path = is_homebrew_installed()

    if not gs_path or not brew_path:
        dialog = SetupDialog()
        dialog.run_checks()

        gs_path = None

        def on_satisfied(path: str):
            nonlocal gs_path
            gs_path = path

        dialog.dependencies_satisfied.connect(on_satisfied)

        if dialog.exec() != SetupDialog.Accepted:
            sys.exit(0)

        if not gs_path:
            sys.exit(1)

    window = MainWindow()
    window.gs_path = gs_path
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
