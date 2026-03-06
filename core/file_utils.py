import os
import shutil

PDF_MAGIC_BYTES = b"%PDF"
MINIMUM_DISK_SPACE_MB = 50


def validate_pdf(file_path: str) -> tuple[bool, str]:
    """Check that the file exists, is readable, and starts with the PDF magic bytes.

    Returns (is_valid, error_message). error_message is empty when valid.
    """
    if not os.path.isfile(file_path):
        return False, f"File not found: {file_path}"

    if not os.access(file_path, os.R_OK):
        return False, f"File is not readable: {file_path}"

    try:
        with open(file_path, "rb") as f:
            header = f.read(8)
    except OSError as e:
        return False, f"Cannot read file: {e}"

    if not header.startswith(PDF_MAGIC_BYTES):
        return False, f"Not a valid PDF file: {file_path}"

    return True, ""


def check_disk_space(target_dir: str, required_mb: int = MINIMUM_DISK_SPACE_MB) -> bool:
    """Return True if the target directory has at least required_mb free."""
    stat = shutil.disk_usage(target_dir)
    free_mb = stat.free / (1024 * 1024)
    return free_mb >= required_mb


def generate_output_path(input_path: str) -> str:
    """Create an output path by inserting '_optimized' before the extension.

    If that file already exists, appends a numeric suffix.
    Example: report.pdf -> report_optimized.pdf
             report.pdf -> report_optimized_2.pdf (if first already exists)
    """
    directory = os.path.dirname(input_path)
    stem, ext = os.path.splitext(os.path.basename(input_path))
    base = f"{stem}_optimized{ext}"
    candidate = os.path.join(directory, base)

    counter = 2
    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{stem}_optimized_{counter}{ext}")
        counter += 1

    return candidate


def generate_temp_path(output_path: str) -> str:
    """Return a temporary path next to the intended output for atomic write."""
    return output_path + ".tmp"


def format_file_size(size_bytes: int) -> str:
    """Format bytes as a human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"

    for unit in ("KB", "MB", "GB"):
        size_bytes /= 1024
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"

    return f"{size_bytes:.1f} TB"


def compute_savings(original_bytes: int, optimized_bytes: int) -> tuple[str, float]:
    """Return a human-readable savings string and the percentage reduced.

    Negative percentage means the file grew larger.
    """
    if original_bytes == 0:
        return "0 B", 0.0

    diff = original_bytes - optimized_bytes
    percentage = (diff / original_bytes) * 100
    return format_file_size(abs(diff)), percentage


# Rough typical compression ratios per Ghostscript preset.
# Real results vary wildly depending on content (images vs text,
# already-compressed assets, etc.), but these give a useful ballpark.
_ESTIMATED_REDUCTION = {
    "/screen":   0.70,   # ~70% smaller
    "/ebook":    0.50,   # ~50% smaller
    "/printer":  0.30,   # ~30% smaller
    "/prepress": 0.10,   # ~10% smaller
}


def estimate_savings(original_bytes: int, preset: str) -> tuple[int, str, float]:
    """Estimate the output size for a given quality preset.

    Returns (estimated_bytes, savings_text, savings_percent).
    These are rough estimates — actual results depend on PDF content.
    """
    ratio = _ESTIMATED_REDUCTION.get(preset, 0.50)
    saved_bytes = int(original_bytes * ratio)
    estimated_bytes = original_bytes - saved_bytes
    percentage = ratio * 100
    return estimated_bytes, format_file_size(saved_bytes), percentage
