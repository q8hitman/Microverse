"""Calibration dialog: choose parameters, fit them to the imported data set, and freeze the fit as a NEW prediction."""
from __future__ import annotations

import html

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QThreadPool, Qt
from PySide6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QInputDialog, QLabel, QMessageBox, QProgressBar,
                               QPushButton, QScrollArea, QSplitter, QTextBrowser, QVBoxLayout, QWidget)

from ..analysis import calibration as C
from ..analysis import reality as R
from ..data import db
from ..i18n import L, is_ar, param_name
from .workers import Job

INTRO_EN = """<b>Calibration</b> changes a few parameters until the model matches <i>this</i> data set as closely as it
can. The prediction you started from is not changed: the result is saved as a <b>new</b> prediction that records
which file it was fitted to. A fit always matches its own data, so it proves little; test the new prediction on a
<b>different</b> data set (another batch, temperature or day)."""
INTRO_AR = """<b>المعايرة</b> تغيّر بعض المعاملات حتى يطابق النموذج <i>هذه</i> البيانات قدر الإمكان. التوقع الذي بدأت منه لا
يتغير: تُحفظ النتيجة كتوقع <b>جديد</b> يسجّل الملف الذي عُويِر عليه. الملاءمة تطابق بياناتها دائماً فلا تثبت الكثير؛
اختبر التوقع الجديد على مجموعة بيانات <b>مختلفة</b> (دفعة أو حرارة أو يوم آخر)."""

FREEZE_EN = """The fitted settings will be stored as a NEW prediction, with the file it was fitted to (SHA-256) and
the prediction it came from. It cannot be edited or deleted afterwards. Prediction #{base} stays exactly as it was.

Freeze it now?"""
FREEZE_AR = """ستُحفظ الإعدادات المعايَرة كتوقع جديد مع الملف الذي عُويِرت عليه (بصمة SHA-256) والتوقع الأصلي.
لا يمكن تعديله أو حذفه بعد ذلك. التوقع رقم {base} يبقى كما هو تماماً.

هل تريد تجميده الآن؟"""


