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


# Arabic names of individual model parameters (symbol → name). Symbols that are shared by several
# models mean the same thing in each.
PARAM_AR = {
    "delta": "معدل التخفيف δ", "Ni": "النيتروجين الداخل Nᵢ", "bC": "أقصى معدل امتصاص للطحالب b_C",
    "KC": "ثابت نصف التشبع للطحالب K_C", "bB": "أقصى معدل تجنيد للدوّارات b_B", "KB": "ثابت نصف التشبع للدوّارات K_B",
    "eps": "كفاءة التمثيل ε", "m": "معدل موت الدوّارات m", "lam": "معدل تراجع الخصوبة λ",
    "T": "درجة الحرارة", "XS0": "لقاح S. thermophilus", "XL0": "لقاح L. bulgaricus", "Lac0": "اللاكتوز الابتدائي",
    "buf": "قوة التنظيم (البفر) في الحليب", "muS": "μ المثلى لـ S. thermophilus", "TminS": "أدنى حرارة لـ S. thermophilus",
    "ToptS": "الحرارة المثلى لـ S. thermophilus", "TmaxS": "أعلى حرارة لـ S. thermophilus",
    "pHminS": "أدنى pH لـ S. thermophilus", "aS": "نمو S. thermophilus بدون ببتيدات",
    "muL": "μ المثلى لـ L. bulgaricus", "TminL": "أدنى حرارة لـ L. bulgaricus", "ToptL": "الحرارة المثلى لـ L. bulgaricus",
    "TmaxL": "أعلى حرارة لـ L. bulgaricus", "pHminL": "أدنى pH لـ L. bulgaricus", "aL": "نمو L. bulgaricus بدون فورمات",
    "kP": "إطلاق الببتيدات بواسطة L. bulgaricus", "KP": "ثابت نصف التشبع للببتيدات", "P0": "الأحماض الأمينية/الببتيدات في الحليب",
    "yP": "استهلاك الببتيدات بواسطة S. thermophilus", "yF": "إنتاج الفورمات بواسطة S. thermophilus",
    "KF": "ثابت نصف التشبع للفورمات", "F0": "الفورمات من المعاملة الحرارية للحليب", "alpha": "الحمض لكل كتلة جديدة (α)",
    "betaS": "حمض الصيانة لـ S. thermophilus (β)", "betaL": "حمض الصيانة لـ L. bulgaricus (β)",
    "light": "الضوء", "aeration": "التهوية (تبادل الغازات)", "poly0": "البوليمرات المضافة", "sug0": "السكريات المضافة",
    "nh40": "النيتروجين المضاف", "inoculum": "لقاح كل كائن", "buffer": "قوة تنظيم الوسط", "ph_base": "الـ pH الابتدائي",
    "dilution": "التخفيف (التدفق المستمر)", "refuge": "ملجأ الفريسة", "det_rate": "تحلل البقايا العضوية",
    "mu_scale": "مضاعف معدل النمو",
}


def param_name(prm) -> str:
    """Parameter name in the current language (falls back to English)."""
    return PARAM_AR.get(prm.symbol, prm.name) if is_ar() else prm.name
