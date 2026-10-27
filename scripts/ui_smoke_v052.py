"""v0.5.2 screenshots: School mode workspace and spread plates whose colonies start from a few cells.
→ screenshots/v052_*.png"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pyqtgraph as pg
from PySide6.QtWidgets import QApplication

from microverse import i18n
from microverse.agar.model import AgarParams, Plating, simulate
from microverse.ui.app import dark_palette
from microverse.ui.style import STYLESHEET

app = QApplication(sys.argv)
app.setStyle("Fusion"); app.setPalette(dark_palette()); app.setStyleSheet(STYLESHEET)
pg.setConfigOptions(antialias=True, background="#0d1117", foreground="#c9d1d9")
from microverse.labs import fixed_labs
from microverse.ui.main_window import MainWindow

(ROOT / "screenshots").mkdir(exist_ok=True)
w = MainWindow(); w.resize(1600, 980); w.show()
w.change_mode("school")
lab = list(fixed_labs())[0]
w.open_lab(lab, lab.scenarios[0])
for _ in range(40):
    app.processEvents()
    QApplication.instance().thread().msleep(50)
print("saved", w.grab().save(str(ROOT / "screenshots" / "v052_school_workspace.png")))
w.change_mode("research")

w.open_agar()
a = w.agar
for name, hours in (("v052_agar_ecoli_12h.png", 12), ("v052_agar_ecoli_24h.png", 24)):
    pl = Plating(density_cfu_ml=6e8, dilution_exp=6, volume_ml=0.1)
    a.tend.setValue(hours)
    run = simulate(AgarParams(organism="ecoli", seed=4), pl, hours, 60)
    a._done(None, run)
    a.timer.stop()
    a.slider.setValue(a.slider.maximum())
    app.processEvents()
    print("saved", name, w.grab().save(str(ROOT / "screenshots" / name)))
print("ok")
