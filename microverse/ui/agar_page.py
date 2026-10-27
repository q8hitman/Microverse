"""Virtual Agar page: plate a culture, watch colonies grow (time-lapse), count them."""
from __future__ import annotations

import html

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QPointF, QRectF, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QPushButton, QSizePolicy, QSlider, QSpinBox, QSplitter, QVBoxLayout, QWidget)

from ..agar.model import (DISH_MM, HOURS_PER_UNIT, ORGANISMS, AgarParams, AgarRun, Plating, fill_fraction,
                          radius_mm, simulate)
from ..i18n import L, is_ar
from ..library.organisms import ORGANISMS as DB
from .workers import Job

STATUS_EN = ("Qualitative, educational model of colony morphology (Kawasaki et al. 1997; Mimura et al. 2000). "
             "Space and time are dimensionless; the clock (1 unit ≈ 1 h) and the mm scale are assumed for display. "
             "Not calibrated: use it to explore how food and agar firmness shape colonies, and how plate counts work. "
             "Colonies grow about 3–5× larger than real colonies of the same age (a real E. coli colony is ≈2–3 mm "
             "across after a day), because one clock cannot fit both growth and colony shape.")
STATUS_AR = ("نموذج تعليمي نوعي لشكل المستعمرات (Kawasaki وزملاؤه 1997؛ Mimura وزملاؤه 2000). الزمن والمسافة بلا وحدات؛ "
             "الساعة (الوحدة ≈ ساعة) ومقياس المليمتر مفترضان للعرض. غير معاير: استخدمه لاستكشاف أثر الغذاء وصلابة الآجار "
             "على شكل المستعمرات، وطريقة عدّ المستعمرات. المستعمرات هنا أكبر بنحو 3–5 أضعاف من مستعمرات حقيقية بالعمر نفسه "
             "(مستعمرة الإشريكية القولونية الحقيقية ≈2–3 مم بعد يوم)، لأن ساعة واحدة لا تناسب النمو والشكل معاً.")


# Bromocresol purple, a common pH indicator in agar: purple above pH ≈ 6.8, yellow below ≈ 5.2.
BCP_PURPLE = np.array([122, 74, 140], np.float32)
BCP_YELLOW = np.array([214, 196, 74], np.float32)


def _colony_layer(f: np.ndarray, org) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(alpha, shade, colour) of one organism's colonies, from its density field."""
    from scipy import ndimage
    h = np.clip(f / 3.0, 0, 1.2)
    if org.texture in ("smooth", "pinpoint"):                               # glossy colonies are domes
        h = ndimage.gaussian_filter(np.clip(f / 1.5, 0, 1.0), 1.6) * 1.2
    gy, gx = np.gradient(h)
    shade = np.clip(0.78 + 2.2 * (-gx * 0.6 - gy * 0.8), 0.45, 1.25)       # light from the upper left
    alpha = np.clip((f - 0.08) / 0.5, 0, 1)
    if org.texture == "fuzzy":                                              # aerial hyphae: soft halo
        alpha = np.clip(ndimage.gaussian_filter(alpha, 1.2) * 1.3, 0, 1)
    if org.texture == "dry":                                                # wrinkled surface
        wr = ndimage.gaussian_filter(np.random.default_rng(3).standard_normal(f.shape), 0.8)
        shade = shade * (1 + 0.12 * wr * alpha)
    col = np.broadcast_to(np.array(org.colour, np.float32), f.shape + (3,)).copy()
    if org.texture == "fuzzy":                                              # older mycelium sporulates (greener)
        age = np.clip(f / 4.0, 0, 1)[..., None]
        col = col * (1 - 0.4 * age) + np.array([120, 150, 60], np.float32) * 0.4 * age
    return alpha, shade, col


