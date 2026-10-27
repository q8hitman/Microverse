"""MicroVerse main window: start screen → lab workspace, plus the organism library."""
from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QMessageBox, QStackedWidget

from .. import i18n
from ..i18n import L
from .start_screen import LibraryPage, StartScreen
from .workspace import Workspace

HOWTO_EN = """1. On the start screen pick a LAB — or build your own community of 2–5 organisms.
2. Pick a SCENARIO. Each one is a research question the simulation can answer.
3. Inside the lab:
   • LEFT: the parameters you control. The coloured dot shows how trustworthy each value is.
   • MIDDLE: the microscope view (drawn from the computed numbers) and the graphs.
     Drag the white line, or press Play, to move through time.
   • RIGHT ("Why?"): everything the model computed at that moment, the predicted outcome,
     the assumptions, and what you should measure in a real lab.
4. "Measure interactions" re-runs each organism alone and each pair together, then compares
   the final biomass to show who helps or harms whom, and why.
5. "Freeze prediction" stores the prediction permanently BEFORE you do the real experiment,
   so you cannot change it afterwards."""

HOWTO_AR = """1. في الشاشة الأولى اختر المختبر، أو ابنِ مجتمعك الخاص من 2 إلى 5 كائنات.
2. اختر السيناريو. كل سيناريو سؤال بحثي تستطيع المحاكاة الإجابة عليه.
3. داخل المختبر:
   • اليسار: المعاملات التي تتحكم بها، ولون النقطة يبيّن مدى موثوقية القيمة.
   • الوسط: منظر المجهر (مرسوم من الأرقام المحسوبة) والرسوم البيانية.
     اسحب الخط الأبيض أو اضغط تشغيل للتنقل في الزمن.
   • اليمين («ليش صار كذا؟»): كل ما حسبه النموذج في تلك اللحظة، والنتيجة المتوقعة،
     والافتراضات، وما الذي يجب أن تقيسه في المختبر الحقيقي.
4. «قياس التفاعلات» يعيد تشغيل كل كائن لوحده وكل زوج معاً، ثم يقارن الكتلة النهائية
   ليبيّن من يفيد من ومن يضره، ولماذا.
5. «تجميد التوقع» يحفظ التوقع نهائياً قبل إجراء التجربة الحقيقية، فلا يمكن تغييره بعدها."""

STATUS_EN = """MicroVerse 0.5

• Verified: the code solves the stated equations (automated tests).
• NOT validated: no model has been compared with laboratory data yet.
• Chemostat lab: literature parameters, still to be checked against Fussmann et al. (2000).
• Yoghurt and Community labs: exploratory. Traits are textbook estimates needing calibration.
• Microscope views: drawn counts follow the simulated state; each drawn cell represents a cohort.
  Shapes come from the literature; positions, swimming paths and division animations are illustrative.
• The usual teaching/food strains of every organism are Risk Group 1 in most national lists;
  classification is per strain and per country."""

STATUS_AR = """MicroVerse 0.5

• متحقق منه رياضياً: الكود يحل المعادلات المذكورة (اختبارات آلية).
• غير متحقق منه مخبرياً: لم يُقارن أي نموذج ببيانات مختبرية بعد.
• مختبر الكيموستات: معاملات من الأدبيات وتحتاج مراجعة على ورقة Fussmann وزملائه (2000).
• مختبرا اللبن والمجتمعات: استكشافيان، والصفات تقديرات من الكتب وتحتاج معايرة.
• مناظر المجهر: عدد الخلايا المرسومة يتبع الحالة المحسوبة، وكل خلية تمثل مجموعة. الأشكال من المراجع؛ المواقع ومسارات السباحة وحركات الانقسام توضيحية.
• السلالات المعتادة لكل الكائنات من مجموعة الخطورة 1 في أغلب القوائم الوطنية؛ التصنيف يعتمد على السلالة والدولة."""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(1640, 980)
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.workspace = None
        self.library = None
        self.start = None
        self._build()
        self._menu()

    def _build(self):
        for old in (self.start, self.library):
            if old is not None:
                self.stack.removeWidget(old)
                old.deleteLater()
        self.start = StartScreen()
        self.start.start.connect(self.open_lab)
        self.start.open_library.connect(lambda: self.stack.setCurrentWidget(self.library))
        self.start.lang_changed.connect(self.change_language)
        self.library = LibraryPage()
        self.library.back.connect(self.home)
        self.stack.addWidget(self.start)
        self.stack.addWidget(self.library)
        self.stack.setCurrentWidget(self.start)
        self.setWindowTitle(L("MicroVerse — microbiology simulation & prediction",
                              "MicroVerse — محاكاة وتوقّع ميكروبيولوجي"))

    def _menu(self):
        self.menuBar().clear()
        h = self.menuBar().addMenu(L("&Help", "&مساعدة"))
        h.addAction(QAction(L("How to use MicroVerse…", "كيف تستخدم البرنامج…"), self, triggered=self._howto))
        h.addAction(QAction(L("Scientific status…", "الحالة العلمية…"), self, triggered=self._about))

    def change_language(self, code: str):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        i18n.set_lang(code)
        # Arabic mirrors the whole layout (panels, menus, forms), not just the text
        QApplication.instance().setLayoutDirection(Qt.RightToLeft if code == "ar" else Qt.LeftToRight)
        if self.workspace is not None:
            self.stack.removeWidget(self.workspace)
            self.workspace.deleteLater()
            self.workspace = None
        self._build()
        self._menu()

    def open_lab(self, lab, scenario):
        if self.workspace is not None:
            self.stack.removeWidget(self.workspace)
            self.workspace.deleteLater()
        self.workspace = Workspace(lab, scenario)
        self.workspace.go_home.connect(self.home)
        self.stack.addWidget(self.workspace)
        self.stack.setCurrentWidget(self.workspace)
        self.setWindowTitle(f"MicroVerse — {L(lab.title, lab.title_ar)} › {L(scenario.title, scenario.title_ar)}")

    def home(self):
        self.stack.setCurrentWidget(self.start)

    def _howto(self):
        QMessageBox.information(self, L("How to use MicroVerse", "كيف تستخدم البرنامج"), L(HOWTO_EN, HOWTO_AR))

    def _about(self):
        QMessageBox.information(self, L("Scientific status", "الحالة العلمية"), L(STATUS_EN, STATUS_AR))
