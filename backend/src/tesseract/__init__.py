"""Tesseract Controller – zentrale Verwaltung für Caddy-Nodes."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("tesseract")
except PackageNotFoundError:  # pragma: no cover – nur bei nicht installiertem Paket
    __version__ = "0.0.0"


def main() -> None:
    """Einstiegspunkt für `uv run tesseract`."""
    from tesseract.cli import run

    run()
