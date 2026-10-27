"""Start screen: pick a lab (or build your own community), then a scenario. Plus the organism library."""
from __future__ import annotations

import html

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QScrollArea, QVBoxLayout, QWidget)

from ..i18n import L, is_ar
from ..labs import PLANNED, community_lab, fixed_labs
from ..labs.base import Lab, Scenario
from ..labs.community import PRESETS
from ..library.organisms import ORGANISMS, by_group
from .organism_card import OrganismCard, Portrait
from .style import MUTED, TEXT_2

MAX_PICK = 5


class ClickCard(QFrame):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)          # reachable with Tab, activated with Enter / Space

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(ev)

    def set_selected(self, on: bool):
        self.setObjectName("cardSelected" if on else "card")
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, ev):
        self.clicked.emit()
        super().mousePressEvent(ev)


def _clear(lay):
    while lay.count():
        it = lay.takeAt(0)
        if it.widget():
            it.widget().deleteLater()
        elif it.layout():
            _clear(it.layout())


class StartScreen(QWidget):
    start = Signal(object, object)          # (Lab, Scenario)
    open_library = Signal()
    open_reality = Signal()
    lang_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lab: Lab | None = None
        self.scenario: Scenario | None = None
        self.custom_keys: list[str] = []
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 16)

        head = QHBoxLayout()
        hv = QVBoxLayout()
        t = QLabel("MicroVerse")
        t.setObjectName("h1")
        hv.addWidget(t)
        self.sub = QLabel()
        self.sub.setObjectName("muted")
        hv.addWidget(self.sub)
        head.addLayout(hv, 1)
        self.lang = QComboBox()
        self.lang.addItem("English", "en")
        self.lang.addItem("العربية", "ar")
        self.lang.setCurrentIndex(1 if is_ar() else 0)
        self.lang.currentIndexChanged.connect(lambda i: self.lang_changed.emit(self.lang.itemData(i)))
        head.addWidget(self.lang, 0, Qt.AlignTop)
        self.lib_btn = QPushButton()
        self.lib_btn.clicked.connect(self.open_library)
        head.addWidget(self.lib_btn, 0, Qt.AlignTop)
        self.real_btn = QPushButton()
        self.real_btn.clicked.connect(self.open_reality)
        head.addWidget(self.real_btn, 0, Qt.AlignTop)
        root.addLayout(head)

        body = QHBoxLayout()
        body.setSpacing(16)
        left = QWidget()
        self.left_lay = QVBoxLayout(left)
        left_scroll = QScrollArea(widgetResizable=True)
        left_scroll.setWidget(left)
        left_scroll.setMaximumWidth(430)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body.addWidget(left_scroll)
        self.detail = QVBoxLayout()
        dw = QWidget()
        dw.setLayout(self.detail)
        scroll = QScrollArea(widgetResizable=True)
        scroll.setWidget(dw)
        body.addWidget(scroll, 1)
        root.addLayout(body, 1)
        self.rebuild()

    # ------------------------------------------------------------------
    def rebuild(self):
        self.sub.setText(L("Microbiology simulation &amp; prediction lab<br>"
                           "<span style='color:#6e7681'>Hypothesis → Prediction → Visualization → Explanation → "
                           "Lab validation</span>",
                           "مختبر محاكاة وتوقّع ميكروبيولوجي<br>"
                           "<span style='color:#6e7681'>فرضية ← توقع ← تصوّر ← تفسير ← تحقق مخبري</span>"))
        self.lib_btn.setText(L("📚 Organism library", "📚 مكتبة الكائنات"))
        self.real_btn.setText(L("📏 Prediction vs Reality", "📏 التوقع مقابل الواقع"))
        self.real_btn.setToolTip(L("Compare a frozen prediction with your laboratory measurements (CSV).",
                                   "قارن توقعاً مجمّداً بقياساتك المخبرية (CSV)."))
        lay = self.left_lay
        _clear(lay)
        h = QLabel(L("1 · Choose a lab", "1 · اختر المختبر"))
        h.setObjectName("h2")
        lay.addWidget(h)
        self.lab_cards = {}
        for lab in fixed_labs():
            lay.addWidget(self._lab_card(lab, lab.key))
        # community presets
        h2 = QLabel(L("Community Builder — ready-made communities", "باني المجتمعات – مجتمعات جاهزة"))
        h2.setObjectName("h2")
        lay.addWidget(h2)
        for key, keys, en, ar, q, ov, te in PRESETS:
            lab = community_lab(keys, key)
            lay.addWidget(self._lab_card(lab, f"preset:{key}", title=(en, ar), keys=keys))
        # custom builder
        h3 = QLabel(L("… or build your own", "… أو ابنِ مجتمعك"))
        h3.setObjectName("h2")
        lay.addWidget(h3)
        card = ClickCard()
        cl = QVBoxLayout(card)
        cl.addWidget(QLabel(L("<b>Custom community</b><br>Pick 2–5 organisms yourself",
                              "<b>مجتمع مخصص</b><br>اختر من 2 إلى 5 كائنات بنفسك")))
        card.clicked.connect(self.show_builder)
        lay.addWidget(card)
        self.lab_cards["custom"] = card
        soon = QLabel(L("Coming next", "قريباً"))
        soon.setObjectName("muted")
        lay.addWidget(soon)
        g = QGridLayout()
        for i, (en, ar, d) in enumerate(PLANNED):
            w = QLabel(f"<b>{html.escape(L(en, ar))}</b><br><span style='font-size:8pt'>{html.escape(d)}</span>")
            w.setWordWrap(True)
            w.setStyleSheet(f"color:{MUTED}; border:1px dashed #30363d; border-radius:8px; padding:5px")
            g.addWidget(w, i // 2, i % 2)
        lay.addLayout(g)
        lay.addStretch(1)
        first = fixed_labs()[0]
        self.select_lab(first, first.key)

    def _lab_card(self, lab: Lab, card_key: str, title=None, keys=None):
        card = ClickCard()
        cl = QVBoxLayout(card)
        name = L(*title) if title else L(lab.title, lab.title_ar)
        cl.addWidget(QLabel(f"<span style='font-size:12pt; font-weight:700; color:{lab.accent}'>{html.escape(name)}</span>"))
        if not title:
            tg = QLabel(html.escape(L(lab.tagline, lab.tagline_ar)))
            tg.setWordWrap(True)
            cl.addWidget(tg)
        row = QHBoxLayout()
        for k in (keys or lab.organisms):
            o = ORGANISMS[k]
            lbl = QLabel(f"<span style='color:{o.colour}'>●</span> {html.escape(L(o.name.split(' subsp.')[0], o.name_ar))}")
            lbl.setStyleSheet("font-size:8pt")
            row.addWidget(lbl)
        row.addStretch(1)
        cl.addLayout(row)
        card.clicked.connect(lambda l=lab, k=card_key: self.select_lab(l, k))
        self.lab_cards[card_key] = card
        return card

    # ------------------------------------------------------------------
    def select_lab(self, lab: Lab, card_key: str):
        self.lab = lab
        for k, c in self.lab_cards.items():
            c.set_selected(k == card_key)
        d = self.detail
        _clear(d)
        d.addWidget(QLabel(f"<span style='font-size:15pt; font-weight:700'>{html.escape(L(lab.title, lab.title_ar))}</span>"))
        desc = QLabel(html.escape(lab.description))
        desc.setWordWrap(True)
        d.addWidget(desc)
        chip = QLabel("⚑ " + html.escape(lab.status))
        chip.setWordWrap(True)
        chip.setStyleSheet(f"color:{lab.status_colour}; border:1px solid {lab.status_colour}; border-radius:8px; padding:4px 8px")
        d.addWidget(chip)
        h = QLabel(L("2 · The organisms in this lab", "2 · الكائنات في هذا المختبر"))
        h.setObjectName("h2")
        d.addWidget(h)
        for k in lab.organisms:
            d.addWidget(OrganismCard(ORGANISMS[k], compact=True))
        h = QLabel(L("3 · Choose a scenario (a research question)", "3 · اختر السيناريو (سؤال بحثي)"))
        h.setObjectName("h2")
        d.addWidget(h)
        self.sc_cards = []
        grid = QGridLayout()
        for i, sc in enumerate(lab.scenarios):
            card = ClickCard()
            cl = QVBoxLayout(card)
            lb = QLabel(f"<b>{html.escape(L(sc.title, sc.title_ar))}</b>"
                        f"<br><span style='color:{TEXT_2}; font-size:9pt'>{html.escape(sc.question)}</span>")
            lb.setWordWrap(True)
            cl.addWidget(lb)
            card.clicked.connect(lambda s=sc, c=card: self.select_scenario(s, c))
            card.mouseDoubleClickEvent = lambda ev, s=sc: self.start.emit(self.lab, s)
            grid.addWidget(card, i // 2, i % 2)
            self.sc_cards.append(card)
        d.addLayout(grid)
        row = QHBoxLayout()
        row.addStretch(1)
        btn = QPushButton(L("Start lab ▶", "ابدأ المختبر ▶"))
        btn.setObjectName("primary")
        btn.setMinimumWidth(200)
        btn.clicked.connect(lambda: self.start.emit(self.lab, self.scenario))
        row.addWidget(btn)
        d.addLayout(row)
        d.addStretch(1)
        self.select_scenario(lab.scenarios[0], self.sc_cards[0])

    def select_scenario(self, sc: Scenario, card):
        self.scenario = sc
        for c in self.sc_cards:
            c.set_selected(c is card)

    # ------------------------------------------------------------- builder
    def show_builder(self):
        for k, c in self.lab_cards.items():
            c.set_selected(k == "custom")
        d = self.detail
        _clear(d)
        d.addWidget(QLabel(f"<span style='font-size:15pt; font-weight:700'>"
                           f"{html.escape(L('Build your own community', 'ابنِ مجتمعك الميكروبي'))}</span>"))
        info = QLabel(L("Pick 2–5 organisms. The simulation builds its equations from their traits, so what happens "
                        "between them (competition, predation, cross-feeding, acid, oxygen) comes out of the biology, "
                        "not out of a script.",
                        "اختر من 2 إلى 5 كائنات. المحاكاة تبني معادلاتها من صفاتها، فما يحدث بينها (تنافس، افتراس، "
                        "تغذية تبادلية، حموضة، أكسجين) ينتج من الأحياء نفسها وليس من نص مكتوب مسبقاً."))
        info.setWordWrap(True)
        d.addWidget(info)
        self.pick_label = QLabel()
        self.pick_label.setObjectName("h2")
        d.addWidget(self.pick_label)
        self.search = QLineEdit()
        self.search.setPlaceholderText(L("Search by name, group or role…", "ابحث بالاسم أو المجموعة أو الدور…"))
        self.search.textChanged.connect(lambda _: self._fill_picker())
        d.addWidget(self.search)
        self.picker_box = QVBoxLayout()
        d.addLayout(self.picker_box)
        row = QHBoxLayout()
        row.addStretch(1)
        self.build_btn = QPushButton(L("Start with these ▶", "ابدأ بهذه الكائنات ▶"))
        self.build_btn.setObjectName("primary")
        self.build_btn.setMinimumWidth(220)
        self.build_btn.clicked.connect(self._start_custom)
        row.addWidget(self.build_btn)
        d.addLayout(row)
        d.addStretch(1)
        self._fill_picker()

    def _fill_picker(self):
        _clear(self.picker_box)
        q = self.search.text().strip().lower() if hasattr(self, "search") else ""
        self.checks = {}
        for group, items in by_group().items():
            shown = [o for o in items if not q or q in (o.name + o.name_ar + o.group + o.common
                                                        + o.role + o.role_ar).lower()]
            if not shown:
                continue
            g = QLabel(html.escape(L(group, shown[0].group_ar.split(" –")[0])))
            g.setStyleSheet(f"color:{TEXT_2}; font-weight:600; margin-top:4px")
            self.picker_box.addWidget(g)
            grid = QGridLayout()
            for i, o in enumerate(shown):
                cb = QCheckBox()
                cb.setChecked(o.key in self.custom_keys)
                cb.toggled.connect(lambda on, k=o.key: self._toggle(k, on))
                lbl = QLabel(f"<span style='color:{o.colour}'>●</span> "
                             f"<b>{html.escape(L(o.name.split(' subsp.')[0], o.name_ar))}</b>"
                             f"<br><span style='color:{TEXT_2}; font-size:8pt'>"
                             f"{html.escape(L(o.feeding_label[0], o.feeding_label[1]))} · "
                             f"{html.escape(L(o.oxygen_label[0], o.oxygen_label[1]))} · {o.size_um:g} µm</span>")
                lbl.setWordWrap(True)
                cell = QHBoxLayout()
                cell.addWidget(cb, 0, Qt.AlignTop)
                cell.addWidget(Portrait(o, small=True), 0, Qt.AlignTop)
                cell.addWidget(lbl, 1)
                w = QWidget()
                w.setLayout(cell)
                grid.addWidget(w, i // 2, i % 2)
                self.checks[o.key] = cb
            self.picker_box.addLayout(grid)
        self._update_pick_label()

    def _toggle(self, key: str, on: bool):
        if on and key not in self.custom_keys:
            if len(self.custom_keys) >= MAX_PICK:
                self.checks[key].setChecked(False)
                return
            self.custom_keys.append(key)
        elif not on and key in self.custom_keys:
            self.custom_keys.remove(key)
        self._update_pick_label()

    def _update_pick_label(self):
        names = ", ".join(L(ORGANISMS[k].name.split(" subsp.")[0], ORGANISMS[k].name_ar) for k in self.custom_keys)
        self.pick_label.setText(L(f"Selected {len(self.custom_keys)} / {MAX_PICK}: {names or '—'}",
                                  f"المختار {len(self.custom_keys)} من {MAX_PICK}: {names or '—'}"))
        if hasattr(self, "build_btn"):
            self.build_btn.setEnabled(len(self.custom_keys) >= 2)

    def _start_custom(self):
        keys = tuple(self.custom_keys)
        lab = community_lab(keys, "custom")
        self.start.emit(lab, lab.scenarios[0])


class LibraryPage(QWidget):
    back = Signal()

    def __init__(self, parent=None):
        from PySide6.QtWidgets import QTabWidget
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 16)
        head = QHBoxLayout()
        b = QPushButton(L("◀ Home", "◀ الرئيسية"))
        b.clicked.connect(self.back)
        head.addWidget(b)
        t = QLabel(L("Organism Library", "مكتبة الكائنات"))
        t.setObjectName("h1")
        head.addWidget(t, 1)
        pdf = QPushButton(L("⬇ Printable Guide (PDF)", "⬇ دليل للطباعة (PDF)"))
        pdf.setToolTip(L("A reference document with every function and every organism, for students and lecturers.",
                         "مستند مرجعي بكل الوظائف وكل الكائنات، للطلبة والدكاترة."))
        pdf.clicked.connect(self._export_pdf)
        head.addWidget(pdf)
        csvb = QPushButton(L("⬇ Spreadsheet (CSV)", "⬇ جدول بيانات (CSV)"))
        csvb.setToolTip(L("Opens in Excel; Arabic is preserved.", "يفتح في إكسل مع الحفاظ على العربي."))
        csvb.clicked.connect(self._export_csv)
        head.addWidget(csvb)
        root.addLayout(head)
        note = QLabel(L(f"{len(ORGANISMS)} organisms; their usual teaching/food strains are Risk Group 1 (low risk). Every card says what the organism DOES, "
                        "and how the simulation represents it — so you can look it up any time you forget.",
                        f"{len(ORGANISMS)} كائناً، وسلالاتها المعتادة في التدريس والغذاء من مجموعة الخطورة 1 (منخفضة الخطورة). كل بطاقة توضح وظيفة الكائن "
                        "وكيف تمثله المحاكاة، فتقدر ترجع لها متى ما نسيت."))
        note.setObjectName("muted")
        note.setWordWrap(True)
        root.addWidget(note)
        self.search = QLineEdit()
        self.search.setPlaceholderText(L("Search by name, group, function or role…", "ابحث بالاسم أو المجموعة أو الوظيفة أو الدور…"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _: self._fill())
        root.addWidget(self.search)
        tabs = QTabWidget()
        self.by_org = QVBoxLayout()
        self.by_fn = QVBoxLayout()
        for lay, title in ((self.by_org, L("By Organism", "حسب الكائن")), (self.by_fn, L("By Function", "حسب الوظيفة"))):
            w = QWidget()
            w.setLayout(lay)
            sc = QScrollArea(widgetResizable=True)
            sc.setWidget(w)
            tabs.addTab(sc, title)
        root.addWidget(tabs, 1)
        self._fill()

    def _match(self, o) -> bool:
        from ..library.functions import functions_of
        q = self.search.text().strip().lower()
        if not q:
            return True
        hay = (o.name + o.name_ar + o.group + o.group_ar + o.common + o.common_ar + o.role + o.role_ar
               + " ".join(f.name + f.name_ar for f in functions_of(o.key))).lower()
        return q in hay

    def _fill(self):
        from ..library.functions import FUNCTIONS, organisms_with
        _clear(self.by_org)
        for group, items in by_group().items():
            shown = [o for o in items if self._match(o)]
            if not shown:
                continue
            h = QLabel(html.escape(L(group, shown[0].group_ar.split(" –")[0])))
            h.setObjectName("h2")
            self.by_org.addWidget(h)
            for o in shown:
                self.by_org.addWidget(OrganismCard(o))
        self.by_org.addStretch(1)

        _clear(self.by_fn)
        for f in FUNCTIONS.values():
            who = [o for o in organisms_with(f.key) if self._match(o)]
            if not who:
                continue
            card = QFrame()
            card.setObjectName("card")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(12, 10, 12, 10)
            title = QLabel(f"<span style='font-size:13pt; font-weight:700; color:{f.colour}'>{html.escape(f.icon)} "
                           f"{html.escape(L(f.name, f.name_ar))}</span>")
            cl.addWidget(title)
            body = QLabel(f"{html.escape(L(f.meaning, f.meaning_ar))}"
                          + (f"<br><span style='color:{TEXT_2}'>{L('In the simulation', 'في المحاكاة')}: "
                             f"{html.escape(L(f.in_model, f.in_model_ar))}</span>" if f.in_model else
                             f"<br><span style='color:{TEXT_2}'>{L('Information only — not simulated.', 'للمعلومة فقط – غير ممثل في المحاكاة.')}</span>")
                          + f"<br><span style='color:{TEXT_2}'>{L('Try it', 'جرّبها')}: {html.escape(L(f.example, f.example_ar))}</span>")
            body.setWordWrap(True)
            cl.addWidget(body)
            grid = QGridLayout()
            for i, o in enumerate(who):
                cell = QHBoxLayout()
                cell.addWidget(Portrait(o, small=True))
                lbl = QLabel(f"<b style='color:{o.colour}'>{html.escape(L(o.name.split(' subsp.')[0], o.name_ar))}</b>"
                             f"<br><span style='color:{TEXT_2}; font-size:8pt'>{html.escape(L(o.role, o.role_ar))}</span>")
                lbl.setWordWrap(True)
                cell.addWidget(lbl, 1)
                w = QWidget()
                w.setLayout(cell)
                grid.addWidget(w, i // 2, i % 2)
            cl.addLayout(grid)
            self.by_fn.addWidget(card)
        self.by_fn.addStretch(1)

    def _export_pdf(self):
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from ..library.guide import export_pdf
        path, _ = QFileDialog.getSaveFileName(self, L("Save guide", "حفظ الدليل"),
                                              L("MicroVerse_organism_guide.pdf", "دليل_كائنات_MicroVerse.pdf"), "PDF (*.pdf)")
        if path:
            export_pdf(path)
            QMessageBox.information(self, L("Saved", "تم الحفظ"), path)

    def _export_csv(self):
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from ..data.db import export_organisms_csv
        path, _ = QFileDialog.getSaveFileName(self, L("Save spreadsheet", "حفظ الجدول"), "MicroVerse_organisms.csv", "CSV (*.csv)")
        if path:
            export_organisms_csv(path)
            QMessageBox.information(self, L("Saved", "تم الحفظ"), path)