class CalibrationDialog(QDialog):
    def __init__(self, fp: R.FrozenPrediction, lab, table: R.Table, cmap: R.ColumnMap, obs, series, parent=None):
        super().__init__(parent)
        self.fp, self.lab, self.table, self.cmap, self.obs, self.series = fp, lab, table, cmap, obs, series
        self.result: C.CalibrationResult | None = None
        self.new_pid: int | None = None
        self.token = 0
        self.setWindowTitle(L("Calibrate → new prediction", "معايرة ← توقع جديد"))
        self.resize(1180, 760)
        root = QVBoxLayout(self)
        intro = QLabel(L(INTRO_EN, INTRO_AR))
        intro.setWordWrap(True)
        intro.setObjectName("muted")
        root.addWidget(intro)

        split = QSplitter(Qt.Horizontal)
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 8, 0)
        lv.addWidget(QLabel(L(f"Parameters to fit (at most {C.MAX_PARAMS})", f"المعاملات المراد معايرتها (حتى {C.MAX_PARAMS})")))
        box = QWidget()
        bv = QVBoxLayout(box)
        bv.setContentsMargins(0, 0, 0, 0)
        model = lab.model
        meta = model.default_parameters().params
        suggested = set(C.suggested_parameters(model))
        self.checks: dict[str, QCheckBox] = {}
        for sym, prm in meta.items():
            if prm.evidence.value == "control":
                continue                    # experimental settings are known, not fitted
            v = fp.config.parameters.get(sym, prm.value)
            cb = QCheckBox(f"{param_name(prm)} ({sym}) = {v:g} {prm.unit}")
            cb.setToolTip(f"{prm.description}\n{L('evidence', 'الدليل')}: {prm.evidence.value} · "
                          f"{L('allowed', 'المسموح')}: {prm.lower:g}–{prm.upper:g}")
            cb.setChecked(sym in suggested)
            cb.toggled.connect(self._count)
            bv.addWidget(cb)
            self.checks[sym] = cb
        bv.addStretch(1)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setWidget(box)
        lv.addWidget(sc, 1)
        self.count_lbl = QLabel()
        self.count_lbl.setObjectName("muted")
        lv.addWidget(self.count_lbl)
        self.bar = QProgressBar()
        self.bar.setVisible(False)
        lv.addWidget(self.bar)
        row = QHBoxLayout()
        self.btn_fit = QPushButton(L("Fit", "عايِر"))
        self.btn_fit.setObjectName("primary")
        self.btn_fit.clicked.connect(self._fit)
        row.addWidget(self.btn_fit)
        self.btn_freeze = QPushButton(L("Freeze as new prediction…", "جمّد كتوقع جديد…"))
        self.btn_freeze.setEnabled(False)
        self.btn_freeze.clicked.connect(self._freeze)
        row.addWidget(self.btn_freeze)
        lv.addLayout(row)
        split.addWidget(left)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(8, 0, 0, 0)
        self.plots = pg.GraphicsLayoutWidget()
        rv.addWidget(self.plots, 3)
        self.report = QTextBrowser()
        rv.addWidget(self.report, 2)
        split.addWidget(right)
        split.setSizes([400, 780])
        root.addWidget(split, 1)
        self._count()
        self._plot(None)

    def chosen(self) -> list[str]:
        return [s for s, cb in self.checks.items() if cb.isChecked()]

    def _count(self, *_):
        n = sum(len(s.t_model) for s in self.series)
        k = len(self.chosen())
        self.count_lbl.setText(L(f"{k} parameter(s) chosen · {n} measurements", f"{k} معامل مختار · {n} قياس"))
        self.btn_fit.setEnabled(0 < k <= C.MAX_PARAMS)

    # ------------------------------------------------------------------ fitting
    def _fit(self):
        self.token += 1
        self.btn_fit.setEnabled(False)
        self.btn_freeze.setEnabled(False)
        self.bar.setVisible(True)
        self.bar.setRange(0, 0)
        job = Job(self.token, C.calibrate, self.lab.model, self.fp.config, self.obs, self.series, self.chosen(),
                  with_progress=True)
        job.signals.progress.connect(lambda i, n: (self.bar.setRange(0, n), self.bar.setValue(i)))
        job.signals.done.connect(self._done)
        job.signals.failed.connect(self._failed)
        QThreadPool.globalInstance().start(job)

    def _failed(self, token, tb):
        if token != self.token:
            return
        self.bar.setVisible(False)
        self._count()
        last = tb.strip().splitlines()[-1]
        QMessageBox.warning(self, L("Calibration failed", "فشلت المعايرة"), last.split(":", 1)[-1].strip())

    def _done(self, token, res):
        if token != self.token:
            return
        self.result = res
        self.bar.setVisible(False)
        self._count()
        self.btn_freeze.setEnabled(True)
        self._plot(res)
        self._write(res)

    # ------------------------------------------------------------------ display
    def _plot(self, res):
        self.plots.clear()
        unit_t = R.model_time_unit(self.lab.model)
        by_key = {o.key: o for o in self.obs}
        base_traj = self.parent().traj if self.parent() is not None and getattr(self.parent(), "traj", None) is not None \
            else None
        for k, s in enumerate(self.series):
            o = by_key[s.key]
            p = self.plots.addPlot(row=k, col=0, title=L(o.label, o.label_ar))
            p.setLogMode(y=o.log)
            p.showGrid(x=True, y=True, alpha=0.15)
            p.setLabel("bottom", "time", unit_t)
            p.setLabel("left", o.unit)
            p.getAxis("left").enableAutoSIPrefix(False)
            p.addLegend(offset=(-8, 8))
            f = (lambda y: np.maximum(y, 1e-12)) if o.log else (lambda y: y)
            if base_traj is not None:
                p.plot(base_traj.t, f(o.getter(base_traj)), pen=pg.mkPen("#3987e5", width=2, style=Qt.DashLine),
                       name=L(f"prediction #{self.fp.id}", f"التوقع رقم {self.fp.id}"))
            if res is not None:
                p.plot(res.traj.t, f(o.getter(res.traj)), pen=pg.mkPen("#3fb950", width=2),
                       name=L("fitted", "بعد المعايرة"))
            p.plot(s.t_model, s.values, pen=None, symbol="o", symbolSize=8, symbolBrush="#d95926",
                   symbolPen=pg.mkPen("#0d1117"), name=L("measured", "المقاس"))

    def _write(self, res: C.CalibrationResult):
        ar = is_ar()
        out = [f"<div dir='{'rtl' if ar else 'ltr'}'>"]
        out.append("<table cellpadding='4' style='border-collapse:collapse'><tr>" + "".join(
            f"<th align='left'>{h}</th>" for h in (L("parameter", "المعامل"), L("start", "البداية"),
                                                    L("fitted", "بعد المعايرة"), L("≈95 % interval", "مجال ≈95٪"),
                                                    L("unit", "الوحدة"))) + "</tr>")
        for p in res.parameters:
            ci = "–" if p.ci_low is None else f"{p.ci_low:.3g} – {p.ci_high:.3g}"
            flag = " ⚠" if p.at_limit else ""
            out.append(f"<tr><td>{html.escape(param_name(p))} ({p.symbol})</td><td>{p.start:.3g}</td>"
                       f"<td><b>{p.value:.3g}</b>{flag}</td><td>{ci}</td><td>{html.escape(p.unit)}</td></tr>")
        out.append("</table>")
        out.append("<p>" + L("Error on this data set (RMSE): ", "الخطأ على هذه البيانات (RMSE): ") + " · ".join(
            f"{html.escape(L(o.label, o.label_ar))} {mb.rmse:.3g} → <b>{ma.rmse:.3g}</b>{' (log10)' if o.log else ''}"
            for (o, _s, mb), (_o, _s2, ma) in zip(res.before, res.after)) + "</p>")
        warns = res.warnings_ar if ar else res.warnings
        if warns:
            out.append("<p style='color:#e3b341'>" + "<br>".join("⚠ " + html.escape(w) for w in warns) + "</p>")
        out.append("<p style='color:#8b949e'>" + L(
            f"{res.n_points} measurements, {res.n_evals} model runs. Intervals are local (linearised) estimates. "
            "This is a fit to one data set; it is not validation.",
            f"{res.n_points} قياس و{res.n_evals} تشغيل للنموذج. المجالات تقديرات محلية (خطية). "
            "هذه ملاءمة لمجموعة بيانات واحدة وليست تحققاً.") + "</p></div>")
        self.report.setHtml("".join(out))

    # ------------------------------------------------------------------ freezing
    def _freeze(self):
        if self.result is None:
            return
        hyp, ok = QInputDialog.getText(self, L("New prediction", "توقع جديد"),
                                       L("What will you test it on? (a different data set)",
                                         "على ماذا ستختبره؟ (مجموعة بيانات مختلفة)"))
        if not ok:
            return
        sure = QMessageBox.question(self, L("Freeze permanently?", "تجميد نهائي؟"),
                                    L(FREEZE_EN, FREEZE_AR).format(base=self.fp.id))
        if sure != QMessageBox.Yes:
            return
        con = db.connect()
        self.new_pid = C.freeze_calibrated(con, self.fp, self.result, self.table, self.cmap, self.lab, hyp)
        QMessageBox.information(self, L("Prediction frozen", "جُمّد التوقع"),
                                L(f"New prediction #{self.new_pid} stored. Prediction #{self.fp.id} was not changed.",
                                  f"حُفظ التوقع الجديد رقم {self.new_pid}. التوقع رقم {self.fp.id} لم يتغير."))
        self.accept()
