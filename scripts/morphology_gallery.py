"""Render every organism's morphology (resting, mid-division) in each display mode → screenshots/v05_gallery_*.png

A visual check that organisms do not all look like generic circles and rods, and that each one
divides in its own way. Not to scale between tiles (each tile is scaled to fit).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication

from microverse.library.morphology import SPECS
from microverse.library.organisms import ORGANISMS
from microverse.ui.specimen_paint import Look, paint_agent
from microverse.viz.population import DIVIDING, Agent

app = QApplication(sys.argv)
TILE = 150
keys = list(SPECS)
cols = 6
for mode, stain in (("natural", ""), ("microscope", ""), ("explain", "")):
    rows = (len(keys) + cols - 1) // cols
    img = QImage(cols * TILE * 2, rows * TILE, QImage.Format_ARGB32)
    img.fill(QColor("#0d1117"))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    for idx, key in enumerate(keys):
        spec = SPECS[key]
        for half, q in ((0, 0.0), (1, 0.6)):
            x0 = (idx % cols) * TILE * 2 + half * TILE
            y0 = (idx // cols) * TILE
            bg = QColor(150, 154, 158) if mode == "microscope" else QColor(236, 233, 224)
            p.fillRect(QRectF(x0 + 3, y0 + 3, TILE - 6, TILE - 22), bg)
            n = min(max(spec.max_chain, 1), 4)
            span = spec.length_um * (n if spec.shape in ("coccus", "ovococcus", "rod", "oval") else 1)
            if spec.shape in ("bell", "hypha"):
                span *= 2.0
            k = (TILE * 0.55) / max(span, 1e-6)
            a = Agent(1, 0.0, 0.0, -0.4 if spec.shape != "bell" else 0.0, n=n, variant=0.7, phase=1.3)
            if q:
                a.state, a.progress, a.gain = DIVIDING, q, (3 if spec.division == "autospores" else min(n, 2))
            p.save()
            p.translate(x0 + TILE / 2, y0 + (TILE - 20) / 2)
            if spec.shape == "hypha":
                p.translate(-TILE * 0.3, TILE * 0.1)
            elif spec.shape == "bell":
                p.translate(0, TILE * 0.3)
            paint_agent(p, spec, a, k, Look(mode, stain), {"eggs": 1})
            p.restore()
            p.setPen(QColor("#c9d1d9"))
            p.setFont(QFont("Segoe UI", 7))
            label = ORGANISMS[key].name.split(" subsp.")[0] if half == 0 else spec.division.replace("_", " ")
            p.drawText(QRectF(x0 + 2, y0 + TILE - 19, TILE - 4, 16), Qt.AlignCenter, label)
    p.end()
    out = ROOT / "screenshots" / f"v05_gallery_{mode}.png"
    img.save(str(out))
    print(out)
