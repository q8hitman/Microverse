"""Prediction vs Reality page: pick a frozen prediction, import measurements, map columns, compare, save a report."""
from __future__ import annotations

import html
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QTextBrowser,
                               QVBoxLayout, QWidget)

from ..analysis import calibration as C
from ..analysis import reality as R
from ..data import db
from ..i18n import L, is_ar, is_school

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "data" / "examples"

HELP_EN = """<b>How it works.</b> 1) Choose a prediction you froze before doing the experiment. 2) Import your measurements
as a CSV file (Excel: <i>Save as → CSV UTF-8</i>). One column is time; each other column is one measured variable.
3) Tell MicroVerse which column is time (and its unit) and what each measured column is (and its unit).
4) Press <b>Compare</b>. The frozen prediction is re-simulated from its stored settings; it is never changed.
The report lists the error metrics and what the pattern of differences suggests."""
HELP_AR = """<b>طريقة العمل.</b> ١) اختر توقعاً جمّدته قبل التجربة. ٢) استورد قياساتك كملف CSV (من إكسل: <i>حفظ باسم ← CSV UTF-8</i>).
عمود واحد للزمن، وكل عمود آخر لمتغير مقاس. ٣) حدّد عمود الزمن ووحدته، وما يمثله كل عمود ووحدته.
٤) اضغط <b>قارن</b>. يُعاد حساب التوقع المجمّد من إعداداته المحفوظة ولا يتغير أبداً.
التقرير يعرض مقاييس الخطأ وما يوحي به نمط الاختلاف."""