def plate_image(run: AgarRun, i: int, explain: bool = False, indicator: bool = False) -> QImage:
    """Render frame i as a lit plate: agar colour, colonies shaded from their height (density).
    With two organisms each keeps its own colour and texture. `indicator`: the agar contains bromocresol purple,
    which turns from purple to yellow where lactic acid has spread (qualitative: acid level, not a computed pH)."""
    tot = run.frames[i].astype(np.float32)
    nut = run.nutrient[i].astype(np.float32)
    n = tot.shape[0]
    agar = np.array([206, 176, 112], np.float32)                           # nutrient agar, amber
    agar_poor = np.array([214, 196, 150], np.float32)
    rich = np.clip(nut / max(run.params.nutrient * 2.0, 1e-6), 0, 1)[..., None]
    base = agar_poor + (agar - agar_poor) * rich
    if indicator:
        acid = run.acid[i].astype(np.float32) if run.acid else np.zeros_like(tot)
        y = np.clip(acid / (0.6 * run.params.buffering), 0, 1)[..., None]
        base = 0.25 * base + 0.75 * (BCP_PURPLE * (1 - y) + BCP_YELLOW * y)
    if run.frames2:
        f2 = run.frames2[i].astype(np.float32)
        layers = [(np.maximum(tot - f2, 0), ORGANISMS[run.params.organism]), (f2, ORGANISMS[run.params.organism2])]
    else:
        layers = [(tot, ORGANISMS[run.params.organism])]
    rgb = base
    for f, org in layers:
        alpha, shade, col = _colony_layer(f, org)
        rgb = rgb * (1 - alpha[..., None]) + col * shade[..., None] * alpha[..., None]
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    a = np.full(run.mask.shape, 255, np.uint8)        # the dish outline is clipped smoothly by the painter
    arr = np.ascontiguousarray(np.dstack([rgb, a]))
    return QImage(arr.data, n, n, n * 4, QImage.Format_RGBA8888).copy()


