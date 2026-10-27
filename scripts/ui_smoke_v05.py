"""v0.5 visual smoke test: plays each lab in each display mode and saves microscope screenshots.

Usage:  .venv\\Scripts\\python scripts\\ui_smoke_v05.py   → screenshots/v05_*.png
It also records the frame time of the microscope widget (paint) for the performance notes.
"""
import sys
import time
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

w = MainWindow(); w.resize(1600, 980); w.show()
steps, t = [], [0]
paint_ms = {}


def at(delay, fn):
    t[0] += delay
    steps.append((t[0], fn))


def shot(name, whole=False):
    (w if whole else w.workspace.micro).grab().save(str(OUT / name))


def mode(m):
    i = w.workspace.mode_combo.findData(m)
    w.workspace.mode_combo.setCurrentIndex(i)


def play(on=True):
    if w.workspace.playing != on:
        w.workspace._toggle_play()


def time_paint(key):
    micro = w.workspace.micro
    t0 = time.perf_counter()
    for _ in range(20):
        micro.repaint()
    paint_ms[key] = (time.perf_counter() - t0) / 20 * 1000


labs = [
    ("chem", get("chemostat")),
    ("yog", get("yogurt")),
    ("pond", community_lab(("chlorella", "tetrahymena", "brachionus"), "pond")),
    ("mix", community_lab(("ecoli", "scerevisiae", "aoryzae", "paramecium", "euglena"), "custom")),
    ("pickle", community_lab(("llactis", "lplantarum"), "vegetable")),
]
for key, lab in labs:
    at(400, lambda lab=lab: w.open_lab(lab, lab.scenarios[0]))
    at(2500, lambda: play(True))
    for j in range(4):                                  # a short sequence: continuity is visible frame to frame
        at(700, lambda key=key, j=j: shot(f"v05_{key}_seq{j}.png"))
    at(200, lambda: play(False))
    at(300, lambda key=key: time_paint(key))
    for m in ("microscope", "explain"):
        at(300, lambda m=m: mode(m))
        at(900, lambda key=key, m=m: shot(f"v05_{key}_{m}.png"))
    at(200, lambda: mode("natural"))
at(300, lambda: shot("v05_full_window.png", whole=True))
at(300, lambda: (print("paint ms per frame:", {k: round(v, 1) for k, v in paint_ms.items()}), app.quit()))
for ms, fn in steps:
    QTimer.singleShot(ms, fn)
app.exec()
print("ok")
