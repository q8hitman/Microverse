"""Smoke test of the Virtual Agar page → screenshots/v05_agar_*.png"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pyqtgraph as pg
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from microverse.ui.app import dark_palette
from microverse.ui.style import STYLESHEET

app = QApplication(sys.argv)
app.setStyle("Fusion"); app.setPalette(dark_palette()); app.setStyleSheet(STYLESHEET)
pg.setConfigOptions(antialias=True, background="#0d1117", foreground="#c9d1d9")
from microverse.ui.main_window import MainWindow

w = MainWindow(); w.resize(1600, 980); w.show()
shot = lambda n: w.grab().save(str(ROOT / "screenshots" / n))
steps = []
t = [0]


def at(d, fn):
    t[0] += d
    steps.append((t[0], fn))


def setup(org, nut, soft, mode, dil, hours):
    a = w.agar
    a.org.setCurrentIndex(a.org.findData(org))
    a.nut.setValue(nut); a.soft.setValue(soft)
    a.mode.setCurrentIndex(a.mode.findData(mode))
    a.dil.setValue(dil); a.tend.setValue(hours)
    a._run()


def finish(name):
    a = w.agar
    a.timer.stop()
    a.slider.setValue(a.slider.maximum())
    a.chk.setChecked(name.endswith("count.png"))


at(400, w.open_agar)
at(300, lambda: setup("ecoli", 1.0, 1.0, "spread", 6, 72))
at(6000, lambda: finish("v05_agar_count.png"))
at(600, lambda: shot("v05_agar_count.png"))
at(300, lambda: setup("bsubtilis", 0.45, 0.7, "spot", 6, 600))
at(14000, lambda: finish("v05_agar_dendritic.png"))
at(600, lambda: shot("v05_agar_dendritic.png"))
at(300, lambda: setup("aoryzae", 1.0, 1.0, "spot", 6, 200))
at(9000, lambda: finish("v05_agar_mould.png"))
at(600, lambda: shot("v05_agar_mould.png"))
at(300, app.quit)
for ms, fn in steps:
    QTimer.singleShot(ms, fn)
app.exec()
print("ok")
