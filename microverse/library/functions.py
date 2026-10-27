"""Ecological / technological FUNCTIONS of organisms — the "what does it do?" reference.

Most functions are DERIVED FROM THE TRAITS that the simulation uses (so the label and the
behaviour can never disagree). A few that the model does not represent (food starter,
model organism, extremophile) are assigned by hand and marked as such.
"""
from __future__ import annotations

from dataclasses import dataclass

from .organisms import ORGANISMS, Organism


@dataclass(frozen=True)
class Function:
    key: str
    icon: str
    colour: str
    name: str
    name_ar: str
    meaning: str          # what it means, in plain words
    meaning_ar: str
    in_model: str         # how the simulation represents it (empty = not simulated)
    in_model_ar: str
    example: str          # a concrete thing you can try in MicroVerse
    example_ar: str


FUNCTIONS: dict[str, Function] = {f.key: f for f in [
    Function("producer", "☀", "#3fb950", "Primary producer", "منتج أولي",
             "Makes new organic matter from light and CO₂. Everything else in a food web ultimately lives on it.",
             "يصنع مادة عضوية جديدة من الضوء وثاني أكسيد الكربون، وكل الشبكة الغذائية تعتمد عليه في النهاية.",
             "Grows on light × nitrogen; needs no organic food.",
             "ينمو بالضوء والنيتروجين، ولا يحتاج غذاءً عضوياً.",
             "Set Light to 0 and watch it stop growing.", "اجعل الضوء صفراً وشاهد توقفه عن النمو."),
    Function("oxygen", "O₂", "#58a6ff", "Oxygen producer", "منتج للأكسجين",
             "Releases oxygen while photosynthesising, which aerobic organisms then breathe.",
             "يطلق الأكسجين أثناء البناء الضوئي، فتتنفسه الكائنات الهوائية.",
             "Adds 1.4 mg O₂ per mg of new biomass to the dissolved-oxygen pool.",
             "يضيف 1.4 ملغم أكسجين لكل ملغم كتلة جديدة إلى الأكسجين الذائب.",
             "Preset 'Sealed jar': an alga keeps an aerobic bacterium alive.",
             "السيناريو «وعاء مغلق»: طحلب يبقي بكتيريا هوائية حية."),
    Function("lactic", "🥛", "#79c0ff", "Lactic acid fermenter", "مخمّر لحمض اللاكتيك",
             "Turns sugar into lactic acid. This acidifies and preserves food (yoghurt, cheese, pickles).",
             "يحوّل السكر إلى حمض اللاكتيك، فيحمّض الغذاء ويحفظه (لبن، جبن، مخللات).",
             "A fixed fraction of the sugar it eats becomes lactate, which lowers the pH.",
             "جزء ثابت من السكر الذي يأكله يتحول إلى لاكتات تخفض الحموضة.",
             "Preset 'Pickle jar'.", "السيناريو «مرطبان مخلل»."),
    Function("alcohol", "🍷", "#e3b341", "Alcohol fermenter", "مخمّر للكحول",
             "Turns sugar into ethanol and CO₂ (bread, beer, wine).",
             "يحوّل السكر إلى إيثانول وغاز ثاني أكسيد الكربون (خبز، بيرة، نبيذ).",
             "Releases ethanol into the shared pool, where others may eat it.",
             "يطلق الإيثانول في المخزون المشترك حيث قد تأكله كائنات أخرى.",
             "Preset 'Wine to vinegar'.", "السيناريو «من النبيذ إلى الخل»."),
    Function("acidifier", "pH↓", "#f0883e", "Acidifier", "مُحمِّض",
             "Lowers the pH of its surroundings. This can shut down acid-sensitive neighbours — and eventually itself.",
             "يخفض حموضة الوسط، وقد يوقف جيرانه الحساسين للحموضة ثم يوقف نفسه في النهاية.",
             "Its lactate/acetate enters a charge balance that sets the pH everyone experiences.",
             "اللاكتات أو الأسيتات التي ينتجها تدخل في معادلة تحدد الحموضة التي يعيشها الجميع.",
             "Raise 'Medium buffering' and see the pH drop less.", "ارفع «قدرة الوسط على التنظيم» وشاهد انخفاضاً أقل."),
    Function("decomposer", "✂", "#a371f7", "Decomposer (enzyme producer)", "محلِّل (منتج إنزيمات)",
             "Secretes enzymes that cut polymers (starch, protein, cellulose) into small sugars — food that others can then use too.",
             "يفرز إنزيمات تقطع البوليمرات (نشا، بروتين، سليولوز) إلى سكريات صغيرة يستفيد منها الآخرون أيضاً.",
             "Converts the polymer pool into the sugar pool outside the cell, for everyone.",
             "يحوّل مخزون البوليمرات إلى سكريات خارج الخلية، للجميع.",
             "Preset 'Only polymers: who can open the food?'.", "السيناريو «بوليمرات فقط»."),
    Function("crossfeeder", "⇄", "#2dd4bf", "Cross-feeder", "متغذٍّ تبادلي",
             "Lives on a waste product of another organism (lactate, acetate or ethanol).",
             "يعيش على فضلات كائن آخر (لاكتات أو أسيتات أو إيثانول).",
             "Eats from a pool that other organisms fill with their products.",
             "يأكل من مخزون تملؤه كائنات أخرى بنواتجها.",
             "Preset 'Swiss cheese'.", "السيناريو «الجبن السويسري»."),
    Function("scavenger", "♻", "#39d353", "Aerobic scavenger", "كنّاس هوائي",
             "With oxygen, eats almost any small organic molecule — including leftovers from fermenters.",
             "مع الأكسجين يأكل تقريباً أي جزيء عضوي صغير، حتى بقايا المخمّرات.",
             "Uses several organic pools at once, but only when oxygen is present.",
             "يستهلك عدة مخزونات عضوية معاً، لكن فقط بوجود الأكسجين.",
             "Add Pseudomonas to a lactic community with aeration on.", "أضف سودوموناس إلى مجتمع لاكتيك مع التهوية."),
    Function("bacterivore", "🦠→", "#d29922", "Bacterial grazer", "راعٍ للبكتيريا",
             "Eats bacteria and other very small cells. Controls bacterial numbers and recycles nutrients.",
             "يأكل البكتيريا والخلايا الصغيرة جداً، فيضبط أعدادها ويعيد تدوير المغذيات.",
             "Holling type II grazing on prey smaller than its size limit.",
             "رعي من نوع هولينغ الثاني على الفرائس الأصغر من حده.",
             "Add Tetrahymena to E. coli.", "أضف تيتراهيمينا إلى إشريشيا كولاي."),
    Function("algivore", "🌿→", "#e3b341", "Algal grazer", "راعٍ للطحالب",
             "Eats microalgae. Drives classic predator–prey cycles.",
             "يأكل الطحالب الدقيقة، ويسبب دورات المفترس والفريسة الكلاسيكية.",
             "Grazes prey up to a larger size limit that includes algal cells.",
             "يرعى فرائس حتى حد حجم أكبر يشمل خلايا الطحالب.",
             "Chemostat lab, or preset 'Pond food web'.", "مختبر الكيموستات أو السيناريو «شبكة غذائية في بركة»."),
    Function("toppredator", "🔺", "#bc8cff", "Top predator", "مفترس أعلى",
             "Large enough to eat other grazers, not only bacteria and algae.",
             "كبير بما يكفي ليأكل رعاة آخرين، وليس فقط البكتيريا والطحالب.",
             "Its prey size limit is large enough to include protists.",
             "حد حجم فرائسه كبير بما يكفي ليشمل الأوليات.",
             "Add Amoeba to a pond community.", "أضف الأميبا إلى مجتمع البركة."),
    Function("defended", "🛡", "#8b949e", "Grazing-resistant", "مقاوم للرعي",
             "Too large (colonies, filaments) or armoured to be eaten by most grazers.",
             "كبير جداً (مستعمرات، خيوط) أو محصّن فلا تأكله معظم الرعاة.",
             "Marked not edible, so grazers ignore it.",
             "مُعلَّم بأنه غير صالح للأكل فيتجاهله الرعاة.",
             "Compare Chlorella with Scenedesmus next to a rotifer.", "قارن الكلوريلا مع السينيديسمس بجانب دولاب."),
    Function("nfixer", "N₂", "#58d0a0", "Nitrogen fixer", "مثبّت للنيتروجين",
             "Takes nitrogen gas from the air, so it does not depend on dissolved nitrogen; returns it to the system when it dies.",
             "يأخذ غاز النيتروجين من الهواء فلا يعتمد على النيتروجين الذائب، ويعيده للنظام عند موته.",
             "Needs no dissolved nitrogen to grow.", "لا يحتاج نيتروجيناً ذائباً لينمو.",
             "Preset 'The nitrogen cycle'.", "السيناريو «دورة النيتروجين»."),
    Function("nitrifier", "NH₄→", "#7d8590", "Nitrifier", "مؤكسد للأمونيا",
             "Gets energy by oxidising ammonia. Part of the nitrogen cycle; competes with algae for nitrogen.",
             "يستمد طاقته من أكسدة الأمونيا، وهو جزء من دورة النيتروجين وينافس الطحالب عليه.",
             "Consumes ammonium and oxygen; builds biomass from CO₂.",
             "يستهلك الأمونيوم والأكسجين، ويبني كتلته من ثاني أكسيد الكربون.",
             "Preset 'The nitrogen cycle'.", "السيناريو «دورة النيتروجين»."),
    Function("methanogen", "CH₄", "#a371f7", "Methanogen", "منتج للميثان",
             "Turns acetate into methane at the end of anaerobic food chains (biogas). Oxygen kills it.",
             "يحوّل الأسيتات إلى ميثان في نهاية السلاسل اللاهوائية (الغاز الحيوي)، والأكسجين يقتله.",
             "Eats only acetate, and only without oxygen.", "يأكل الأسيتات فقط، وفقط بدون أكسجين.",
             "Preset 'Anaerobic digester'.", "السيناريو «مخمّر لاهوائي»."),
    Function("mixotroph", "☀+🍽", "#56d364", "Mixotroph", "مختلط التغذية",
             "Can photosynthesise and also absorb organic food.", "يستطيع البناء الضوئي وامتصاص الغذاء العضوي معاً.",
             "Photoautotroph that also lists organic substrates.", "ذاتي التغذية ضوئياً ويملك أيضاً ركائز عضوية.",
             "Euglena in the dark with sugar.", "اليوغلينا في الظلام مع سكر."),
    Function("anaerobe", "⊘O₂", "#6e7681", "Oxygen-sensitive", "حساس للأكسجين",
             "Grows only (or best) without oxygen. Needs others to remove oxygen, or a sealed vessel.",
             "ينمو فقط (أو أفضل) بدون أكسجين، ويحتاج من يزيل الأكسجين أو وعاءً مغلقاً.",
             "Its growth is multiplied by an oxygen-inhibition term.", "نموه مضروب بمعامل تثبيط بالأكسجين.",
             "Turn aeration on and off.", "شغّل التهوية وأطفئها."),
    # ---- assigned by hand (not simulated) ----
    Function("food", "🧀", "#f2cc60", "Food starter culture", "بادئ غذائي",
             "Used deliberately to make a food.", "يُستخدم عمداً لصناعة غذاء.", "", "",
             "See its 'Uses' row.", "انظر صف «الاستخدامات»."),
    Function("model", "🔬", "#79c0ff", "Model organism", "كائن نموذجي",
             "A standard lab organism: much of biology was first discovered in it.",
             "كائن مخبري معياري، واكتُشف فيه الكثير من علم الأحياء أولاً.", "", "",
             "See its references.", "انظر مراجعه."),
    Function("extremophile", "🔥", "#ff7b72", "Extremophile", "محب للظروف القاسية",
             "Thrives where most life cannot (very salty, hot, acidic or dry).",
             "يزدهر حيث لا تستطيع معظم الكائنات العيش (ملوحة أو حرارة أو حموضة أو جفاف شديد).", "", "",
             "Salinity and drying are not modelled yet.", "الملوحة والجفاف غير ممثلين بعد."),
]}

