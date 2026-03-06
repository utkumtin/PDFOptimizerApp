import os
import shutil

from PySide6.QtCore import QObject, QProcess, Signal, QProcessEnvironment


def is_homebrew_installed() -> str | None:
    """Return the Homebrew binary path if installed, None otherwise."""
    known_paths = [
        "/opt/homebrew/bin/brew",  # Apple Silicon
        "/usr/local/bin/brew",     # Intel Mac
    ]

    for path in known_paths:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path

    resolved = shutil.which("brew")
    if resolved:
        return resolved

    return None


def is_ghostscript_installed() -> str | None:
    """Return the Ghostscript binary path if installed, None otherwise."""
    known_paths = [
        "/opt/homebrew/bin/gs",  # Apple Silicon (Homebrew)
        "/usr/local/bin/gs",     # Intel Mac (Homebrew)
        "/opt/local/bin/gs",     # MacPorts
    ]

    for path in known_paths:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path

    resolved = shutil.which("gs")
    if resolved:
        return resolved

    return None


class DependencyInstaller(QObject):
    """Installs missing dependencies via QProcess, emitting live output."""

    output_received = Signal(str)
    install_finished = Signal(bool, str)  # success, dependency_name

    def __init__(self):
        super().__init__()
        self._process = QProcess()
        self._process.setProcessChannelMode(QProcess.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_output)
        self._current_target = ""

    def install_homebrew(self) -> None:
        """Install Homebrew non-interactively via /bin/bash."""
        self._current_target = "Homebrew"

        env = QProcessEnvironment.systemEnvironment()
        env.insert("NONINTERACTIVE", "1")
        self._process.setProcessEnvironment(env)

        self._process.finished.connect(self._on_finished)
        self._process.start("/bin/bash", [
            "-c",
            'curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh | bash',
        ])

    def install_ghostscript(self) -> None:
        """Install Ghostscript via Homebrew."""
        self._current_target = "Ghostscript"
        brew_path = is_homebrew_installed()
        if not brew_path:
            self.install_finished.emit(False, "Ghostscript")
            return

        self._process.finished.connect(self._on_finished)
        self._process.start(brew_path, ["install", "ghostscript"])

    def cancel(self) -> None:
        if self._process.state() == QProcess.Running:
            self._process.kill()

    def _on_output(self) -> None:
        data = self._process.readAllStandardOutput()
        text = bytes(data).decode("utf-8", errors="replace")
        self.output_received.emit(text)

    def _on_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        self._process.finished.disconnect(self._on_finished)
        self.install_finished.emit(exit_code == 0, self._current_target)
