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


# --- audience: "research" shows every control; "school" hides the advanced ones (same engine, same numbers) ---
MODE = "research"


def set_mode(code: str) -> None:
    global MODE
    MODE = "school" if code == "school" else "research"


def is_school() -> bool:
    return MODE == "school"


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


# Display strings defined in lab definitions (plot titles, axis labels, series names, scan titles).
TERMS_AR = {
    "B — all rotifers": "B — كل الدوّارات", "C — Chlorella": "C — كلوريلا", "N — dissolved nitrogen": "N — النيتروجين الذائب",
    "R — egg-bearing rotifers": "R — الدوّارات الحاملة للبيض", "Populations and nutrient": "الأعداد والمغذيات",
    "Bacteria": "البكتيريا", "CFU/mL (log scale)": "CFU/مل (مقياس لوغاريتمي)", "Food and products": "الغذاء والنواتج",
    "Organisms": "الكائنات", "Sugar and acid": "السكر والحمض", "pH and oxygen": "الحموضة والأكسجين",
    "pH of the milk": "حموضة الحليب", "Regime scan (δ)": "مسح الأنظمة (δ)", "Temperature scan": "مسح درجة الحرارة",
    "acetate": "أسيتات", "biomass (mg/L)": "الكتلة الحيوية (ملغم/ل)", "end point": "نقطة النهاية", "ethanol": "إيثانول",
    "galactose": "جالاكتوز", "gel onset": "بداية التخثر", "lactate": "لاكتات", "lactic acid": "حمض اللاكتيك",
    "lactose": "لاكتوز", "nitrogen": "نيتروجين", "oxygen (mg/L)": "أكسجين (ملغم/ل)", "polymers": "بوليمرات",
    "pH": "الحموضة (pH)", "sugars": "سكريات", "pH  /  O₂ (mg/L)": "الحموضة / أكسجين (ملغم/ل)", "time": "الزمن",
    "measured": "مقاس", "literature estimate": "تقدير من المراجع", "fitted": "معاير", "derived": "مشتق",
    "assumed (exploratory)": "مفترض (استكشافي)", "you control it": "تتحكم فيه أنت", "× full daylight": "× ضوء النهار الكامل",
}


def tr(text: str) -> str:
    """Translate a display string from a lab definition when the interface is Arabic (else unchanged)."""
    if not is_ar():
        return text
    if text in TERMS_AR:
        return TERMS_AR[text]
    from .library.organisms import ORGANISMS
    for o in ORGANISMS.values():                     # organism names in series labels
        if text == o.name:
            return o.name_ar
    return text

TERMS_AR.update({
    # scenario questions
    "At an intermediate dilution rate, do algae and rotifers oscillate instead of settling?":
        "عند معدل تخفيف متوسط، هل تتذبذب الطحالب والدوّارات بدلاً من أن تستقر؟",
    "With very slow medium exchange, do the oscillations die out?": "مع تبديل بطيء جداً للوسط، هل يخمد التذبذب؟",
    "Near the rotifers' limit, do both species settle at a steady level?": "قرب حد الدوّارات، هل يستقر النوعان عند مستوى ثابت؟",
    "If the vessel is diluted faster than rotifers can reproduce, what happens to each species?":
        "إذا خُفّف الوعاء أسرع مما تتكاثر الدوّارات، ماذا يحدث لكل نوع؟",
    "Above which dilution rate can even the algae not persist?": "فوق أي معدل تخفيف لا تستطيع حتى الطحالب البقاء؟",
    "Does adding more nutrient (Nᵢ = 160) destabilise a system that was stable?":
        "هل تؤدي زيادة المغذيات (Nᵢ = 160) إلى زعزعة نظام كان مستقراً؟",
    "In a 5 mL vessel, can random births and deaths wipe out the rotifers during a cycle trough?":
        "في وعاء 5 مل، هل تستطيع الولادات والوفيات العشوائية إفناء الدوّارات عند قاع الدورة؟",
    "With a 1:1 starter at 43 °C, how long until the milk sets at pH 4.6?":
        "مع بادئ بنسبة 1:1 عند 43 °م، كم يحتاج الحليب ليتخثر عند pH 4.6؟",
    "Without its partner, how much slower is acidification, and where does it stop?":
        "بدون شريكه، كم يكون التحميض أبطأ، وأين يتوقف؟",
    "Can the rod acidify milk on its own in a normal fermentation time?": "هل تستطيع العصية تحميض الحليب وحدها في زمن تخمير عادي؟",
    "What does a lower temperature do to timing and to the balance between the species?":
        "ماذا تفعل الحرارة الأقل بالتوقيت وبالتوازن بين النوعين؟",
    "Near the cardinal maximum, which organism fails first?": "قرب الحد الأعلى للحرارة، أي كائن يفشل أولاً؟",
    "If the yoghurt is left warm for 16 h, how sour does it become and who keeps acidifying?":
        "إذا تُرك اللبن دافئاً 16 ساعة، كم يصبح حامضاً ومن يستمر في التحميض؟",
    "With stronger milk buffering (×1.4), how much longer to pH 4.6?": "مع تنظيم أقوى في الحليب (×1.4)، كم يزيد الزمن حتى pH 4.6؟",
    "Does changing the starter ratio change speed and final composition?": "هل يغيّر تغيير نسبة البادئ السرعة والتركيب النهائي؟",
    "Can three levels of a food web coexist, and do their numbers rise and fall in turn?":
        "هل تتعايش ثلاثة مستويات من شبكة غذائية، وهل ترتفع أعدادها وتنخفض بالتناوب؟",
    "Which lactic acid bacterium finishes the fermentation, and at what pH does each one stop?":
        "أي بكتيريا لاكتيك تُكمل التخمير، وعند أي pH يتوقف كل منها؟",
    "Can one organism live on the waste product of another?": "هل يستطيع كائن أن يعيش على فضلات كائن آخر؟",
    "Does adding the vinegar bacterium at the same time help or hurt?": "هل تفيد إضافة بكتيريا الخل في نفس الوقت أم تضر؟",
    "Polymers → lactate → acetate → methane: does each organism depend on the one before it?":
        "بوليمرات ← لاكتات ← أسيتات ← ميثان: هل يعتمد كل كائن على الذي قبله؟",
    "In a closed vessel, can an alga keep an aerobic bacterium alive? What happens in the dark?":
        "في وعاء مغلق، هل يستطيع طحلب إبقاء بكتيريا هوائية حية؟ وماذا يحدث في الظلام؟",
    "Three fast growers, one pot of sugar: who wins, and does the acid decide it?":
        "ثلاثة كائنات سريعة النمو ووعاء سكر واحد: من يفوز، وهل يحسم الحمض النتيجة؟",
    "With no free sugar, can a bacterium survive next to a mould that makes enzymes?":
        "بدون سكر حر، هل تعيش بكتيريا بجانب فطر ينتج إنزيمات؟",
    "Who competes for nitrogen, and who brings new nitrogen in?": "من يتنافس على النيتروجين، ومن يُدخل نيتروجيناً جديداً؟",
    "Which organisms survive together, and how do they change each other?": "أي الكائنات تعيش معاً، وكيف يغيّر بعضها بعضاً؟",
})
