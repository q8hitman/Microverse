"""Arabic screenshots of the v0.5.1 screens on a SCRATCH database → screenshots/v051_ar_*.png"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["MICROVERSE_DB"] = str(Path(tempfile.mkdtemp()) / "scratch.sqlite")

import pyqtgraph as pg
from PySide6.QtWidgets import QApplication

from microverse import i18n
from microverse.agar.model import AgarParams, Plating, simulate
from microverse.analysis import calibration as C
from microverse.core.scheduler import run
from microverse.data import db
from microverse.labs import get
from microverse.ui.app import dark_palette
from microverse.ui.style import STYLESHEET

lab = get("yogurt")
cfg = lab.config(lab.scenarios[0].overrides)
tr = run(lab.model, cfg)
con = db.connect()
db.freeze_prediction(con, cfg, {"lab": lab.key, "scenario": "classic", "outcome": lab.outcome(tr)[0]}, "ar",
                     db.save_experiment(con, "ar", cfg))
app = QApplication(sys.argv)
app.setStyle("Fusion"); app.setPalette(dark_palette()); app.setStyleSheet(STYLESHEET)
pg.setConfigOptions(antialias=True, background="#0d1117", foreground="#c9d1d9")
from microverse.ui.calibration_dialog import CalibrationDialog
from microverse.ui.main_window import MainWindow

w = MainWindow(); w.resize(1600, 980); w.show()
w.change_language("ar")
w.open_agar()
a = w.agar
a.org.setCurrentIndex(a.org.findData("llactis")); a.org2.setCurrentIndex(a.org2.findData("ecoli"))
r = simulate(AgarParams(organism="llactis", organism2="ecoli", seed=3),
             Plating(density_cfu_ml=3e9, dilution_exp=6, volume_ml=0.1, mix2=0.95, delay2_h=24), 48, 60)
a._done(None, r); a.timer.stop(); a.slider.setValue(a.slider.maximum()); a.chk_ind.setChecked(True)
app.processEvents()
print("agar", w.grab().save(str(ROOT / "screenshots" / "v051_ar_agar.png")))
w.open_reality()
page = w.reality
page._example()
cmap, series = page._validated()
dlg = CalibrationDialog(page.fp, page.lab, page.table, cmap, page.obs, series, page)
dlg.resize(1400, 860); dlg.show()
dlg._done(dlg.token, C.calibrate(page.lab.model, page.fp.config, page.obs, series, ["muS", "muL", "alpha", "buf"]))
app.processEvents()
print("dialog", dlg.grab().save(str(ROOT / "screenshots" / "v051_ar_calibration.png")))
dlg.close()
page._compare(); app.processEvents()
print("reality", w.grab().save(str(ROOT / "screenshots" / "v051_ar_reality.png")))