MANUAL = {
    "sthermophilus": ("food",), "lbulgaricus": ("food",), "llactis": ("food", "model"),
    "lplantarum": ("food",), "leuconostoc": ("food",), "pfreudenreichii": ("food",), "aaceti": ("food",),
    "scerevisiae": ("food", "model"), "klactis": ("food",), "aoryzae": ("food",), "proqueforti": ("food",),
    "roligosporus": ("food",), "bsubtilis": ("model",), "ecoli": ("model",), "pputida": ("model",),
    "tetrahymena": ("model",), "paramecium": ("model",), "chlorella": ("model",), "synechococcus": ("model",),
    "halobacterium": ("extremophile",), "philodina": ("extremophile",),
}

ORGANIC_PRODUCTS = {"lac", "ace", "eth"}


def derived_functions(o: Organism) -> list[str]:
    """Functions read straight from the simulation traits."""
    out = []
    if o.feeding == "photoautotroph":
        out += ["producer", "oxygen"]
        if any(s in ("sug", "ace", "lac", "eth") for s in o.substrates):
            out.append("mixotroph")
        if not o.edible:
            out.append("defended")
    if o.products.get("lac", 0) >= 0.3:                 # main product, not a by-product
        out.append("lactic")
    if o.products.get("eth", 0) >= 0.2:
        out.append("alcohol")
    # an organism that EATS lactate replaces a strong acid with weaker ones: not an acidifier
    if o.products.get("lac", 0) + o.products.get("ace", 0) >= 0.2 and "lac" not in o.substrates:
        out.append("acidifier")
    if o.hydrolysis >= 0.012:                           # a meaningful enzyme producer
        out.append("decomposer")
    if o.feeding == "heterotroph" and o.oxygen == "anaerobe" and set(o.substrates) == {"ace"}:
        out.append("methanogen")
    elif o.feeding == "heterotroph" and set(o.substrates) & ORGANIC_PRODUCTS:
        if o.oxygen == "aerobe" and len(set(o.substrates) & ORGANIC_PRODUCTS) >= 2:
            out.append("scavenger")
        else:
            out.append("crossfeeder")
    if o.feeding == "predator":
        out.append("bacterivore")                       # every grazer here can take bacteria
        if o.prey_size_max >= 10:
            out.append("algivore")                      # large enough for algal cells too
        if o.prey_size_max >= 50:
            out.append("toppredator")
    if o.feeding == "heterotroph" and o.n_quota == 0:
        out.append("nfixer")
    if o.feeding == "chemolithotroph":
        out.append("nitrifier")
    if o.oxygen == "anaerobe" and "methanogen" not in out:
        out.append("anaerobe")
    if o.feeding != "photoautotroph" and not o.edible and o.feeding != "predator":
        out.append("defended")
    return out


