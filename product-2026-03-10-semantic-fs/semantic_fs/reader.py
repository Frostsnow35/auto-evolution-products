"""File reading and chunking utilities."""
import re
from pathlib import Path
from typing import Iterator

try:
    import PyPDF2
    HAS_PDF = True
except ImportError:
    HAS_PDF = False


TEXT_EXTENSIONS = {
    ".txt", ".md", ".rst", ".org",
    ".py", ".js", ".ts", ".go", ".rs", ".c", ".cpp", ".h",
    ".java", ".rb", ".sh", ".bash", ".zsh", ".fish",
    ".yaml", ".yml", ".toml", ".json", ".ini", ".cfg", ".conf",
    ".html", ".css", ".xml", ".csv", ".log",
    ".dockerfile", ".makefile",
}


def can_read(path: Path, max_mb: float = 10) -> bool:
    """Check if we should index this file."""
    if not path.is_file():
        return False
    if path.stat().st_size > max_mb * 1024 * 1024:
        return False
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        return True
    if suffix == ".pdf" and HAS_PDF:
        return True
    # Try sniffing: no extension but small file
    if suffix == "" and path.stat().st_size < 100_000:
        return True
    return False


def read_file(path: Path) -> str:
    """Read file content as text."""
    if path.suffix.lower() == ".pdf" and HAS_PDF:
        return _read_pdf(path)
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _read_pdf(path: Path) -> str:
    try:
        reader = PyPDF2.PdfReader(str(path))
        return "\n".join(
            page.extract_text() or "" for page in reader.pages
        )
    except Exception:
        return ""


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks by word count."""
    words = text.split()
    if not words:
        return []
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks
