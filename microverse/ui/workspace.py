"""Lab workspace: parameters, live microscope view, plots, scan, organisms and the explanation panel."""
from __future__ import annotations

import html
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QElapsedTimer, QThreadPool, QTimer, Qt, Signal
from PySide6.QtWidgets import (QButtonGroup, QFrame, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox,
                               QHBoxLayout, QInputDialog, QLabel, QMessageBox, QProgressBar, QPushButton,
                               QRadioButton, QScrollArea, QSlider, QSpinBox, QSplitter, QTabWidget, QTextBrowser,
                               QVBoxLayout, QWidget)

from ..analysis.interactions import analyse
from ..analysis.sensitivity import elasticities
from ..i18n import L, group as G, param_name, t as T
from ..core.parameters import Evidence
from ..core.scheduler import run
from ..core.trajectory import RunConfig
from ..data import db
from ..io import experiment
from ..labs.base import Lab, Scenario
from ..library.organisms import ORGANISMS
from .organism_card import OrganismCard
from .style import BORDER, PANEL, TEXT_2
from .workers import Job

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_COLOURS = {
    Evidence.MEASURED: "#3fb950", Evidence.LITERATURE_ESTIMATE: "#d29922", Evidence.FITTED: "#58a6ff",
    Evidence.DERIVED: "#a5d6ff", Evidence.ASSUMED: "#f85149", Evidence.CONTROL: "#8b949e",
}
EVIDENCE_TEXT = {
    Evidence.MEASURED: "measured", Evidence.LITERATURE_ESTIMATE: "literature estimate", Evidence.FITTED: "fitted",
    Evidence.DERIVED: "derived", Evidence.ASSUMED: "assumed (exploratory)", Evidence.CONTROL: "you control it",
}


ERR_EN = """The simulation could not be computed with these values.

Try: undo the last value you changed, or press "Reset to scenario values"."""
ERR_AR = """تعذّر حساب المحاكاة بهذه القيم.

جرّب: أرجع آخر قيمة غيّرتها، أو اضغط «إرجاع قيم السيناريو»."""
FREEZE_EN = """The prediction will be stored with a timestamp and can NOT be edited or deleted afterwards.
That is the point: it proves what you predicted before the experiment.

Freeze it now?"""
FREEZE_AR = """سيُحفظ التوقع مع وقت التسجيل ولا يمكن تعديله أو حذفه بعد ذلك.
وهذا هو المقصود: يثبت ما توقعته قبل التجربة.

هل تريد تجميده الآن؟"""


def _res(key: str) -> tuple[str, str]:
    from ..library.organisms import RESOURCES
    return RESOURCES[key]


