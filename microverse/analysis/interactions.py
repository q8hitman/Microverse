"""Measure how the selected organisms actually affect each other.

Method (a numerical experiment, not a look-up table): run the same environment with
each organism alone and with each PAIR together. The effect of B on A is the log-ratio
of A's final biomass in the pair versus alone. The signs of the two effects give the
ecological interaction type, and the organisms' traits give the mechanism.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..core.scheduler import make_config, run
from ..library.organisms import ORGANISMS, Organism
from ..models.community import NP, Community

THRESHOLD = 0.15          # |log10 ratio| below this counts as "no measurable effect" (≈40%)

TYPES = {
    ("+", "+"): ("Mutualism", "تبادل منفعة", "#3fb950"),
    ("+", "0"): ("Commensalism", "تعايش أحادي النفع", "#58a6ff"),
    ("0", "+"): ("Commensalism", "تعايش أحادي النفع", "#58a6ff"),
    ("+", "-"): ("One gains, one loses", "واحد يستفيد والثاني يتضرر", "#f0883e"),
    ("-", "+"): ("One gains, one loses", "واحد يستفيد والثاني يتضرر", "#f0883e"),
    ("-", "-"): ("Competition", "تنافس", "#f85149"),
    ("-", "0"): ("Amensalism (one-sided harm)", "إضرار من طرف واحد", "#a371f7"),
    ("0", "-"): ("Amensalism (one-sided harm)", "إضرار من طرف واحد", "#a371f7"),
    ("0", "0"): ("No measurable interaction", "لا يوجد تأثير ملموس", "#8b949e"),
}
RES_AR = {"poly": "بوليمرات", "sug": "سكريات", "lac": "لاكتات", "ace": "أسيتات", "eth": "إيثانول", "nh4": "نيتروجين"}


@dataclass
class Interaction:
    a: str
    b: str
    effect_of_b_on_a: float     # log10(biomass of A with B / biomass of A alone)
    effect_of_a_on_b: float
    kind: str
    kind_ar: str
    colour: str
    why_a: list[tuple[str, str]]      # why A was affected, (English, Arabic)
    why_b: list[tuple[str, str]]


def _sign(x: float) -> str:
    return "+" if x > THRESHOLD else ("-" if x < -THRESHOLD else "0")


def _is_predation(A: Organism, B: Organism) -> bool:
    return A.feeding == "predator" and B.edible and B.size_um <= A.prey_size_max


def _res(keys, ar=False) -> str:
    return ", ".join(RES_AR[k] if ar else k for k in sorted(keys))


def why(A: Organism, B: Organism, effect: float) -> list[tuple[str, str]]:
    """Mechanistic reasons, read from traits, for how B affected A."""
    out: list[tuple[str, str]] = []
    if effect < -THRESHOLD:
        if _is_predation(B, A):
            out.append((f"{B.name} ingests {A.name} ({A.size_um:g} µm is within its {B.prey_size_max:g} µm prey limit).",
                        f"{B.name_ar} يبتلع {A.name_ar} (حجمه {A.size_um:g} ميكرومتر ضمن حد الافتراس {B.prey_size_max:g})."))
        shared = set(A.substrates) & set(B.substrates)
        if shared:
            out.append((f"Both compete for the same resources ({_res(shared)}).",
                        f"كلاهما يتنافس على نفس الموارد ({_res(shared, True)})."))
        if any(k in ("lac", "ace") for k in B.products):
            out.append((f"{B.name} produces acid, pushing the pH toward {A.name}'s lower limit of pH {A.cardinal_pH[0]:g}.",
                        f"{B.name_ar} ينتج حمضاً يدفع الحموضة نحو الحد الأدنى لـ {A.name_ar} وهو {A.cardinal_pH[0]:g}."))
        if A.oxygen == "anaerobe" and B.feeding == "photoautotroph":
            out.append((f"{B.name} releases oxygen, which inhibits the anaerobe {A.name}.",
                        f"{B.name_ar} يطلق أكسجيناً يثبّط {A.name_ar} اللاهوائي."))
        if A.oxygen in ("aerobe", "microaerophile") and B.oxygen in ("aerobe", "facultative"):
            out.append((f"Both draw on the same dissolved oxygen.", "كلاهما يسحب من نفس الأكسجين الذائب."))
    elif effect > THRESHOLD:
        if _is_predation(A, B):
            out.append((f"{A.name} eats {B.name}, so its presence is food ({B.size_um:g} µm ≤ {A.prey_size_max:g} µm).",
                        f"{A.name_ar} يأكل {B.name_ar}، فوجوده غذاء له ({B.size_um:g} ≤ {A.prey_size_max:g} ميكرومتر)."))
        fed = set(B.products) & set(A.substrates)
        if fed:
            out.append((f"Cross-feeding: {B.name} releases {_res(fed)}, which {A.name} can consume.",
                        f"تغذية تبادلية: {B.name_ar} يطلق ({_res(fed, True)}) و{A.name_ar} يستطيع استهلاكها."))
        if B.hydrolysis > 0 and "poly" not in A.substrates:
            out.append((f"{B.name} secretes enzymes that break polymers into sugars {A.name} can use.",
                        f"{B.name_ar} يفرز إنزيمات تكسر البوليمرات إلى سكريات يستفيد منها {A.name_ar}."))
        if B.feeding == "photoautotroph" and A.oxygen in ("aerobe", "facultative", "microaerophile"):
            out.append((f"{B.name} releases oxygen by photosynthesis, which {A.name} needs to respire.",
                        f"{B.name_ar} يطلق أكسجيناً بالبناء الضوئي يحتاجه {A.name_ar} للتنفس."))
        if A.oxygen == "anaerobe" and B.oxygen in ("aerobe", "facultative"):
            out.append((f"{B.name} consumes oxygen, protecting the oxygen-sensitive {A.name}.",
                        f"{B.name_ar} يستهلك الأكسجين فيحمي {A.name_ar} الحساس للأكسجين."))
        if B.n_quota == 0 and A.n_quota > 0:
            out.append((f"{B.name} fixes its own nitrogen and releases some when it dies, leaving more for {A.name}.",
                        f"{B.name_ar} يثبّت نيتروجينه ويطلق بعضه عند موته، فيبقى أكثر لـ {A.name_ar}."))
    if not out:
        out.append(("Indirect effect through the shared pools of resources, oxygen or pH.",
                    "تأثير غير مباشر عبر الموارد المشتركة أو الأكسجين أو الحموضة."))
    return out


def _final(model: Community, cfg, keys_subset: tuple[str, ...]) -> dict[str, float]:
    sub = Community(keys_subset)
    p = dict(cfg.parameters)
    c = make_config(sub, t_end=cfg.t_end, dt_out=max(cfg.t_end / 400, 0.05),
                    initial_state=sub.initial_state_from(p), **p)
    tr = run(sub, c)
    tail = max(len(tr.t) // 10, 1)
    return {k: float(np.mean(tr.y[-tail:, NP + i])) for i, k in enumerate(keys_subset)}


def analyse(model: Community, cfg, progress=None):
    """Returns (interactions, biomass in the full community, biomass alone, biomass in pairs)."""
    keys = model.keys
    n = len(keys)
    pairs = [(keys[i], keys[j]) for i in range(n) for j in range(i + 1, n)]
    steps = 1 + n + len(pairs)
    done = 0

    def tick():
        nonlocal done
        done += 1
        if progress:
            progress(done, steps)

    together = _final(model, cfg, keys)
    tick()
    alone: dict[str, float] = {}
    for k in keys:
        alone.update(_final(model, cfg, (k,)))
        tick()
    duos = {}
    for a, b in pairs:
        duos[(a, b)] = _final(model, cfg, (a, b))
        tick()

    out = []
    for a, b in pairs:
        duo = duos[(a, b)]
        ea = float(np.log10((duo[a] + 1e-6) / (alone[a] + 1e-6)))
        eb = float(np.log10((duo[b] + 1e-6) / (alone[b] + 1e-6)))
        kind, kind_ar, colour = TYPES[(_sign(ea), _sign(eb))]
        A, B = ORGANISMS[a], ORGANISMS[b]
        if {_sign(ea), _sign(eb)} == {"+", "-"} and (_is_predation(A, B) or _is_predation(B, A)):
            kind, kind_ar = "Predation (grazing)", "افتراس (رعي)"
        no_effect = [("No measurable change (less than 40%).", "لا تغيّر ملموس (أقل من 40%).")]
        out.append(Interaction(a, b, ea, eb, kind, kind_ar, colour,
                               why(A, B, ea) if _sign(ea) != "0" else no_effect,
                               why(B, A, eb) if _sign(eb) != "0" else no_effect))
    return out, together, alone, duos