class RealityPage(QWidget):
    back = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.fp = None
        self.lab = None
        self.traj = None
        self.table = None
        self.obs = []
        self.results = []
        self._snap = None           # (prediction, table, column map, lab, trajectory) the results came from
        self.var_rows: list[tuple[str, QComboBox, QComboBox]] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        head = QHBoxLayout()
        b = QPushButton("◀ " + L("Home", "الرئيسية"))
        b.setObjectName("link")
        b.clicked.connect(self.back)
        head.addWidget(b)
        t = QLabel(L("Prediction vs Reality", "التوقع مقابل الواقع"))
        t.setObjectName("h1")
        head.addWidget(t, 1)
        root.addLayout(head)
        helpl = QLabel(L(HELP_EN, HELP_AR))
        helpl.setWordWrap(True)
        helpl.setObjectName("muted")
        root.addWidget(helpl)

        split = QSplitter(Qt.Horizontal)
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 8, 0)
        g1 = QGroupBox(L("1 · Frozen prediction", "١ · التوقع المجمّد"))
        f1 = QVBoxLayout(g1)
        self.pred_combo = QComboBox()
        self.pred_combo.currentIndexChanged.connect(self._pick_prediction)
        f1.addWidget(self.pred_combo)
        self.pred_info = QLabel()
        self.pred_info.setWordWrap(True)
        f1.addWidget(self.pred_info)
        lv.addWidget(g1)
        g2 = QGroupBox(L("2 · Measurements", "٢ · القياسات"))
        f2 = QVBoxLayout(g2)
        row = QHBoxLayout()
        self.btn_import = QPushButton(L("Import CSV…", "استيراد CSV…"))
        self.btn_import.clicked.connect(self._import)
        row.addWidget(self.btn_import)
        self.btn_example = QPushButton(L("Make an example file", "أنشئ ملف مثال"))
        self.btn_example.setToolTip(L("Writes a CSV in the right layout for the selected prediction, with SYNTHETIC "
                                      "values (the prediction plus noise and a delay) so you can try the page.",
                                      "ينشئ ملف CSV بالشكل الصحيح للتوقع المختار، بقيم مصطنعة (التوقع مع ضوضاء وتأخير) "
                                      "لتجربة الصفحة."))
        self.btn_example.clicked.connect(self._example)
        row.addWidget(self.btn_example)
        f2.addLayout(row)
        self.file_lbl = QLabel(L("No file yet.", "لا يوجد ملف بعد."))
        self.file_lbl.setWordWrap(True)
        f2.addWidget(self.file_lbl)
        self.preview = QTableWidget(0, 0)
        self.preview.setMaximumHeight(150)
        f2.addWidget(self.preview)
        lv.addWidget(g2)
        g3 = QGroupBox(L("3 · Columns", "٣ · الأعمدة"))
        self.map_form = QFormLayout(g3)
        self.time_col = QComboBox()
        self.time_unit = QComboBox()
        for u, lab in (("h", L("hours", "ساعات")), ("min", L("minutes", "دقائق")), ("d", L("days", "أيام")),
                       ("s", L("seconds", "ثوانٍ")), ("datetime", L("date-time (ISO)", "تاريخ ووقت (ISO)"))):
            self.time_unit.addItem(lab, u)
        tr_row = QHBoxLayout()
        tr_row.addWidget(self.time_col, 1)
        tr_row.addWidget(self.time_unit)
        self.map_form.addRow(L("Time column", "عمود الزمن"), tr_row)
        self.offset = QDoubleSpinBox(decimals=2, minimum=-1e4, maximum=1e4, suffix=L(" h", " ساعة"))
        self.offset.setToolTip(L("If your first measurement was not taken at the simulation's time 0, enter when it was.",
                                 "إذا لم يكن أول قياس عند الزمن صفر في المحاكاة، أدخل متى كان."))
        self.map_form.addRow(L("First measurement at", "أول قياس عند"), self.offset)
        self.time_col.currentIndexChanged.connect(self._invalidate)
        self.time_unit.currentIndexChanged.connect(self._invalidate)
        self.offset.valueChanged.connect(self._invalidate)
        lv.addWidget(g3)
        row2 = QHBoxLayout()
        self.btn_compare = QPushButton(L("4 · Compare", "٤ · قارن"))
        self.btn_compare.setObjectName("primary")
        self.btn_compare.clicked.connect(self._compare)
        row2.addWidget(self.btn_compare)
        self.btn_save = QPushButton(L("Save report", "احفظ التقرير"))
        self.btn_save.clicked.connect(self._save)
        self.btn_save.setEnabled(False)
        row2.addWidget(self.btn_save)
        lv.addLayout(row2)
        self.btn_calib = QPushButton(L("5 · Calibrate → new prediction…", "٥ · عايِر ← توقع جديد…"))
        self.btn_calib.setToolTip(L("Fit a few parameters to this data set and save the fit as a NEW prediction. "
                                    "The selected prediction is not changed.",
                                    "عايِر بعض المعاملات على هذه البيانات واحفظ النتيجة كتوقع جديد. "
                                    "التوقع المختار لا يتغير."))
        self.btn_calib.clicked.connect(self._calibrate)
        lv.addWidget(self.btn_calib)
        lv.addStretch(1)
        split.addWidget(left)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(8, 0, 0, 0)
        self.plots = pg.GraphicsLayoutWidget()
        rv.addWidget(self.plots, 3)
        self.report = QTextBrowser()
        rv.addWidget(self.report, 2)
        split.addWidget(right)
        split.setSizes([460, 900])
        root.addWidget(split, 1)
        self.refresh()
        self.apply_audience()

    # ------------------------------------------------------------------ predictions
    def refresh(self):
        con = db.connect()
        self.rows = [r for r in R.list_predictions(con) if r["has_config"]]
        self.pred_combo.blockSignals(True)
        self.pred_combo.clear()
        for r in self.rows:
            self.pred_combo.addItem(f"#{r['id']} · {r['created'][:16]} · {r['lab']} / {r['scenario']} · "
                                    f"{r['hypothesis'][:40]}", r["id"])
        self.pred_combo.blockSignals(False)
        if not self.rows:
            self.pred_info.setText(L("No frozen predictions yet. Open a lab, run it and press “Freeze prediction”.",
                                     "لا توجد توقعات مجمّدة بعد. افتح مختبراً وشغّله واضغط «تجميد التوقع»."))
        else:
            self._pick_prediction()

    def _pick_prediction(self):
        self._invalidate()
        if not self.rows:
            return
        pid = self.pred_combo.currentData()
        con = db.connect()
        try:
            self.fp = R.load_prediction(con, pid)
            self.lab, self.traj = R.resimulate(self.fp)
        except Exception as e:                                   # noqa: BLE001 — shown to the user
            self.pred_info.setText(str(e))
            self.fp = None
            return
        self.obs = R.observables_for(self.lab.model)
        ok = lambda b: L("✔", "✔") if b else L("✘ FAILED", "✘ فشل")
        txt = L(f"Outcome frozen: <b>{html.escape(str(self.fp.summary.get('outcome', '')))}</b><br>"
                f"Record hash {ok(self.fp.record_ok)} · settings hash {ok(self.fp.config_ok)} · "
                f"simulated to {self.traj.t[-1]:g} {R.model_time_unit(self.lab.model)}",
                f"النتيجة المجمّدة: <b>{html.escape(str(self.fp.summary.get('outcome', '')))}</b><br>"
                f"بصمة السجل {ok(self.fp.record_ok)} · بصمة الإعدادات {ok(self.fp.config_ok)} · "
                f"المحاكاة حتى {self.traj.t[-1]:g} {R.model_time_unit(self.lab.model)}")
        if self.fp.version_note:
            txt += "<br><span style='color:#e3b341'>" + html.escape(self.fp.version_note) + "</span>"
        self.pred_info.setText(txt)
        self._rebuild_mapping()

    # ------------------------------------------------------------------ measurements
    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, L("Measurements", "القياسات"), str(ROOT),
                                              "CSV (*.csv *.txt *.tsv)")
        if path:
            self._load(path)

    def _load(self, path):
        try:
            self.table = R.read_table(path)
        except (ValueError, OSError) as e:
            QMessageBox.warning(self, L("Cannot read the file", "تعذّرت قراءة الملف"), str(e))
            return
        self.file_lbl.setText(f"{Path(path).name} · {len(self.table.rows)} " + L("rows", "صف") +
                              f" · SHA-256 {self.table.sha256[:12]}…")
        self.preview.setColumnCount(len(self.table.columns))
        self.preview.setHorizontalHeaderLabels(self.table.columns)
        self.preview.setRowCount(min(len(self.table.rows), 6))
        for i, r in enumerate(self.table.rows[:6]):
            for j, c in enumerate(r):
                self.preview.setItem(i, j, QTableWidgetItem(c))
        self._rebuild_mapping()

    def _example(self):
        if self.fp is None:
            return
        unit = R.model_time_unit(self.lab.model)
        rng = np.random.default_rng(1)
        t = np.linspace(self.traj.t[0], self.traj.t[-1] * 0.9, 12)
        delay = 0.06 * (self.traj.t[-1] - self.traj.t[0])
        cols = [o for o in self.obs if o.key in ("pH", "st_cfu", "algae_cells", "rotifers")] or self.obs[:2]
        lines = ["# SYNTHETIC example data generated by MicroVerse — NOT real measurements",
                 f"time_{unit}," + ",".join(o.key for o in cols)]
        for ti in t:
            vals = []
            for o in cols:
                v = float(np.interp(max(ti - delay, 0), self.traj.t, o.getter(self.traj)))
                v = v * 10 ** rng.normal(0, 0.08) if o.log else v + rng.normal(0, 0.03 * (abs(v) + 0.1))
                vals.append(f"{v:.4g}")
            lines.append(f"{ti:.3f}," + ",".join(vals))
        EXAMPLE.mkdir(parents=True, exist_ok=True)
        path = EXAMPLE / f"example_P{self.fp.id}.csv"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self._load(str(path))
        i = self.time_unit.findData(unit)
        self.time_unit.setCurrentIndex(i)
        for col, var, u in self.var_rows:
            j = var.findData(col)
            if j >= 0:
                var.setCurrentIndex(j)

    def apply_audience(self):
        self.btn_calib.setVisible(not is_school())       # calibration is a research tool

    def _invalidate(self, *_):
        """Any input changed: the shown comparison no longer matches it, so it cannot be saved."""
        if self.results:
            self.results = []
            self._snap = None
            self.btn_save.setEnabled(False)
            self.plots.clear()
            self.report.setHtml("<i>" + L("Inputs changed. Press Compare again.",
                                          "تغيّرت المدخلات. اضغط «قارن» مرة أخرى.") + "</i>")

    def _rebuild_mapping(self):
        self._invalidate()
        while self.map_form.rowCount() > 2:
            self.map_form.removeRow(2)
        self.var_rows = []
        if self.table is None or not self.obs:
            return
        self.time_col.clear()
        self.time_col.addItems(self.table.columns)
        guess = next((c for c in self.table.columns if c.lower().startswith(("t", "time", "زمن"))), self.table.columns[0])
        self.time_col.setCurrentText(guess)
        for c in self.table.columns:
            var = QComboBox()
            var.addItem(L("— not used —", "— غير مستخدم —"), None)
            for o in self.obs:
                var.addItem(L(o.label, o.label_ar), o.key)
            unit = QComboBox()
            j = var.findData(c)
            if j >= 0:
                var.setCurrentIndex(j)

            def fill_units(_=None, var=var, unit=unit):
                unit.clear()
                o = next((x for x in self.obs if x.key == var.currentData()), None)
                for u in (o.units if o else {}):
                    unit.addItem(u)
            var.currentIndexChanged.connect(fill_units)
            fill_units()
            var.currentIndexChanged.connect(self._invalidate)
            unit.currentIndexChanged.connect(self._invalidate)
            box = QHBoxLayout()
            box.addWidget(var, 1)
            box.addWidget(unit)
            self.map_form.addRow(c, box)
            self.var_rows.append((c, var, unit))

    # ------------------------------------------------------------------ comparison
    def _cmap(self):
        variables = {c: (v.currentData(), u.currentText()) for c, v, u in self.var_rows
                     if v.currentData() and c != self.time_col.currentText()}
        return R.ColumnMap(self.time_col.currentText(), self.time_unit.currentData(), variables, self.offset.value())

    def _compare(self):
        if self.fp is None or self.table is None:
            QMessageBox.information(self, L("Missing input", "مدخلات ناقصة"),
                                    L("Choose a prediction and import a CSV first.", "اختر توقعاً واستورد ملفاً أولاً."))
            return
        cmap = self._cmap()
        series, errors, warnings = R.validate(self.table, cmap, self.obs, self.lab.model)
        if errors:
            QMessageBox.warning(self, L("Please check the data", "يرجى مراجعة البيانات"), "\n".join(errors[:12]))
            return
        by_key = {o.key: o for o in self.obs}
        self.results = []
        for s in series:
            m, pred = R.compare(self.traj, by_key[s.key], s)
            self.results.append((by_key[s.key], s, m, pred))
        self._snap = (self.fp, self.table, cmap, self.lab, self.traj)
        self._plot()
        self._write(warnings)
        self.btn_save.setEnabled(True)

    def _plot(self):
        self.plots.clear()
        unit_t = R.model_time_unit(self.lab.model)
        for k, (o, s, m, _pred) in enumerate(self.results):
            p = self.plots.addPlot(row=k, col=0, title=L(o.label, o.label_ar))
            p.setLogMode(y=o.log)
            p.showGrid(x=True, y=True, alpha=0.15)
            p.setLabel("bottom", L("time", "الزمن"), unit_t)
            p.setLabel("left", o.unit)
            p.getAxis("left").enableAutoSIPrefix(False)
            p.addLegend(offset=(-8, 8))
            p.plot(self.traj.t, np.maximum(o.getter(self.traj), 1e-12) if o.log else o.getter(self.traj),
                   pen=pg.mkPen("#3987e5", width=2), name=L("frozen prediction", "التوقع المجمّد"))
            p.plot(s.t_model, s.values, pen=None, symbol="o", symbolSize=8, symbolBrush="#d95926",
                   symbolPen=pg.mkPen("#0d1117"), name=L("measured", "المقاس"))

    def _write(self, warnings):
        unit_t = R.model_time_unit(self.lab.model)
        ar = is_ar()
        parts = [f"<div dir='{'rtl' if ar else 'ltr'}'>"]
        same = C.same_data_warning(self.fp, self.table, ar)
        if same:
            warnings = [same] + list(warnings)
        if warnings:
            parts.append("<p style='color:#e3b341'>" + "<br>".join(html.escape(w) for w in warnings) + "</p>")
        parts.append("<table cellpadding='4' style='border-collapse:collapse'><tr>" + "".join(
            f"<th align='left'>{h}</th>" for h in (L("variable", "المتغير"), "n", "RMSE", L("bias", "الانحياز"),
                                                    "NRMSE", "R²", L("time shift", "إزاحة زمنية"))) + "</tr>")
        for o, s, m, _p in self.results:
            r2 = "–" if m.r2 is None else f"{m.r2:.3f}"
            parts.append(f"<tr><td>{html.escape(L(o.label, o.label_ar))}{' (log10)' if o.log else ''}</td><td>{m.n}</td>"
                         f"<td>{m.rmse:.3g}</td><td>{m.bias:+.3g}</td><td>{m.nrmse * 100:.0f}%</td><td>{r2}</td>"
                         f"<td dir='ltr'>{m.shift + 0.0:+.3g} {unit_t}</td></tr>")
        parts.append("</table>")
        for o, s, m, _p in self.results:
            parts.append("<ul>" + "".join(f"<li>{html.escape(x)}</li>" for x in R.explain(m, o, unit_t, ar)) + "</ul>")
        parts.append("<p style='color:#8b949e'>" + L(
            "The frozen prediction was re-simulated from its stored settings and was not changed. Agreement with one "
            "data set is evidence, not proof.",
            "أعيد حساب التوقع المجمّد من إعداداته المحفوظة ولم يتغير. التطابق مع مجموعة بيانات واحدة دليل وليس برهاناً.")
                     + "</p></div>")
        self.report.setHtml("".join(parts))

    def _validated(self):
        if self.fp is None or self.table is None:
            QMessageBox.information(self, L("Missing input", "مدخلات ناقصة"),
                                    L("Choose a prediction and import a CSV first.", "اختر توقعاً واستورد ملفاً أولاً."))
            return None
        cmap = self._cmap()
        series, errors, _w = R.validate(self.table, cmap, self.obs, self.lab.model)
        if errors:
            QMessageBox.warning(self, L("Please check the data", "يرجى مراجعة البيانات"), "\n".join(errors[:12]))
            return None
        return cmap, series

    def _calibrate(self):
        v = self._validated()
        if v is None:
            return
        from .calibration_dialog import CalibrationDialog
        cmap, series = v
        dlg = CalibrationDialog(self.fp, self.lab, self.table, cmap, self.obs, series, self)
        if dlg.exec() and dlg.new_pid is not None:
            self.refresh()
            i = self.pred_combo.findData(dlg.new_pid)
            if i >= 0:
                self.pred_combo.setCurrentIndex(i)

    def _save(self):
        if not self.results or self._snap is None:
            return
        fp, table, cmap, lab, traj = self._snap
        con = db.connect()
        path = R.save_report(con, fp, table, cmap, self.results, ROOT / "reports", lab, traj)
        QMessageBox.information(self, L("Report saved", "حُفظ التقرير"),
                                L(f"Saved:\n{path}\n\nThe measurements and this comparison were added to the database. "
                                  "The prediction itself was not changed.",
                                  f"حُفظ في:\n{path}\n\nأضيفت القياسات وهذه المقارنة إلى قاعدة البيانات، ولم يتغير "
                                  "التوقع نفسه."))