class Workspace(QWidget):
    go_home = Signal()

    def __init__(self, lab: Lab, scenario: Scenario, parent=None):
        super().__init__(parent)
        self.lab = lab
        self.scenario = scenario
        self.model = lab.model
        self.pool = QThreadPool.globalInstance()
        self.traj = None
        self.sens = None
        self.inter = None
        self.cur_t = 0.0
        self.run_token = 0
        self.playing = False
        self._explain_dirty = True
        self.scene = lab.make_scene(1)
        self.spins: dict[str, QDoubleSpinBox] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.addWidget(self._header())
        split = QSplitter(Qt.Horizontal)
        split.addWidget(self._params_panel())
        split.addWidget(self._center())
        split.addWidget(self._explain_panel())
        split.setSizes([360, 800, 440])
        split.setStretchFactor(1, 1)
        root.addWidget(split, 1)

        self.debounce = QTimer(self, singleShot=True, interval=250, timeout=self.start_run)
        self.anim = QTimer(self, interval=33, timeout=self._tick)
        self.anim.start()
        self.explain_timer = QTimer(self, interval=300, timeout=self._refresh_explanation)
        self.explain_timer.start()
        self.apply_scenario(scenario)

    # ------------------------------------------------------------------ UI
    def _header(self):
        w = QWidget()
        w.setStyleSheet(f"background:{PANEL}; border:1px solid {BORDER}; border-radius:8px")
        h = QHBoxLayout(w)
        h.setContentsMargins(10, 6, 10, 6)
        home = QPushButton("◀ " + T("home"))
        home.setStyleSheet("border:none; color:#58a6ff")
        home.clicked.connect(self._home)
        h.addWidget(home)
        self.title_lbl = QLabel()
        self.title_lbl.setToolTip(L("The research question this scenario asks.", "السؤال البحثي لهذا السيناريو."))
        self.title_lbl.setStyleSheet("border:none")
        self.title_lbl.setWordWrap(True)
        h.addWidget(self.title_lbl, 1)
        self.outcome_lbl = QLabel("computing…")
        self.outcome_lbl.setStyleSheet("border:none; font-weight:600")
        self.outcome_lbl.setWordWrap(True)
        self.outcome_lbl.setMaximumWidth(460)
        h.addWidget(self.outcome_lbl)
        return w

    def _params_panel(self):
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 4, 0)
        sc = QGroupBox(T("scenario"))
        sl = QVBoxLayout(sc)
        self.sc_combo = QComboBox()
        for s in self.lab.scenarios:
            self.sc_combo.addItem(L(s.title, s.title_ar), s.key)
        self.sc_combo.currentIndexChanged.connect(
            lambda i: self.apply_scenario(self.lab.scenarios[i]) if self.lab.scenarios[i] is not self.scenario else None)
        sl.addWidget(self.sc_combo)
        self.reset_btn = QPushButton(L("Reset to scenario values", "إرجاع قيم السيناريو"))
        self.reset_btn.clicked.connect(lambda: self.apply_scenario(self.scenario))
        sl.addWidget(self.reset_btn)
        lay.addWidget(sc)

        params = self.model.default_parameters().params
        for title, syms in self.lab.param_groups:
            controlled = all(params[x].evidence == Evidence.CONTROL for x in syms)
            grp = QGroupBox()
            gl = QVBoxLayout(grp)
            gl.setContentsMargins(6, 4, 6, 4)
            toggle = QPushButton(("▾  " if controlled else "▸  ") + G(title))
            toggle.setObjectName("fold")
            toggle.setCheckable(True)
            toggle.setChecked(controlled)
            toggle.setToolTip(L("Show or hide these parameters. Organism traits are folded so the panel stays simple.",
                                "إظهار أو إخفاء هذه المعاملات. صفات الكائنات مطوية حتى تبقى اللوحة بسيطة."))
            body = QWidget()
            form = QFormLayout(body)
            form.setContentsMargins(0, 2, 0, 2)
            form.setLabelAlignment(Qt.AlignLeft)
            body.setVisible(controlled)
            toggle.toggled.connect(lambda on, b=body, t=toggle, n=G(title): (b.setVisible(on),
                                                                              t.setText(("▾  " if on else "▸  ") + n)))
            gl.addWidget(toggle)
            gl.addWidget(body)
            for sym in syms:
                prm = params[sym]
                sp = QDoubleSpinBox(decimals=3, minimum=prm.lower, maximum=prm.upper, value=prm.value)
                sp.setSingleStep(max((prm.upper - prm.lower) / 200, 0.001))
                sp.setSuffix(f"  {prm.unit}" if prm.unit not in ("–", "") else "")
                src = html.escape(prm.source.citation) if prm.source else "—"
                tip = (f"<b>{html.escape(param_name(prm))}</b><br>{html.escape(prm.description)}<br><br>"
                       f"<b>Evidence:</b> {EVIDENCE_TEXT[prm.evidence]}<br><b>Source:</b> {src}<br>"
                       f"<b>Checked against source:</b> {'yes' if prm.verified_against_source else 'not yet'}"
                       f"<br><b>Allowed range:</b> {prm.lower:g} – {prm.upper:g} {html.escape(prm.unit)}")
                sp.setToolTip(tip)
                sp.valueChanged.connect(self._params_changed)
                name = QLabel(f"<span style='color:{EVIDENCE_COLOURS[prm.evidence]}'>●</span> {html.escape(param_name(prm))}")
                name.setToolTip(tip)
                name.setWordWrap(True)
                form.addRow(name, sp)
                self.spins[sym] = sp
            lay.addWidget(grp)
        legend = QLabel(L("Dot colour = how trustworthy the value is: ", "لون النقطة = مدى موثوقية القيمة: ") + "  ".join(
            f"<span style='color:{EVIDENCE_COLOURS[e]}'>●</span> {EVIDENCE_TEXT[e]}"
            for e in (Evidence.CONTROL, Evidence.LITERATURE_ESTIMATE, Evidence.ASSUMED, Evidence.MEASURED)))
        legend.setWordWrap(True)
        legend.setStyleSheet(f"color:{TEXT_2}; font-size:8pt")
        lay.addWidget(legend)

        sim = QGroupBox(L("Simulation", "المحاكاة"))
        f2 = QFormLayout(sim)
        self.rb_det = QRadioButton(L("Deterministic (average behaviour)", "حتمي (السلوك المتوسط)"), checked=True)
        self.rb_sto = QRadioButton(L("Stochastic (random births/deaths)", "عشوائي (ولادات ووفيات عشوائية)"))
        grp_mode = QButtonGroup(self)
        for rb in (self.rb_det, self.rb_sto):
            grp_mode.addButton(rb)
            rb.toggled.connect(self._params_changed)
            f2.addRow(rb)
        self.seed = QSpinBox(minimum=0, maximum=10**6, value=1)
        self.volume = QDoubleSpinBox(decimals=1, minimum=0.5, maximum=5000, value=50, suffix="  mL")
        self.volume.setToolTip("Culture volume for the stochastic mode: smaller vessels → fewer individuals → more chance events.")
        self.t_end = QDoubleSpinBox(decimals=1, minimum=1, maximum=2000, value=self.lab.default_t_end,
                                    suffix=f"  {self.lab.time_unit}")
        for wdg in (self.seed, self.volume, self.t_end):
            wdg.valueChanged.connect(self._params_changed)
        f2.addRow(L("Random seed", "البذرة العشوائية"), self.seed)
        f2.addRow(L("Vessel volume", "حجم الوعاء"), self.volume)
        f2.addRow(L("Duration", "المدة"), self.t_end)
        if not self.lab.supports_stochastic:
            for wdg in (self.rb_sto, self.seed, self.volume):
                wdg.setEnabled(False)
            self.rb_sto.setText("Stochastic (not needed: populations are huge)")
        lay.addWidget(sim)

        actions = QGroupBox(L("Experiment", "التجربة"))
        al = QVBoxLayout(actions)
        for text, fn in [(L("🔒 Freeze prediction (before the real experiment)", "🔒 تجميد التوقع (قبل التجربة الحقيقية)"),
                          self._freeze_prediction),
                         (L("💾 Save experiment file…", "💾 حفظ ملف التجربة…"), self._save),
                         (L("📂 Open experiment file…", "📂 فتح ملف تجربة…"), self._open),
                         (L("⬇ Export data (CSV)…", "⬇ تصدير البيانات (CSV)…"), self._export_csv)]:
            b = QPushButton(text)
            b.clicked.connect(fn)
            al.addWidget(b)
        lay.addWidget(actions)
        self.hash_lbl = QLabel()
        self.hash_lbl.setStyleSheet(f"color:{TEXT_2}; font-size:8pt")
        self.hash_lbl.setWordWrap(True)
        lay.addWidget(self.hash_lbl)
        lay.addStretch(1)
        scroll = QScrollArea(widgetResizable=True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(box)
        scroll.setMinimumWidth(340)
        return scroll

    def _center(self):
        tabs = QTabWidget()
        live = QWidget()
        v = QVBoxLayout(live)
        v.setContentsMargins(4, 4, 4, 4)
        split = QSplitter(Qt.Vertical)
        self.micro = self.lab.make_widget(self.scene)
        split.addWidget(self.micro)
        plots = QWidget()
        ph = QHBoxLayout(plots)
        ph.setContentsMargins(0, 0, 0, 0)
        self.plot_widgets, self.curves, self.cursors = [], [], []
        first = None
        for panel in self.lab.plots:
            pw = pg.PlotWidget(title=panel.title)
            pw.setLabel("bottom", "time", self.lab.time_unit)
            pw.setLabel("left", panel.y_label)
            pw.showGrid(x=True, y=True, alpha=0.15)
            pw.setLogMode(y=panel.log_y)
            pw.getAxis("left").enableAutoSIPrefix(False)
            pw.addLegend(offset=(-8, 8), brush=pg.mkBrush(13, 17, 23, 200), pen=pg.mkPen(BORDER), labelTextSize="8pt")
            if first is None:
                first = pw
            else:
                pw.setXLink(first)
            for val, label in panel.ref_lines:
                pw.addItem(pg.InfiniteLine(pos=val, angle=0, pen=pg.mkPen("#8b949e", style=Qt.DotLine),
                                           label=label, labelOpts={"position": 0.92, "color": "#8b949e"}))
            cs = []
            for s in panel.series:
                cs.append((s, pw.plot([], [], name=s.label,
                                      pen=pg.mkPen(s.colour, width=2, style=Qt.DashLine if s.dashed else Qt.SolidLine))))
            cur = pg.InfiniteLine(angle=90, movable=True, pen=pg.mkPen("#ffffff", width=1))
            cur.sigDragged.connect(lambda l: self._seek(l.value(), source=l))
            pw.addItem(cur)
            self.cursors.append(cur)
            self.plot_widgets.append(pw)
            self.curves.append(cs)
            ph.addWidget(pw)
        split.addWidget(plots)
        split.setSizes([470, 330])
        v.addWidget(split, 1)
        bar = QHBoxLayout()
        self.btn_play = QPushButton("▶ " + T("play"))
        self.btn_play.setObjectName("primary")
        self.btn_play.clicked.connect(self._toggle_play)
        self.slider = QSlider(Qt.Horizontal, minimum=0, maximum=1000)
        self.slider.sliderMoved.connect(lambda v_: self._seek(v_ / 1000 * self._t_max()))
        unit = self.lab.time_unit
        self.speed = QDoubleSpinBox(decimals=2, minimum=0.01, maximum=100,
                                    value=2.0 if unit == "d" else 0.5, suffix=f"  {unit}/s")
        self.speed.setToolTip(L("Simulated time per real second during playback (time-lapse of growth and death)",
                                "الزمن المحاكى في كل ثانية حقيقية أثناء التشغيل (تسريع النمو والموت)"))
        self.btn_replay = QPushButton("↺ " + L("Replay", "إعادة"))
        self.btn_replay.setToolTip(L("Start again from time 0 with a fresh sample", "ابدأ من الزمن صفر بعينة جديدة"))
        self.btn_replay.clicked.connect(self._replay)
        self.time_lbl = QLabel()
        for wdg in (self.btn_play, self.btn_replay, self.slider, QLabel(T("speed")), self.speed, self.time_lbl):
            bar.addWidget(wdg, 1 if wdg is self.slider else 0)
        v.addLayout(bar)
        view = QHBoxLayout()
        from ..viz.specimen import MODE_LABELS, MODES
        view.addWidget(QLabel(L("View:", "العرض:")))
        self.mode_combo = QComboBox()
        for m in MODES:
            self.mode_combo.addItem(L(*MODE_LABELS[m]), m)
        self.mode_combo.setToolTip(L("Realistic: brightfield colours · Microscope: phase contrast (or Gram stain for "
                                     "smears) · Explanation: marks dividing, dying and eaten cells and who eats whom. "
                                     "All three show the same simulated state.",
                                     "واقعي: ألوان المجهر الضوئي · مجهري: تباين الطور (أو صبغة جرام) · الشرح: يعلّم "
                                     "الخلايا التي تنقسم أو تموت أو تُؤكل. الثلاثة تعرض نفس الحالة المحسوبة."))
        self.mode_combo.currentIndexChanged.connect(lambda _: self._set_mode())
        view.addWidget(self.mode_combo)
        view.addSpacing(16)
        view.addWidget(QLabel(L("Swimming:", "السباحة:")))
        self.motion_combo = QComboBox()
        for label, val in ((L("real speed", "السرعة الحقيقية"), 1.0), (L("½ speed", "نصف السرعة"), 0.5),
                           (L("¼ speed", "ربع السرعة"), 0.25), (L("still", "متوقفة"), 0.0)):
            self.motion_combo.addItem(label, val)
        self.motion_combo.setToolTip(L("How fast organisms swim on screen. Growth and division follow the playback "
                                       "speed instead.", "سرعة سباحة الكائنات على الشاشة. النمو والانقسام يتبعان "
                                       "سرعة التشغيل."))
        self.motion_combo.currentIndexChanged.connect(lambda _: setattr(self.scene, "motion_scale",
                                                                        self.motion_combo.currentData()))
        view.addWidget(self.motion_combo)
        view.addStretch(1)
        hint = QLabel(L("wheel = zoom · drag = pan · click = inspect", "العجلة = تكبير · السحب = تحريك · النقر = فحص"))
        hint.setObjectName("muted")
        view.addWidget(hint)
        v.addLayout(view)
        tabs.addTab(live, L("Live lab", "المختبر الحي"))

        if self.lab.scan_compute:
            scan = QWidget()
            sv = QVBoxLayout(scan)
            info = QLabel(self.lab.scan_info)
            info.setWordWrap(True)
            sv.addWidget(info)
            h = QHBoxLayout()
            self.btn_scan = QPushButton(L(f"▶ Run the {self.lab.scan_title.lower()} with these parameters",
                                          "▶ شغّل المسح بهذه المعاملات"))
            self.btn_scan.clicked.connect(self._run_scan)
            self.scan_prog = QProgressBar()
            h.addWidget(self.btn_scan)
            h.addWidget(self.scan_prog, 1)
            sv.addLayout(h)
            self.scan_plot = pg.PlotWidget()
            self.scan_plot.showGrid(x=True, y=True, alpha=0.15)
            self.scan_plot.addLegend(offset=(-8, 8), brush=pg.mkBrush(13, 17, 23, 200), pen=pg.mkPen(BORDER))
            sv.addWidget(self.scan_plot, 1)
            tabs.addTab(scan, self.lab.scan_title)

        if self.lab.supports_stochastic:
            rep = QWidget()
            rl = QVBoxLayout(rep)
            info = QLabel(L("Chance matters in small vessels. This runs the SAME settings many times in stochastic mode, "
                            "each with a different random seed, and reports how often each population went extinct "
                            "(with a 95% confidence interval) and the 5–95% envelope of the populations.",
                            "الصدفة مهمة في الأوعية الصغيرة. هذا يشغّل نفس الإعدادات عدة مرات بالوضع العشوائي، كل مرة ببذرة "
                            "مختلفة، ويبيّن كم مرة انقرض كل نوع (مع مجال ثقة 95٪) ومدى 5–95٪ للأعداد."))
            info.setWordWrap(True)
            rl.addWidget(info)
            h = QHBoxLayout()
            h.addWidget(QLabel(L("Replicates:", "عدد التكرارات:")))
            self.rep_n = QSpinBox(minimum=5, maximum=500, value=30)
            h.addWidget(self.rep_n)
            self.btn_rep = QPushButton("▶ " + L("Run replicates", "شغّل التكرارات"))
            self.btn_rep.clicked.connect(self._run_replicates)
            h.addWidget(self.btn_rep)
            self.rep_prog = QProgressBar()
            h.addWidget(self.rep_prog, 1)
            rl.addLayout(h)
            self.rep_plot = pg.PlotWidget()
            self.rep_plot.showGrid(x=True, y=True, alpha=0.15)
            self.rep_plot.addLegend(offset=(-8, 8), brush=pg.mkBrush(13, 17, 23, 200), pen=pg.mkPen(BORDER))
            self.rep_plot.setLabel("bottom", "time", self.lab.time_unit)
            rl.addWidget(self.rep_plot, 1)
            self.rep_text = QLabel()
            self.rep_text.setWordWrap(True)
            rl.addWidget(self.rep_text)
            tabs.addTab(rep, L("Replicates", "التكرارات"))

        orgs = QWidget()
        ov = QVBoxLayout(orgs)
        for k in self.lab.organisms:
            ov.addWidget(OrganismCard(ORGANISMS[k]))
        ov.addStretch(1)
        osc = QScrollArea(widgetResizable=True)
        osc.setWidget(orgs)
        tabs.addTab(osc, L("Organisms", "الكائنات"))

        about = QTextBrowser()
        about.setHtml(self._model_html())
        tabs.addTab(about, L("Model && assumptions", "النموذج والافتراضات"))
        return tabs

    def _explain_panel(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 0, 0, 0)
        lbl = QLabel(T("why"))
        lbl.setObjectName("h2")
        v.addWidget(lbl)
        hint = QLabel(L("Everything here is computed from the run you are watching — no stored text.",
                        "كل ما هنا محسوب من التجربة التي تشاهدها، وليس نصاً مخزناً."))
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color:{TEXT_2}; font-size:8pt")
        v.addWidget(hint)
        btns = QHBoxLayout()
        if self.lab.key == "community":
            self.btn_inter = QPushButton(L("⇄ Measure interactions", "⇄ قياس التفاعلات"))
            self.btn_inter.setToolTip(L("Re-runs each organism alone and each pair together, then compares the final "
                                        "biomass to see who helps or harms whom.",
                                        "يعيد تشغيل كل كائن لوحده وكل زوج معاً، ثم يقارن الكتلة النهائية لمعرفة من "
                                        "يفيد من ومن يضره."))
            self.btn_inter.clicked.connect(self._run_interactions)
            btns.addWidget(self.btn_inter)
        b1 = QPushButton(L(f"📊 Sensitivity: {self.lab.sensitivity_label}", "📊 الحساسية"))
        b1.setToolTip(L("Changes each parameter by ±5% and reports how much the outcome moves.",
                        "يغيّر كل معامل بنسبة ±5% ويوضح مقدار تغير النتيجة."))
        b1.clicked.connect(self._run_sensitivity)
        btns.addWidget(b1)
        v.addLayout(btns)
        self.explain_view = QTextBrowser()
        self.explain_view.setOpenExternalLinks(True)
        v.addWidget(self.explain_view, 1)

        side = QTabWidget()
        side.addTab(w, L("Why?", "ليش؟"))
        side.addTab(self._whos_who(), L("Who's Who", "من هو من"))
        side.setMinimumWidth(390)
        return side

    def _whos_who(self):
        """A quick reference for the organisms in THIS lab: what each one does, and how they relate here."""
        from ..library.functions import relations
        from .organism_card import Portrait, badges_html
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(4, 4, 4, 4)
        intro = QLabel(L("What each organism in this lab does. Hover a coloured chip for its meaning; the full card "
                         "is in the Organisms tab and in the Library.",
                         "وظيفة كل كائن في هذا المختبر. مرّر المؤشر على أي وسم ملون لمعرفة معناه، والبطاقة الكاملة "
                         "في تبويب الكائنات وفي المكتبة."))
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color:{TEXT_2}; font-size:8pt")
        v.addWidget(intro)
        for k in self.lab.organisms:
            o = ORGANISMS[k]
            row = QFrame()
            row.setObjectName("card")
            h = QHBoxLayout(row)
            h.setContentsMargins(8, 6, 8, 6)
            h.addWidget(Portrait(o, small=True), 0, Qt.AlignTop)
            eats = ", ".join(L(*_res(s)) for s in o.substrates) or L("other organisms", "كائنات أخرى")
            makes = ", ".join(L(*_res(s)) for s in o.products) or "—"
            txt = QLabel(f"<b style='color:{o.colour}'>{html.escape(L(o.name, o.name_ar))}</b><br>"
                         f"{badges_html(k, 8)}<br>"
                         f"<span>{html.escape(L(o.role, o.role_ar))}</span><br>"
                         f"<span style='color:{TEXT_2}; font-size:8pt'>{L('Eats', 'يأكل')}: {html.escape(eats)} · "
                         f"{L('Produces', 'ينتج')}: {html.escape(makes)} · {html.escape(L(*o.oxygen_label).split(' —')[0].split(' –')[0])} · "
                         f"{L('best at', 'أفضل عند')} {o.cardinal_T[1]:g} °C, pH {o.cardinal_pH[1]:g}</span>")
            txt.setWordWrap(True)
            h.addWidget(txt, 1)
            v.addWidget(row)
        rel = relations(tuple(self.lab.organisms))
        if rel:
            t = QLabel(L("What the traits suggest will happen between them", "ما تتوقعه الصفات بينها"))
            t.setObjectName("h2")
            v.addWidget(t)
            icons = {"eats": "🍽", "feeds": "⇄", "opens": "✂", "oxygen": "O₂", "acid": "pH↓", "compete": "⚔"}
            lst = QLabel("<br>".join(f"{icons.get(kind, '•')}  {html.escape(L(en, ar))}" for _, _, kind, en, ar in rel))
            lst.setWordWrap(True)
            v.addWidget(lst)
            note = QLabel(L("These come from the traits alone. Whether they actually matter depends on the conditions"
                            + (" — press ⇄ Measure interactions to find out." if self.lab.key == "community" else "."),
                            "هذه مستنتجة من الصفات فقط، وأهميتها الفعلية تعتمد على الظروف"
                            + (" – اضغط ⇄ قياس التفاعلات لمعرفتها." if self.lab.key == "community" else ".")))
            note.setWordWrap(True)
            note.setStyleSheet(f"color:{TEXT_2}; font-size:8pt")
            v.addWidget(note)
        v.addStretch(1)
        sc = QScrollArea(widgetResizable=True)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sc.setWidget(box)
        return sc

    def _model_html(self) -> str:
        e = html.escape
        m = self.model
        rows = "".join(f"<tr><td><b>{e(s.symbol)}</b></td><td>{e(s.name)}</td><td>{e(s.unit)}</td>"
                       f"<td>{e(s.description)}</td></tr>" for s in m.state_vars)
        prm = "".join(
            f"<tr><td>{e(p.symbol)}</td><td>{e(param_name(p))}</td><td align=right>{p.value:g}</td><td>{e(p.unit)}</td>"
            f"<td style='color:{EVIDENCE_COLOURS[p.evidence]}'>{EVIDENCE_TEXT[p.evidence]}</td></tr>"
            for p in m.default_parameters().params.values())
        doc = (m.__class__.__module__.split(".")[-1])
        return (f"<h3>{e(m.title)} <span style='color:#8b949e'>(model {e(m.id)} v{e(m.version)})</span></h3>"
                f"<p style='color:{self.lab.status_colour}'>{e(self.lab.status)}</p>"
                f"<p>{e((m.__class__.__doc__ or '').strip())}</p>"
                f"<h4>State variables</h4><table cellpadding=3>{rows}</table>"
                f"<h4>Parameters (defaults)</h4><table cellpadding=3>{prm}</table>"
                f"<p>Full documentation: <code>docs/models/{e(doc)}.md</code></p>")

    # ------------------------------------------------------------- scenario
    def apply_scenario(self, sc: Scenario):
        self.scenario = sc
        self.sc_combo.blockSignals(True)
        self.sc_combo.setCurrentIndex([s.key for s in self.lab.scenarios].index(sc.key))
        self.sc_combo.blockSignals(False)
        widgets = [*self.spins.values(), self.seed, self.volume, self.t_end, self.rb_det, self.rb_sto]
        for wdg in widgets:
            wdg.blockSignals(True)
        for sym, prm in self.model.default_parameters().params.items():
            self.spins[sym].setValue(sc.overrides.get(sym, prm.value))
        self.seed.setValue(sc.seed)
        self.volume.setValue(sc.volume_ml)
        self.t_end.setValue(sc.t_end or self.lab.default_t_end)
        (self.rb_sto if sc.mode == "stochastic" and self.lab.supports_stochastic else self.rb_det).setChecked(True)
        for wdg in widgets:
            wdg.blockSignals(False)
        self.title_lbl.setText(
            f"<span style='font-size:12pt; font-weight:700; color:{self.lab.accent}'>"
            f"{html.escape(L(self.lab.title, self.lab.title_ar))}</span>"
            f"  <span style='color:{TEXT_2}'>›</span>  <b>{html.escape(L(sc.title, sc.title_ar))}</b>"
            f"<br><span style='color:{TEXT_2}'>{T('question')}: {html.escape(sc.question)}</span>")
        self.cur_t = 0.0
        self._params_changed()

    # -------------------------------------------------------------- running
    def current_config(self) -> RunConfig:
        vals = {k: s.value() for k, s in self.spins.items()}
        mode = "stochastic" if self.rb_sto.isChecked() and self.lab.supports_stochastic else "deterministic"
        cfg = self.lab.config(vals, mode=mode, seed=self.seed.value(), volume_ml=self.volume.value(),
                              t_end=self.t_end.value())
        if cfg.t_end / cfg.dt_out > 8000:
            cfg = replace(cfg, dt_out=cfg.t_end / 8000)
        return cfg

    def _params_changed(self, *_):
        self.sens = None
        self.inter = None
        self.debounce.start()

    def start_run(self):
        self.run_token += 1
        self.outcome_lbl.setText(T("computing"))
        job = Job(self.run_token, run, self.model, self.current_config())
        job.signals.done.connect(self._run_done)
        job.signals.failed.connect(self._failed)
        self.pool.start(job)

    def _run_done(self, token, traj):
        if token != self.run_token:
            return
        self.traj = traj
        for cs in self.curves:
            for s, curve in cs:
                y = np.asarray(s.getter(traj), float)
                curve.setData(traj.t, np.maximum(y, 1e-6))
        self.cur_t = min(self.cur_t, self._t_max())
        self._show_outcome()
        self.hash_lbl.setText(f"Run config hash: {traj.config_hash[:16]}… (identical inputs ⇒ identical results)")
        self._seek(self.cur_t)
        self._refresh_explanation(force=True)

    def _show_outcome(self):
        if self.traj is None:
            return
        label, colour = self.lab.outcome(self.traj)
        self.outcome_lbl.setText(f"<span style='color:{TEXT_2}; font-weight:400'>{T('prediction')}:</span> "
                                 f"<span style='color:{colour}'>{html.escape(label)}</span>")

    def _failed(self, _token, tb):
        self.outcome_lbl.setText(L("could not compute", "تعذّر الحساب"))
        box = QMessageBox(QMessageBox.Warning, L("Could not compute", "تعذّر الحساب"),
                          L(ERR_EN, ERR_AR), parent=self)
        box.setDetailedText(tb)
        box.exec()

    # ------------------------------------------------------------- playback
    def _t_max(self):
        return float(self.traj.t[-1]) if self.traj is not None else 1.0

    def _toggle_play(self):
        self.playing = not self.playing
        if self.playing and self.cur_t >= self._t_max() - 1e-9:
            self.cur_t = 0.0
        self.btn_play.setText("⏸ " + T("pause") if self.playing else "▶ " + T("play"))

    def _seek(self, t, source=None):
        self.cur_t = float(np.clip(t, 0, self._t_max()))
        for c in self.cursors:
            if c is not source:
                c.setValue(self.cur_t)
        self.slider.blockSignals(True)
        self.slider.setValue(int(self.cur_t / self._t_max() * 1000))
        self.slider.blockSignals(False)
        self.time_lbl.setText(f"t = {self.cur_t:7.2f} {self.lab.time_unit}")
        self._explain_dirty = True

    def _tick(self):
        if self.traj is None:
            return
        if not hasattr(self, "_clock"):
            self._clock = QElapsedTimer()
            self._clock.start()
        dt = min(self._clock.restart() / 1000.0, 0.1)        # real seconds since the last frame
        if self.playing:
            self._seek(self.cur_t + self.speed.value() * dt)
            if self.cur_t >= self._t_max():
                self._toggle_play()
        self.scene.update(self.traj, self.cur_t, dt)          # interpolated state at the current time
        self.micro.time_d = self.cur_t
        self.micro.update()

    def _replay(self):
        if self.traj is None:
            return
        self.scene.replay(self.traj, 0.0)
        self._seek(0.0)
        if not self.playing:
            self._toggle_play()

    def _set_mode(self):
        self.scene.mode = self.mode_combo.currentData()
        self.micro.update()

    def _refresh_explanation(self, force=False):
        if self.traj is None or not (force or self._explain_dirty):
            return
        self._explain_dirty = False
        sb = self.explain_view.verticalScrollBar().value()
        extra = (self.sens, self.inter) if self.lab.key == "community" else self.sens
        from ..analysis.changes import to_html as changes_html
        idx = self.traj.index_at(self.cur_t)
        self.explain_view.setHtml(self.lab.explain_html(self.traj, idx, extra) +
                                  changes_html(self.model, self.traj, idx, self.sens))
        self.explain_view.verticalScrollBar().setValue(sb)

    # ------------------------------------------------------ analysis actions
    def _run_sensitivity(self):
        cfg = self.current_config()
        if self.lab.key == "chemostat":
            cfg = replace(cfg, t_end=max(cfg.t_end, 600), dt_out=0.5)
        self.outcome_lbl.setText(T("computing"))
        job = Job(self.run_token, elasticities, self.model, cfg, self.lab.sensitivity_metric, rebuild=self.lab.rebuild)
        job.signals.done.connect(self._sens_done)
        job.signals.failed.connect(self._failed)
        self.pool.start(job)

    def _sens_done(self, token, sens):
        if token != self.run_token:
            return
        self.sens = sens
        self._show_outcome()
        self._refresh_explanation(force=True)

    def _run_interactions(self):
        self.btn_inter.setEnabled(False)
        self.outcome_lbl.setText(L("measuring interactions…", "جاري قياس التفاعلات…"))
        job = Job(self.run_token, analyse, self.model, self.current_config(), with_progress=True)
        job.signals.done.connect(self._inter_done)
        job.signals.failed.connect(self._failed)
        self.pool.start(job)

    def _inter_done(self, token, result):
        self.btn_inter.setEnabled(True)
        self.inter = result[0]
        self._show_outcome()
        self._refresh_explanation(force=True)

    def _run_replicates(self):
        from ..analysis.replicates import run_replicates
        self.btn_rep.setEnabled(False)
        cfg = replace(self.current_config(), mode="stochastic")
        job = Job(None, run_replicates, self.model, cfg, self.rep_n.value(), with_progress=True)
        job.signals.progress.connect(lambda i, n: (self.rep_prog.setMaximum(n), self.rep_prog.setValue(i)))
        job.signals.done.connect(self._replicates_done)
        job.signals.failed.connect(lambda t, tb: (self.btn_rep.setEnabled(True), self._failed(t, tb)))
        self.pool.start(job)

    def _replicates_done(self, _token, s):
        from ..analysis.replicates import describe
        from ..i18n import is_ar
        self.btn_rep.setEnabled(True)
        self.rep_plot.clear()
        names = {sv.symbol: sv.name for sv in self.model.state_vars}
        colours = {}
        for panel in self.lab.plots:
            for ser in panel.series:
                colours[ser.label.split(" — ")[0].split(" ")[0]] = ser.colour
        for j, sym in enumerate(s.symbols):
            col = colours.get(sym, "#9da7b3")
            lo = pg.PlotDataItem(s.t, s.lo[:, j], pen=pg.mkPen(col, width=0.5))
            hi = pg.PlotDataItem(s.t, s.hi[:, j], pen=pg.mkPen(col, width=0.5))
            c = pg.mkColor(col)
            c.setAlpha(50)
            self.rep_plot.addItem(pg.FillBetweenItem(lo, hi, brush=c))
            self.rep_plot.plot(s.t, s.mean[:, j], pen=pg.mkPen(col, width=2), name=f"{names.get(sym, sym)} (mean)")
        self.rep_text.setText("<br>".join(describe(s, names, self.lab.time_unit, is_ar())))

    def _run_scan(self):
        self.btn_scan.setEnabled(False)
        job = Job(None, self.lab.scan_compute, self.lab, self.current_config(), with_progress=True)
        job.signals.progress.connect(lambda i, n: (self.scan_prog.setMaximum(n), self.scan_prog.setValue(i)))
        job.signals.done.connect(self._scan_done)
        job.signals.failed.connect(self._failed)
        self.pool.start(job)

    def _scan_done(self, _token, rows):
        self.btn_scan.setEnabled(True)
        self.scan_plot.clear()
        x = self.lab.scan_plot(self.scan_plot, rows, self.current_config())
        self.scan_plot.addItem(pg.InfiniteLine(pos=x, angle=90, pen=pg.mkPen("#ffffff", style=Qt.DashLine),
                                               label="current", labelOpts={"position": 0.95}))

    def _freeze_prediction(self):
        if self.traj is None:
            return
        hyp, ok = QInputDialog.getText(self, L("Freeze prediction", "تجميد التوقع"),
                                       L("Hypothesis — what will you test in the lab?",
                                         "الفرضية – ماذا ستختبر في المختبر؟"))
        if not ok:
            return
        sure = QMessageBox.question(self, L("Freeze permanently?", "تجميد نهائي؟"), L(FREEZE_EN, FREEZE_AR))
        if sure != QMessageBox.Yes:
            return
        cfg = self.traj.config
        summary = {"lab": self.lab.key, "scenario": self.scenario.key, "model": f"{self.model.id} v{self.model.version}",
                   "mode": cfg.mode, "outcome": self.lab.outcome(self.traj)[0], **self.lab.summary(self.traj),
                   "status": "prediction (not validated)"}
        con = db.connect()
        db.seed_model(con, self.model)
        exp_id = db.save_experiment(con, hyp[:60] or self.scenario.title, cfg)
        pid = db.freeze_prediction(con, cfg, summary, hyp, exp_id)
        rec = con.execute("SELECT record_hash, created FROM predictions WHERE id=?", (pid,)).fetchone()
        QMessageBox.information(self, "Prediction frozen",
                                f"Prediction #{pid} stored at {rec['created']} (UTC).\nRecord hash: {rec['record_hash'][:16]}…\n\n"
                                "It can no longer be edited or deleted. Compare it with your lab results later.")

    # ---------------------------------------------------------------- files
    def _save(self):
        (ROOT / "experiments").mkdir(exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(self, "Save experiment",
                                              str(ROOT / "experiments" / f"{self.lab.key}_{self.scenario.key}.json"),
                                              "MicroVerse experiment (*.json)")
        if path:
            experiment.save(path, self.current_config(), Path(path).stem, notes=self.scenario.question)

    def _open(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open experiment", str(ROOT / "experiments"),
                                              "MicroVerse experiment (*.json)")
        if not path:
            return
        try:
            cfg = experiment.load(path)
        except ValueError as e:
            QMessageBox.warning(self, "Cannot open", str(e))
            return
        if cfg.model_id != self.model.id:
            QMessageBox.warning(self, "Different lab", f"This file belongs to the '{cfg.model_id}' model. "
                                "Go Home and open that lab first.")
            return
        widgets = [*self.spins.values(), self.seed, self.volume, self.t_end, self.rb_det, self.rb_sto]
        for wdg in widgets:
            wdg.blockSignals(True)
        for k, v in cfg.parameters.items():
            self.spins[k].setValue(v)
        self.seed.setValue(cfg.seed)
        self.volume.setValue(cfg.volume_ml)
        self.t_end.setValue(cfg.t_end)
        (self.rb_sto if cfg.mode == "stochastic" else self.rb_det).setChecked(True)
        for wdg in widgets:
            wdg.blockSignals(False)
        self._params_changed()

    def _export_csv(self):
        if self.traj is None:
            return
        (ROOT / "experiments").mkdir(exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV",
                                              str(ROOT / "experiments" / f"{self.lab.key}_{self.scenario.key}.csv"),
                                              "CSV (*.csv)")
        if path:
            Path(path).write_text(self.traj.to_csv(), encoding="utf-8")
            Path(path).with_suffix(".config.json").write_text(json.dumps(self.traj.config.to_dict(), indent=2))

    def _home(self):
        self.anim.stop()
        self.explain_timer.stop()
        self.go_home.emit()
