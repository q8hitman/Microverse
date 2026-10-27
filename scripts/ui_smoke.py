"""UI smoke test: opens each screen and lab, captures screenshots to screenshots/."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "screenshots"
OUT.mkdir(exist_ok=True)

import pyqtgraph as pg
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from microverse.labs import community_lab, get
from microverse.ui.app import dark_palette
from microverse.ui.style import STYLESHEET

app = QApplication(sys.argv)
app.setStyle("Fusion"); app.setPalette(dark_palette()); app.setStyleSheet(STYLESHEET)
pg.setConfigOptions(antialias=True, background="#0d1117", foreground="#c9d1d9")
from microverse.ui.main_window import MainWindow

w = MainWindow(); w.show()
steps = []
at = lambda ms, fn: steps.append((ms, fn))
shot = lambda n: w.grab().save(str(OUT / n))
mix = community_lab(("chlorella", "ecoli", "tetrahymena", "brachionus", "aoryzae"), "custom")
pond = community_lab(("chlorella", "tetrahymena", "brachionus"), "pond")


def library_by_function():
    w.stack.setCurrentWidget(w.library)
    w.library.findChild(type(w.library.layout().itemAt(3).widget())).setCurrentIndex(1) \
        if False else None
    from PySide6.QtWidgets import QTabWidget
    w.library.findChild(QTabWidget).setCurrentIndex(1)


def whos_who():
    from PySide6.QtWidgets import QTabWidget
    tabs = [t for t in w.workspace.findChildren(QTabWidget) if t.count() == 2]
    tabs[0].setCurrentIndex(1)


at(900, lambda: shot("01_start.png"))
at(1100, library_by_function)
at(2200, lambda: shot("02_library_by_function.png"))
at(2400, lambda: w.open_lab(mix, mix.scenarios[0]))
at(4200, lambda: w.workspace._seek(40))
at(7500, lambda: shot("03_lab_two_panels.png"))
at(7700, whos_who)
at(8600, lambda: shot("04_whos_who.png"))
at(8800, lambda: w.change_language("ar"))
at(10000, lambda: w.open_lab(pond, pond.scenarios[0]))
at(11800, lambda: w.workspace._seek(80))
at(15000, lambda: shot("05_arabic_rtl.png"))
at(15200, whos_who)
at(16200, lambda: shot("06_arabic_whos_who.png"))
at(16400, lambda: w.change_language("en"))
at(16800, app.quit)
for ms, fn in steps:
    QTimer.singleShot(ms, fn)
app.exec()
print("ok")