def functions_of(key: str) -> list[Function]:
    o = ORGANISMS[key]
    keys = derived_functions(o) + [k for k in MANUAL.get(key, ()) if k not in derived_functions(o)]
    return [FUNCTIONS[k] for k in keys]


def organisms_with(function_key: str) -> list[Organism]:
    return [o for o in ORGANISMS.values() if function_key in [f.key for f in functions_of(o.key)]]


def is_derived(key: str, function_key: str) -> bool:
    return function_key in derived_functions(ORGANISMS[key])


def relations(keys: tuple[str, ...]) -> list[tuple[str, str, str, str, str]]:
    """Who-does-what-to-whom among a chosen set, read from traits only.

    Returns (from_key, to_key, kind, english, arabic). This is what the traits SUGGEST;
    the interaction analysis then measures whether it actually matters.
    """
    from .organisms import RESOURCES
    orgs = [ORGANISMS[k] for k in keys]
    out = []
    for a in orgs:
        for b in orgs:
            if a is b:
                continue
            if a.feeding == "predator" and b.edible and b.size_um <= a.prey_size_max:
                out.append((a.key, b.key, "eats", f"{a.name} eats {b.name}", f"{a.name_ar} يأكل {b.name_ar}"))
            fed = set(a.products) & set(b.substrates)
            if fed:
                n_en = ", ".join(RESOURCES[k][0].lower() for k in sorted(fed))
                n_ar = "، ".join(RESOURCES[k][1] for k in sorted(fed))
                out.append((a.key, b.key, "feeds", f"{a.name} makes {n_en}, which {b.name} eats",
                            f"{a.name_ar} ينتج {n_ar} ويأكلها {b.name_ar}"))
            if a.hydrolysis > 0 and "poly" not in b.substrates and "sug" in b.substrates:
                out.append((a.key, b.key, "opens", f"{a.name} breaks polymers into sugars that {b.name} can use",
                            f"{a.name_ar} يكسر البوليمرات إلى سكريات يستفيد منها {b.name_ar}"))
            if a.feeding == "photoautotroph" and b.oxygen in ("aerobe", "facultative", "microaerophile") and b is not a:
                out.append((a.key, b.key, "oxygen", f"{a.name} supplies oxygen that {b.name} can breathe",
                            f"{a.name_ar} يوفّر أكسجيناً يتنفسه {b.name_ar}"))
            if (a.products.get("lac", 0) + a.products.get("ace", 0) >= 0.2) and b.cardinal_pH[0] > 4.0:
                out.append((a.key, b.key, "acid", f"{a.name}'s acid can push the pH below {b.name}'s limit "
                            f"({b.cardinal_pH[0]:g})", f"حمض {a.name_ar} قد يخفض الحموضة تحت حد {b.name_ar} "
                            f"({b.cardinal_pH[0]:g})"))
    for i, a in enumerate(orgs):
        for b in orgs[i + 1:]:
            shared = (set(a.substrates) & set(b.substrates)) - {"nh4"} if a.feeding != "photoautotroph" else \
                set(a.substrates) & set(b.substrates)
            if shared:
                n_en = ", ".join(RESOURCES[k][0].lower() for k in sorted(shared))
                n_ar = "، ".join(RESOURCES[k][1] for k in sorted(shared))
                out.append((a.key, b.key, "compete", f"{a.name} and {b.name} compete for {n_en}",
                            f"{a.name_ar} و{b.name_ar} يتنافسان على {n_ar}"))
    return out
