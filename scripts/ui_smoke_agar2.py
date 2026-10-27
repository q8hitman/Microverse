"""Virtual Agar v0.5.1 screenshots (two organisms, lactic acid, pH indicator, finer spot grid).
Runs each plate synchronously, then shows it in the page → screenshots/v051_agar_*.png"""
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pyqtgraph as pg
from PySide6.QtWidgets import QApplication

from microverse.agar.model import AgarParams, Plating, simulate
from microverse.ui.app import dark_palette
from microverse.ui.style import STYLESHEET

app = QApplication(sys.argv)
app.setStyle("Fusion"); app.setPalette(dark_palette()); app.setStyleSheet(STYLESHEET)
pg.setConfigOptions(antialias=True, background="#0d1117", foreground="#c9d1d9")
from microverse.ui.main_window import MainWindow

w = MainWindow(); w.resize(1600, 980); w.show()
w.open_agar()
a = w.agar
(ROOT / "screenshots").mkdir(exist_ok=True)


def show(name, params, plating, hours, indicator=False, marks=False):
    a.org.setCurrentIndex(a.org.findData(params.organism))
    a.org2.setCurrentIndex(a.org2.findData(params.organism2))
    a.mode.setCurrentIndex(a.mode.findData(plating.mode))
    a.buf.setValue(params.buffering)
    a.nut.setValue(params.nutrient)
    a.soft.setValue(params.softness)
    a.dens.setValue(math.log10(plating.density_cfu_ml))
    a.dil.setValue(plating.dilution_exp)
    a.vol.setValue(plating.volume_ml)
    a.mix.setValue(round(plating.mix2 * 100))
    a.gap.setValue(plating.spot_gap_mm)
    a.delay.setValue(int(plating.delay2_h))
    a.tend.setValue(hours)
    t0 = time.time()
    run = simulate(params, plating, hours, 120)
    print(f"{name}: simulated in {time.time() - t0:.1f} s, grid {run.grid}")
    a._done(None, run)
    a.timer.stop()
    a.play.setText("▶")
    a.slider.setValue(a.slider.maximum())
    a.chk.setChecked(marks)
    a.chk_ind.setChecked(indicator)
    app.processEvents()
    print("saved", name, w.grab().save(str(ROOT / "screenshots" / name)))


overlay = Plating(density_cfu_ml=3e9, dilution_exp=6, volume_ml=0.1, mix2=0.95, delay2_h=24)
show("v051_agar_lactic_overlay.png", AgarParams(organism="llactis", organism2="ecoli", seed=3), overlay, 48,
     indicator=True)
show("v051_agar_lactic_overlay_buffered.png", AgarParams(organism="llactis", organism2="ecoli", seed=3, buffering=4),
     overlay, 48, indicator=True)
show("v051_agar_two_spots.png", AgarParams(organism="llactis", organism2="bsubtilis"),
     Plating(mode="spot", spot_gap_mm=14, delay2_h=24), 48, indicator=True)
show("v051_agar_mixed_count.png", AgarParams(organism="ecoli", organism2="scerevisiae", seed=5),
     Plating(density_cfu_ml=3e8, dilution_exp=6, volume_ml=0.1, mix2=0.4), 24, marks=True)
show("v051_agar_lobed_fine.png", AgarParams(organism="bsubtilis", nutrient=0.4, softness=0.7), Plating(mode="spot"), 200)
print("ok")
