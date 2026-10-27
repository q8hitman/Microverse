"""Bilingual text. `LANG` holds the language the user selected: "en" or "ar"."""
from __future__ import annotations

LANG = "en"


def set_lang(code: str) -> None:
    global LANG
    LANG = "ar" if code == "ar" else "en"


def is_ar() -> bool:
    return LANG == "ar"


def L(en: str, ar: str) -> str:
    """Pick the right language for one piece of text."""
    return ar if LANG == "ar" else en


def rtl(text: str) -> str:
    """Wrap in a right-to-left block when Arabic is active (for HTML)."""
    return f"<div dir='rtl' style='text-align:right'>{text}</div>" if LANG == "ar" else text


# --- words that appear in many places ---------------------------------------
UI = {
    "why": ("Why? — what the model computed", "ليش صار كذا؟ – ما الذي حسبه النموذج"),
    "prediction": ("Prediction", "التوقع"),
    "question": ("Question", "السؤال"),
    "status": ("Status", "الحالة"),
    "now": ("What is happening right now", "ما الذي يحدث الآن"),
    "terms": ("The numbers behind it", "الأرقام وراء ذلك"),
    "outcome": ("Predicted outcome of this run", "النتيجة المتوقعة لهذه التجربة"),
    "assumptions": ("Assumptions (what the model ignores)", "الافتراضات (ما الذي يتجاهله النموذج)"),
    "alternatives": ("Other things that could really happen", "أشياء أخرى قد تحدث فعلاً"),
    "measure": ("How to test this in the lab", "كيف تختبر هذا في المختبر"),
    "sensitivity": ("Which parameters matter most", "أي المعاملات أكثر تأثيراً"),
    "interactions": ("How the organisms affect each other", "كيف تؤثر الكائنات على بعضها"),
    "scenario": ("Scenario", "السيناريو"),
    "organisms": ("Organisms", "الكائنات"),
    "environment": ("Environment", "البيئة"),
    "home": ("Home", "الرئيسية"),
    "play": ("Play", "تشغيل"),
    "pause": ("Pause", "إيقاف"),
    "speed": ("speed", "السرعة"),
    "computing": ("computing…", "جاري الحساب…"),
    "not_validated": ("verified maths, NOT yet validated against laboratory data",
                      "رياضياً متحقق منه، لكنه غير مُتحقَّق منه مخبرياً بعد"),
    "exploratory": ("EXPLORATORY: parameters are estimates, use the result to form hypotheses, then measure",
                    "استكشافي: المعاملات تقديرية، استخدم النتيجة لصياغة فرضيات ثم قِس فعلياً"),
}


def t(key: str) -> str:
    en, ar = UI[key]
    return ar if LANG == "ar" else en


# Parameter-group headings used by the labs
GROUPS = {
    "Vessel & medium (what the experimenter controls)": "الوعاء والوسط (ما يتحكم به الباحث)",
    "Chlorella vulgaris (prey)": "كلوريلا فولغاريس (الفريسة)",
    "Brachionus calyciflorus (predator)": "براكيونس كاليسيفلورس (المفترس)",
    "Process (what you control)": "العملية (ما تتحكم به)",
    "Streptococcus thermophilus": "ستربتوكوكس ثيرموفيلس",
    "Lactobacillus bulgaricus": "لاكتوباسيلس بلغاريكس",
    "Shared chemistry": "الكيمياء المشتركة",
    "Environment you control": "البيئة التي تتحكم بها",
    "Food you add": "الغذاء الذي تضيفه",
    "Vessel behaviour": "سلوك الوعاء",
}


def group(name: str) -> str:
    return GROUPS.get(name, name) if LANG == "ar" else name


def num(x: float, digits: int = 2) -> str:
    return f"{x:.{digits}f}"
