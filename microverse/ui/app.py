"""Entry point: python -m microverse.ui.app"""
from __future__ import annotations

import sys

import pyqtgraph as pg
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from .main_window import MainWindow
from .style import STYLESHEET


def dark_palette() -> QPalette:
    pal = QPalette()
    for role, col in [(QPalette.Window, "#161b22"), (QPalette.WindowText, "#e6edf3"), (QPalette.Base, "#0d1117"),
                      (QPalette.AlternateBase, "#161b22"), (QPalette.Text, "#e6edf3"), (QPalette.Button, "#21262d"),
                      (QPalette.ButtonText, "#e6edf3"), (QPalette.Highlight, "#1f6feb"),
                      (QPalette.HighlightedText, "#ffffff"), (QPalette.ToolTipBase, "#21262d"),
                      (QPalette.ToolTipText, "#e6edf3"), (QPalette.Link, "#58a6ff")]:
        pal.setColor(role, QColor(col))
    return pal


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("MicroVerse")
    app.setStyle("Fusion")
    app.setPalette(dark_palette())
    app.setStyleSheet(STYLESHEET)
    pg.setConfigOptions(antialias=True, background="#0d1117", foreground="#c9d1d9")
    try:                                        # keep data/microverse.sqlite in step with the code
        from ..data import db
        db.seed_organisms(db.connect())
    except Exception as exc:                    # the app works without the database file
        print(f"organism database not refreshed: {exc}", file=sys.stderr)
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
