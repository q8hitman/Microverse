"""Smoke test of the Prediction vs Reality page on a SCRATCH database (never the real one).

Freezes a yoghurt prediction, writes a synthetic example CSV, compares, and saves screenshots/v05_reality.png.
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["MICROVERSE_DB"] = str(Path(tempfile.mkdtemp()) / "scratch.sqlite")

import pyqtgraph as pg
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from microverse.core.scheduler import run
from microverse.data import db
from microverse.labs import get
from microverse.ui.app import dark_palette
from microverse.ui.style import STYLESHEET

lab = get("yogurt")
s = lab.scenarios[0]
cfg = lab.config(s.overrides)
tr = run(lab.model, cfg)
con = db.connect()
exp = db.save_experiment(con, "smoke", cfg)
db.freeze_prediction(con, cfg, {"lab": lab.key, "scenario": s.key, "outcome": lab.outcome(tr)[0]},
                     "Classic yoghurt reaches pH 4.6 in about 4.5 h", exp)

app = QApplication(sys.argv)
app.setStyle("Fusion"); app.setPalette(dark_palette()); app.setStyleSheet(STYLESHEET)
pg.setConfigOptions(antialias=True, background="#0d1117", foreground="#c9d1d9")
from microverse.ui.main_window import MainWindow

w = MainWindow(); w.resize(1600, 980); w.show()
QTimer.singleShot(500, w.open_reality)
QTimer.singleShot(1500, lambda: w.reality._example())
QTimer.singleShot(2500, lambda: w.reality._compare())
QTimer.singleShot(4000, lambda: w.grab().save(str(ROOT / "screenshots" / "v05_reality.png")))
QTimer.singleShot(4300, app.quit)
app.exec()
print("ok", os.environ["MICROVERSE_DB"])
