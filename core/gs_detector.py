import os
import shutil


def find_ghostscript() -> str | None:
    """Locate the Ghostscript binary on macOS.

    Scans default Homebrew paths for both Apple Silicon and Intel Macs,
    falls back to MacPorts, then checks PATH via shutil.which.
    Returns the absolute path if found, None otherwise.
    """
    known_paths = [
        "/opt/homebrew/bin/gs",  # Apple Silicon (Homebrew)
        "/usr/local/bin/gs",     # Intel Mac (Homebrew)
        "/opt/local/bin/gs",     # MacPorts
    ]

    for path in known_paths:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path

    # Last resort: search PATH
    resolved = shutil.which("gs")
    if resolved:
        return resolved

    return None
