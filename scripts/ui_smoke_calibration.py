"""Calibration dialog on a SCRATCH database (never the real one) → screenshots/v051_calibration*.png

Freezes a yoghurt prediction, writes the page's SYNTHETIC example CSV (the prediction delayed, plus noise),
fits muS, muL and alpha, freezes the fit as a new prediction and compares the new prediction with the same
file (which must show the "a fit, not a test" warning)."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["MICROVERSE_DB"] = str(Path(tempfile.mkdtemp()) / "scratch.sqlite")

import pyqtgraph as pg
from PySide6.QtWidgets import QApplication

from microverse.analysis import calibration as C
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
db.freeze_prediction(con, cfg, {"lab": lab.key, "scenario": s.key, "outcome": lab.outcome(tr)[0]},
                     "Classic yoghurt reaches pH 4.6 in about 4.5 h", db.save_experiment(con, "smoke", cfg))

app = QApplication(sys.argv)
app.setStyle("Fusion"); app.setPalette(dark_palette()); app.setStyleSheet(STYLESHEET)
pg.setConfigOptions(antialias=True, background="#0d1117", foreground="#c9d1d9")
from microverse.ui.calibration_dialog import CalibrationDialog
from microverse.ui.main_window import MainWindow

w = MainWindow(); w.resize(1600, 980); w.show()
w.open_reality()
page = w.reality
page._example()
cmap, series = page._validated()
dlg = CalibrationDialog(page.fp, page.lab, page.table, cmap, page.obs, series, page)
dlg.resize(1400, 860)
dlg.show()
res = C.calibrate(page.lab.model, page.fp.config, page.obs, series, dlg.chosen())
dlg._done(dlg.token, res)
app.processEvents()
print("fitted:", {p.symbol: round(p.value, 3) for p in res.parameters}, "warnings:", res.warnings)
print("saved dialog", dlg.grab().save(str(ROOT / "screenshots" / "v051_calibration.png")))

pid = C.freeze_calibrated(db.connect(), page.fp, res, page.table, cmap, page.lab, "test on batch B")
dlg.close()
page.refresh()
page.pred_combo.setCurrentIndex(page.pred_combo.findData(pid))
page._compare()
app.processEvents()
print("new prediction", pid, "warning shown:", "fit, not a test" in page.report.toPlainText())
print("saved page", w.grab().save(str(ROOT / "screenshots" / "v051_calibration_same_data.png")))