class PlateView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.run: AgarRun | None = None
        self.i = 0
        self.explain = False
        self.indicator = False
        self.setMinimumSize(380, 380)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor("#0d1117"))
        side = min(self.width(), self.height()) - 30
        r = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)
        g = QRadialGradient(r.center(), side * 0.55)                          # bench shadow
        g.setColorAt(0.85, QColor(0, 0, 0, 120))
        g.setColorAt(1, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(r.adjusted(-12, -6, 12, 18))
        p.setBrush(QColor(225, 230, 235, 40))                                 # dish wall
        p.setPen(QPen(QColor(220, 228, 236, 170), 3))
        p.drawEllipse(r.adjusted(-6, -6, 6, 6))
        if self.run is None:
            p.setPen(QColor("#8b949e"))
            p.drawText(r, Qt.AlignCenter, L("Press “Plate and incubate”", "اضغط «ازرع واحضن»"))
            p.end()
            return
        img = plate_image(self.run, self.i, self.explain, self.indicator)
        from PySide6.QtGui import QPainterPath
        clip = QPainterPath()
        clip.addEllipse(r)
        p.save()
        p.setClipPath(clip)
        p.drawImage(r, img)
        p.restore()
        p.setPen(Qt.NoPen)                                                    # lid reflection
        hl = QRadialGradient(QPointF(r.x() + side * 0.3, r.y() + side * 0.25), side * 0.35)
        hl.setColorAt(0, QColor(255, 255, 255, 40))
        hl.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(hl)
        p.drawEllipse(r)
        k = side / DISH_MM
        if self.explain:                                                      # mark each counted colony
            from scipy import ndimage
            lab, n = self.run_labels()
            if n:
                cms = ndimage.center_of_mass(np.ones_like(lab), lab, range(1, n + 1))
                two = np.zeros(n, bool)
                if self.run.frames2:                                          # majority organism of each colony
                    idx = np.arange(1, n + 1)
                    two = (ndimage.sum(self.run.frames2[self.i].astype(float), lab, idx) >
                           0.5 * ndimage.sum(self.run.frames[self.i].astype(float), lab, idx))
                p.setBrush(Qt.NoBrush)
                p.setFont(QFont("Segoe UI", 7))
                px = side / self.run.grid
                for j, (cy, cx) in enumerate(cms):
                    c = QPointF(r.x() + (cx + 0.5) * px, r.y() + (cy + 0.5) * px)
                    if two[j]:                                                # organism 2: blue square
                        p.setPen(QPen(QColor(57, 135, 229), 1.5))
                        p.drawRect(QRectF(c.x() - 5.5, c.y() - 5.5, 11, 11))
                    else:                                                     # organism 1: green circle
                        p.setPen(QPen(QColor(63, 185, 80), 1.5))
                        p.drawEllipse(c, 6, 6)
                    if n <= 60:
                        p.drawText(c + QPointF(7, -4), str(j + 1))
        p.setPen(QPen(QColor(230, 230, 230), 3))                              # 10 mm scale bar
        p.drawLine(QPointF(r.right() - 10 * k, r.bottom() + 14), QPointF(r.right(), r.bottom() + 14))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(QRectF(r.right() - 10 * k - 20, r.bottom() + 16, 10 * k + 40, 14), Qt.AlignCenter, L("10 mm", "10 مم"))
        p.setPen(QColor("#e6edf3"))
        p.drawText(QRectF(r.x(), r.y() - 22, side, 18), Qt.AlignLeft | Qt.AlignVCenter,
                   L(f"t ≈ {self.run.times[self.i] * HOURS_PER_UNIT:.0f} h (assumed clock) · 90 mm dish",
                     f"t ≈ {self.run.times[self.i] * HOURS_PER_UNIT:.0f} ساعة (ساعة مفترضة) · طبق 90 مم"))
        p.end()

    def run_labels(self):
        from scipy import ndimage
        return ndimage.label((self.run.frames[self.i].astype(float) > 0.15) & self.run.mask)


class AgarPage(QWidget):
    back = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.run: AgarRun | None = None
        self.pool = QThreadPool.globalInstance()
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        head = QHBoxLayout()
        b = QPushButton("◀ " + L("Home", "الرئيسية"))
        b.setObjectName("link")
        b.clicked.connect(self.back)
        head.addWidget(b)
        t = QLabel(L("Virtual Agar — colonies on a plate", "الآجار الافتراضي – مستعمرات على طبق"))
        t.setObjectName("h1")
        head.addWidget(t, 1)
        root.addLayout(head)
        st = QLabel(L(STATUS_EN, STATUS_AR))
        st.setWordWrap(True)
        st.setStyleSheet("color:#e3b341")
        root.addWidget(st)
        split = QSplitter(Qt.Horizontal)

        left = QWidget()
        lv = QVBoxLayout(left)
        g = QGroupBox(L("Organism and medium", "الكائن والوسط"))
        f = QFormLayout(g)
        self.org = QComboBox()
        for k, o in ORGANISMS.items():
            self.org.addItem(L(DB[k].name, DB[k].name_ar), k)
            self.org.setItemData(self.org.count() - 1, L(o.note, o.note), Qt.ToolTipRole)
        f.addRow(L("Organism", "الكائن"), self.org)
        self.org2 = QComboBox()
        self.org2.addItem(L("— none —", "— لا يوجد —"), "")
        for k, o in ORGANISMS.items():
            self.org2.addItem(L(DB[k].name, DB[k].name_ar), k)
            self.org2.setItemData(self.org2.count() - 1, L(o.note, o.note), Qt.ToolTipRole)
        self.org2.setToolTip(L("Optional second organism on the same plate. They share the food; lactic acid "
                               "bacteria also release acid that spreads through the agar.",
                               "كائن ثانٍ اختياري على الطبق نفسه. يتقاسمان الغذاء، وبكتيريا حمض اللاكتيك تطلق حمضاً "
                               "ينتشر في الآجار."))
        f.addRow(L("Second organism", "الكائن الثاني"), self.org2)
        self.nut = QDoubleSpinBox(decimals=2, minimum=0.05, maximum=3.0, singleStep=0.05, value=1.0)
        self.nut.setToolTip(L("Food in the agar, relative to a standard rich medium (1). Poor media (≈0.2) give "
                              "small, lobed colonies.", "الغذاء في الآجار نسبة إلى وسط غني قياسي (1). الأوساط "
                              "الفقيرة (≈0.2) تعطي مستعمرات صغيرة مفصّصة."))
        f.addRow(L("Nutrient (×rich)", "الغذاء (×غني)"), self.nut)
        self.soft = QDoubleSpinBox(decimals=2, minimum=0.2, maximum=3.0, singleStep=0.1, value=1.0)
        self.soft.setToolTip(L("1 = standard 1.5 % agar. Softer agar (>1) lets cells spread; harder agar (<1) holds "
                               "them back.", "1 = آجار قياسي 1.5٪. الآجار الأطرى (>1) يسمح بالانتشار، والأصلب (<1) يعيقه."))
        f.addRow(L("Agar softness", "طراوة الآجار"), self.soft)
        self.buf = QDoubleSpinBox(decimals=1, minimum=0.5, maximum=8.0, singleStep=0.5, value=1.0)
        self.buf.setToolTip(L("How strongly the agar resists acid (1 = ordinary nutrient agar). A phosphate-buffered "
                              "agar (higher value) protects acid-sensitive organisms from lactic acid.",
                              "مدى مقاومة الآجار للحمض (1 = آجار مغذٍّ عادي). الآجار المنظَّم بالفوسفات (قيمة أعلى) يحمي "
                              "الكائنات الحساسة للحمض من حمض اللاكتيك."))
        f.addRow(L("Buffering", "التنظيم (البفر)"), self.buf)
        lv.addWidget(g)
        g2 = QGroupBox(L("Plating", "الزراعة"))
        f2 = QFormLayout(g2)
        self.mode = QComboBox()
        self.mode.addItem(L("Spread plate (count colonies)", "زراعة بالنشر (عدّ المستعمرات)"), "spread")
        self.mode.addItem(L("Central spot (watch one colony)", "نقطة في المنتصف (مستعمرة واحدة)"), "spot")
        f2.addRow(L("Method", "الطريقة"), self.mode)
        self.dens = QDoubleSpinBox(decimals=1, minimum=1.0, maximum=12.0, singleStep=0.1, value=8.0, prefix="10^",
                                   suffix=L(" CFU/mL", " CFU/مل"))
        f2.addRow(L("Culture density", "كثافة المزرعة"), self.dens)
        self.dil = QSpinBox(minimum=0, maximum=10, value=6, prefix="10^-")
        f2.addRow(L("Dilution plated", "التخفيف المزروع"), self.dil)
        self.vol = QDoubleSpinBox(decimals=2, minimum=0.01, maximum=1.0, singleStep=0.05, value=0.1, suffix=L(" mL", " مل"))
        f2.addRow(L("Volume spread", "الحجم المنشور"), self.vol)
        self.mix = QSpinBox(minimum=1, maximum=99, value=50, suffix=" %")
        self.mix.setToolTip(L("Share of the plated cells that are the second organism.",
                              "نسبة الخلايا المزروعة التي تتبع الكائن الثاني."))
        f2.addRow(L("Second organism share", "نسبة الكائن الثاني"), self.mix)
        self.gap = QDoubleSpinBox(decimals=0, minimum=4, maximum=60, singleStep=2, value=16, suffix=L(" mm", " مم"))
        f2.addRow(L("Distance between spots", "المسافة بين النقطتين"), self.gap)
        self.delay = QSpinBox(minimum=0, maximum=200, value=0, suffix=L(" h", " ساعة"))
        self.delay.setToolTip(L("Add the second organism this long after the first (a deferred test: the first one "
                                "has time to grow and release acid before its neighbour arrives).",
                                "أضف الكائن الثاني بعد هذه المدة من الأول (اختبار مؤجَّل: يجد الأول وقتاً لينمو ويطلق "
                                "الحمض قبل وصول جاره)."))
        f2.addRow(L("Add second organism after", "أضف الكائن الثاني بعد"), self.delay)
        self.expect = QLabel()
        f2.addRow(L("Expected colonies", "المستعمرات المتوقعة"), self.expect)
        self.org2.currentIndexChanged.connect(self._update_expect)
        for w in (self.dens, self.dil, self.vol):
            w.valueChanged.connect(self._update_expect)
        self.mode.currentIndexChanged.connect(self._update_expect)
        lv.addWidget(g2)
        g3 = QGroupBox(L("Incubation", "الحضانة"))
        f3 = QFormLayout(g3)
        self.tend = QSpinBox(minimum=6, maximum=1500, value=24, suffix=L(" h", " ساعة"))
        f3.addRow(L("Incubate for", "مدة الحضانة"), self.tend)
        self.seed = QSpinBox(minimum=0, maximum=99999, value=1)
        f3.addRow(L("Random seed", "البذرة العشوائية"), self.seed)
        lv.addWidget(g3)
        self.btn = QPushButton(L("Plate and incubate", "ازرع واحضن"))
        self.btn.setObjectName("primary")
        self.btn.clicked.connect(self._run)
        lv.addWidget(self.btn)
        self.busy = QLabel()
        lv.addWidget(self.busy)
        lv.addStretch(1)
        split.addWidget(left)

        mid = QWidget()
        mv = QVBoxLayout(mid)
        self.view = PlateView()
        mv.addWidget(self.view, 1)
        bar = QHBoxLayout()
        self.play = QPushButton("▶")
        self.play.clicked.connect(self._toggle)
        bar.addWidget(self.play)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.valueChanged.connect(self._seek)
        bar.addWidget(self.slider, 1)
        self.chk = QCheckBox(L("Mark counted colonies", "علّم المستعمرات المعدودة"))
        self.chk.toggled.connect(lambda v: (setattr(self.view, "explain", v), self.view.update()))
        bar.addWidget(self.chk)
        self.chk_ind = QCheckBox(L("pH indicator in agar", "كاشف pH في الآجار"))
        self.chk_ind.setToolTip(L("Show the agar as if it contained bromocresol purple: it turns yellow where lactic "
                                  "acid has spread. Qualitative (acid level, not a computed pH).",
                                  "اعرض الآجار كأنه يحتوي كاشف البروموكريزول الأرجواني: يصفرّ حيث انتشر حمض اللاكتيك. "
                                  "نوعي (مستوى الحمض وليس pH محسوباً)."))
        self.chk_ind.toggled.connect(lambda v: (setattr(self.view, "indicator", v), self.view.update()))
        bar.addWidget(self.chk_ind)
        mv.addLayout(bar)
        split.addWidget(mid)

        right = QWidget()
        rv = QVBoxLayout(right)
        self.readout = QLabel()
        self.readout.setWordWrap(True)
        self.readout.setTextFormat(Qt.RichText)
        rv.addWidget(self.readout)
        self.plot = pg.PlotWidget()
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        self.plot.setLabel("bottom", L("time (h, assumed)", "الزمن (ساعة، مفترض)"))
        self.plot.addLegend(offset=(-8, 8))
        rv.addWidget(self.plot, 1)
        split.addWidget(right)
        split.setSizes([330, 640, 420])
        root.addWidget(split, 1)
        self.timer = QTimer(self, interval=80, timeout=self._advance)
        self._update_expect()

    # ------------------------------------------------------------------
    def _plating(self) -> Plating:
        return Plating(self.mode.currentData(), 10 ** self.dens.value(), self.dil.value(), self.vol.value(),
                       mix2=self.mix.value() / 100, spot_gap_mm=self.gap.value(), delay2_h=self.delay.value())

    def _update_expect(self):
        pl = self._plating()
        two = bool(self.org2.currentData())
        self.mix.setEnabled(two and pl.mode == "spread")
        self.gap.setEnabled(two and pl.mode == "spot")
        self.delay.setEnabled(two)
        if pl.mode == "spot":
            self.expect.setText(L("2 spots", "نقطتان") if two else L("1 spot", "نقطة واحدة"))
            return
        e = pl.expected_colonies
        hint = (L("ideal for counting (30–300)", "مثالي للعد (30–300)") if 30 <= e <= 300 else
                L("too many to count reliably (TNTC)", "أكثر من أن تُعد بدقة") if e > 300 else
                L("too few for a reliable count", "أقل من أن يكون العد موثوقاً"))
        self.expect.setText(f"{e:,.1f} · {hint}")

    def _run(self):
        params = AgarParams(organism=self.org.currentData(), nutrient=self.nut.value(), softness=self.soft.value(),
                            seed=self.seed.value(), organism2=self.org2.currentData() or "",
                            buffering=self.buf.value())
        pl = self._plating()
        if pl.mode == "spread" and pl.expected_colonies > 3000:
            self.busy.setText(L("More than 3000 colonies expected: dilute further (a lawn would form).",
                                "أكثر من 3000 مستعمرة متوقعة: خفّف أكثر (ستتكون طبقة كاملة)."))
            return
        self.btn.setEnabled(False)
        self.busy.setText(L("incubating…", "جارٍ التحضين…"))
        job = Job(None, simulate, params, pl, self.tend.value() / HOURS_PER_UNIT, 120, with_progress=True)
        job.signals.progress.connect(lambda i, n: self.busy.setText(
            L(f"incubating… {100 * i // max(n, 1)} %", f"جارٍ التحضين… {100 * i // max(n, 1)}٪")))
        job.signals.done.connect(self._done)
        job.signals.failed.connect(lambda _t, tb: (self.btn.setEnabled(True), self.busy.setText(tb[-300:])))
        self.pool.start(job)

    def _done(self, _token, run: AgarRun):
        self.btn.setEnabled(True)
        self.busy.setText("")
        self.run = run
        self.view.run = run
        self.slider.setMaximum(len(run.frames) - 1)
        self.slider.setValue(0)
        times = np.array(run.times) * HOURS_PER_UNIT
        radii = [radius_mm(run, i) for i in range(len(run.frames))]
        self.plot.clear()
        if run.frames2:
            by = np.array([run.counts_by_species(i) for i in range(len(run.frames))])
            o1, o2 = DB[run.params.organism], DB[run.params.organism2]
            self.plot.plot(times, by[:, 0], pen=pg.mkPen("#3fb950", width=2),
                           name=L(f"{o1.name} colonies", f"مستعمرات {o1.name_ar}"))
            self.plot.plot(times, by[:, 1], pen=pg.mkPen("#3987e5", width=2),
                           name=L(f"{o2.name} colonies", f"مستعمرات {o2.name_ar}"))
        else:
            counts = [run.counts(i)[0] for i in range(len(run.frames))]
            self.plot.plot(times, counts, pen=pg.mkPen("#3987e5", width=2),
                           name=L("colonies visible", "المستعمرات المرئية"))
        self.plot.plot(times, radii, pen=pg.mkPen("#199e70", width=2), name=L("largest colony radius (mm)",
                                                                              "نصف قطر أكبر مستعمرة (مم)"))
        self._toggle(force=True)

    def _toggle(self, force=False):
        if self.run is None:
            return
        if force or not self.timer.isActive():
            if self.slider.value() >= self.slider.maximum():
                self.slider.setValue(0)
            self.timer.start()
            self.play.setText("⏸")
        else:
            self.timer.stop()
            self.play.setText("▶")

    def _advance(self):
        if self.slider.value() >= self.slider.maximum():
            self._toggle()
            return
        self.slider.setValue(self.slider.value() + 1)

    def _seek(self, i):
        if self.run is None:
            return
        self.view.i = i
        self.view.update()
        r = self.run
        n, sizes = r.counts(i)
        pl = r.plating
        t = r.times[i] * HOURS_PER_UNIT
        lines = [f"<h3>{L('Plate readout', 'قراءة الطبق')}</h3>",
                 L(f"Time ≈ <b>{t:.0f} h</b>", f"الزمن ≈ <b>{t:.0f} ساعة</b>"),
                 L(f"Colonies visible: <b>{n}</b>", f"المستعمرات المرئية: <b>{n}</b>")]
        if pl.mode == "spread":
            back = r.back_calculated_cfu(i)
            true = pl.density_cfu_ml
            lines += [
                L(f"Cells that landed on the plate (Poisson draw): {r.started} (expected {pl.expected_colonies:.1f})",
                  f"الخلايا التي سقطت على الطبق (سحب بواسون): {r.started} (المتوقع {pl.expected_colonies:.1f})"),
                L(f"Back-calculated density: <b>{back:.3g} CFU/mL</b> = colonies ÷ (10^-{pl.dilution_exp} × "
                  f"{pl.volume_ml:g} mL); true culture {true:.3g} CFU/mL ({(back / true - 1) * 100:+.0f}%)",
                  f"الكثافة المحسوبة: <b>{back:.3g} CFU/مل</b> = المستعمرات ÷ (10^-{pl.dilution_exp} × {pl.volume_ml:g} مل)؛ "
                  f"المزرعة الحقيقية {true:.3g} ({(back / true - 1) * 100:+.0f}٪)"),
            ]
            if r.started and n < r.started:
                acid_en = ", or held back by lactic acid" if r.acid else ""
                acid_ar = "، أو أوقفها حمض اللاكتيك" if r.acid else ""
                lines.append(L(f"<span style='color:#e3b341'>{r.started - n} colonies are hidden: still too small to "
                               f"see, grown into a neighbour (counted as one){acid_en}.</span>",
                               f"<span style='color:#e3b341'>{r.started - n} مستعمرة غير ظاهرة: ما زالت صغيرة، أو اندمجت "
                               f"مع جارتها (تُعد واحدة){acid_ar}.</span>"))
        if r.frames2:
            a, b = r.counts_by_species(i)
            n1, n2 = DB[r.params.organism], DB[r.params.organism2]
            lines.append(L(f"● {html.escape(n1.name)}: <b>{a}</b> · ■ {html.escape(n2.name)}: <b>{b}</b> "
                           f"(planted {r.started - r.started2} and {r.started2})",
                           f"● {html.escape(n1.name_ar)}: <b>{a}</b> · ■ {html.escape(n2.name_ar)}: <b>{b}</b> "
                           f"(زُرع {r.started - r.started2} و{r.started2})"))
            if pl.delay2_h:
                lines.append(L(f"The second organism was added after {pl.delay2_h:g} h.",
                               f"أضيف الكائن الثاني بعد {pl.delay2_h:g} ساعة."))
        if r.acid:
            h = r.acid[i].astype(float)
            share = float(((h > 0.5 * r.params.buffering) & r.mask).sum() / r.mask.sum())
            lines.append(L(f"Lactic acid has spread through <b>{share * 100:.0f}%</b> of the agar at a level that stops "
                           "acid-sensitive bacteria such as E. coli. Tick “pH indicator” to see it.",
                           f"انتشر حمض اللاكتيك في <b>{share * 100:.0f}٪</b> من الآجار بمستوى يوقف البكتيريا الحساسة "
                           "للحمض مثل الإشريكية القولونية. فعّل «كاشف pH» لرؤيته."))
        if n:
            fill = fill_fraction(r, i) if pl.mode == "spot" else float("nan")
            lines.append(L(f"Largest colony radius: {radius_mm(r, i):.1f} mm", f"نصف قطر أكبر مستعمرة: {radius_mm(r, i):.1f} مم"))
            if not np.isnan(fill):
                shape = (L("round", "مستديرة") if fill > 0.72 else L("lobed, irregular", "مفصّصة غير منتظمة"))
                lines.append(L(f"Shape: the largest colony fills {fill * 100:.0f}% of its disc — {shape}",
                               f"الشكل: أكبر مستعمرة تملأ {fill * 100:.0f}٪ من دائرتها – {shape}"))
        self.readout.setText(f"<div dir='{'rtl' if is_ar() else 'ltr'}'>" + "<br>".join(lines) + "</div>")
