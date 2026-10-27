"""Generic trait-based microbial community model.

The user picks any organisms from the database; this model builds the equations
from their traits, so interactions EMERGE from the mechanisms instead of being
written in by hand:

* competition      — two organisms draw on the same resource pool
* predation        — a grazer ingests prey small enough to swallow
* cross-feeding    — one organism's product (lactate, acetate, ethanol) is another's food
* chemical warfare — acids lower the pH and shut down the acid-sensitive species
* oxygen coupling  — photosynthesis makes O₂; aerobes consume it; anaerobes are inhibited by it
* nutrient cycling — death → detritus → polymers → sugars → back into the food web

State (mg/L): the eight resource pools of RESOURCES, then one biomass per organism.
Time unit: hours. Status: EXPLORATORY — traits are literature estimates or assumptions.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import brentq

from ..core.model import FluxTerm, Model, StateVar
from ..core.parameters import Evidence, Parameter, ParameterSet, Source
from ..library.organisms import ORGANISMS, Organism

ORGANIC = ("poly", "sug", "lac", "ace", "eth")
POOLS = ("poly", "sug", "lac", "ace", "eth", "nh4", "o2", "det")
NP = len(POOLS)
PI = {p: i for i, p in enumerate(POOLS)}

TRAITS = Source(key="microverse_trait_db",
                citation="MicroVerse organism trait database (microverse/library/organisms.py): typical "
                         "textbook values and documented assumptions, not calibrated to a dataset.",
                note="Every organism card lists its own references.")
GENERIC = Source(key="generic_microbial_ecology",
                 citation="Standard microbial-ecology formulations: Monod kinetics, Holling type II grazing, "
                          "cardinal temperature/pH models (Rosso et al. 1993, 1995), two-film gas transfer.")

O2_SAT = 8.0            # mg/L at ~25 °C, air-saturated fresh water
K_O2 = 0.3              # mg/L half-saturation for aerobic respiration
KI_O2 = 0.3              # mg/L inhibition constant for anaerobes
K_N = 0.05               # mg N/L half-saturation for nitrogen limitation of growth
O2_PER_BIOMASS = 1.4    # mg O2 released per mg photoautotroph biomass formed
O2_PER_SUBSTRATE = 1.0  # mg O2 consumed per mg substrate respired aerobically
PKA = {"lac": 3.86, "ace": 4.76}
MW = {"lac": 90.08, "ace": 60.05}


def ctmi(T, tmin, topt, tmax):
    if T <= tmin or T >= tmax:
        return 0.0
    num = (T - tmax) * (T - tmin) ** 2
    den = (topt - tmin) * ((topt - tmin) * (T - topt) - (topt - tmax) * (topt + tmin - 2 * T))
    return float(np.clip(num / den, 0.0, 1.0))


def cpm(ph, phmin, phopt, phmax):
    if ph <= phmin or ph >= phmax:
        return 0.0
    num = (ph - phmin) * (ph - phmax)
    den = num - (ph - phopt) ** 2
    return float(np.clip(num / den, 0.0, 1.0)) if den != 0 else 0.0


def water_ph(lac_mg_l: float, ace_mg_l: float, buffer_mm: float, ph_base: float) -> float:
    """pH from a charge balance: acids produced vs. a single lumped buffer of the medium."""
    acids = {"lac": max(lac_mg_l, 0.0) / MW["lac"], "ace": max(ace_mg_l, 0.0) / MW["ace"]}   # mmol/L
    pkb = 6.4
    z = buffer_mm / (1 + 10 ** (pkb - ph_base)) - 10 ** (-ph_base) * 1e3

    def f(p):
        h = 10 ** (-p) * 1e3
        return z + h - buffer_mm / (1 + 10 ** (pkb - p)) - sum(a / (1 + 10 ** (PKA[k] - p)) for k, a in acids.items())
    return float(brentq(f, 1.5, 11.0, xtol=1e-6))


class Community(Model):
    id = "community"
    version = "1.0.0"
    title = "Microbial community: any organisms, one environment"
    time_unit = "h"

    def __init__(self, organism_keys: tuple[str, ...]):
        self.keys = tuple(organism_keys)
        self.orgs: tuple[Organism, ...] = tuple(ORGANISMS[k] for k in self.keys)
        self.state_vars = tuple(
            [StateVar(p, *_pool_labels(p)) for p in POOLS]
            + [StateVar(f"X_{o.key}", o.name, "mg/L", o.role) for o in self.orgs])
        self.id = "community:" + ",".join(self.keys)

    # ----------------------------------------------------------- parameters
    def default_parameters(self) -> ParameterSet:
        C, A = Evidence.CONTROL, Evidence.ASSUMED
        ps = [
            Parameter("T", "Temperature", 25.0, "°C", 0.0, 60.0, C, None, "Temperature of the whole vessel."),
            Parameter("light", "Light", 1.0, "× full daylight", 0.0, 2.0, C, None,
                      "Light available for photosynthesis; 0 = dark (a closed box or night)."),
            Parameter("aeration", "Aeration (gas exchange)", 2.0, "1/h", 0.0, 20.0, C, None,
                      "How fast oxygen enters from the air: 0 = sealed anaerobic jar, 2 = open vessel, 10 = shaken flask."),
            Parameter("poly0", "Polymers added", 500.0, "mg/L", 0.0, 5000.0, C, None,
                      "Starch/protein/plant material: only organisms with enzymes can use it."),
            Parameter("sug0", "Sugars added", 2000.0, "mg/L", 0.0, 5000.0, C, None,
                      "Ready-to-eat sugar available to everyone from the start."),
            Parameter("nh40", "Nitrogen added", 60.0, "mg N/L", 0.1, 500.0, C, None,
                      "Dissolved inorganic nitrogen (ammonium/nitrate)."),
            Parameter("inoculum", "Inoculum of each organism", 1.0, "mg/L", 0.001, 100.0, C, None,
                      "Starting biomass given to every selected organism."),
            Parameter("buffer", "Medium buffering", 5.0, "mmol/L", 0.0, 200.0, C, None,
                      "Resistance of the medium to pH change: 2 = pond water, 10 = buffered broth, 120 = milk."),
            Parameter("ph_base", "Starting pH", 7.0, "–", 3.0, 9.5, C, None, "pH before any acid is produced."),
            Parameter("dilution", "Dilution (flow-through)", 0.0, "1/h", 0.0, 1.0, C, None,
                      "0 = closed batch culture; >0 = fresh medium flows in and culture flows out (chemostat)."),
            Parameter("refuge", "Prey refuge", 0.5, "mg/L", 0.0, 20.0, A, GENERIC,
                      "Biomass of each prey that grazers cannot reach (cells stuck to walls, in aggregates or in "
                      "biofilm). It prevents absolute extinction and allows populations to recover."),
            Parameter("det_rate", "Detritus breakdown", 0.02, "1/h", 0.0, 0.5, A, GENERIC,
                      "How fast dead biomass turns back into polymers."),
            Parameter("mu_scale", "Growth-rate scaling", 1.0, "×", 0.2, 3.0, A, TRAITS,
                      "Multiplies every organism's maximum growth rate (use it to test how sensitive the outcome is)."),
        ]
        return ParameterSet({p.symbol: p for p in ps})

    def default_initial_state(self) -> np.ndarray:
        return self.initial_state_from(self.default_parameters().values())

    def initial_state_from(self, p) -> np.ndarray:
        y = np.zeros(NP + len(self.orgs))
        y[PI["poly"]] = p["poly0"]
        y[PI["sug"]] = p["sug0"]
        y[PI["nh4"]] = p["nh40"]
        # An open vessel starts air-saturated. A sealed vessel is purged (as an anaerobic jar is in the
        # lab), so it starts at zero and only gains oxygen if a photosynthetic organism makes it.
        y[PI["o2"]] = O2_SAT if p["aeration"] > 0 else 0.0
        y[NP:] = p["inoculum"]
        return y

    # --------------------------------------------------------------- rates
    def factors(self, y, p) -> dict:
        ph = water_ph(y[PI["lac"]], y[PI["ace"]], p["buffer"], p["ph_base"])
        o2 = max(y[PI["o2"]], 0.0)
        out = {"pH": ph, "o2": o2, "per_org": []}
        for i, o in enumerate(self.orgs):
            fT = ctmi(p["T"], *o.cardinal_T)
            fpH = cpm(ph, *o.cardinal_pH)
            if o.feeding == "photoautotroph":
                fO = 1.0                       # it makes its own oxygen
            elif o.oxygen == "aerobe":
                fO = o2 / (K_O2 + o2)
            elif o.oxygen == "anaerobe":
                fO = KI_O2 / (KI_O2 + o2)
            elif o.oxygen == "microaerophile":
                fO = (o2 / (K_O2 + o2)) * (1.0 / (1.0 + o2 / 4.0))
            else:                                   # facultative
                fO = max(o2 / (K_O2 + o2), 0.55 * KI_O2 / (KI_O2 + o2))
            base = o.mu_max * p["mu_scale"] * fT * fpH * fO
            out["per_org"].append({"fT": fT, "fpH": fpH, "fO2": fO, "base": base})
        return out

    def _rates(self, y, p):
        """Returns (dy, details) — details feed the explanation engine."""
        f = self.factors(y, p)
        n = len(self.orgs)
        dy = np.zeros_like(y)
        pools = {k: max(y[PI[k]], 0.0) for k in POOLS}
        X = np.maximum(y[NP:], 0.0)
        det = []

        # total edible prey biomass available to each predator
        for i, o in enumerate(self.orgs):
            fo = f["per_org"][i]
            d = {"org": o, "mu": 0.0, "uptake": {}, "prey": {}, "growth": 0.0, "limiting": "", "n_limited": False}
            bio = X[i]
            if bio <= 0 or fo["base"] <= 0:
                # Cannot grow — but it still dies and still washes out. (Conditions beyond the
                # cardinal limits stop growth; survival is modelled as the ordinary death rate.)
                d["limiting"] = "temperature" if fo["fT"] <= 1e-6 else ("pH" if fo["fpH"] <= 1e-6 else
                                                                        ("oxygen" if fo["fO2"] <= 1e-6 else "absent"))
                dying = o.death * bio
                dy[NP + i] -= dying + p["dilution"] * bio
                dy[PI["det"]] += dying
                d["death"] = dying
                det.append(d)
                continue

            # Nitrogen limitation, applied smoothly so resource uptake and growth stay consistent.
            # Photoautotrophs and ammonia oxidisers have nitrogen in their own Monod term already.
            nfac = 1.0
            if o.n_quota > 0 and o.feeding not in ("photoautotroph", "chemolithotroph"):
                nfac = pools["nh4"] / (K_N + pools["nh4"])

            if o.feeding == "predator":
                # smooth refuge: accessible ≈ X − refuge for large X, → 0 smoothly as X → 0
                edible = {j: X[j] * X[j] / (X[j] + p["refuge"]) for j, q in enumerate(self.orgs)
                          if j != i and q.edible and q.size_um <= o.prey_size_max}
                total = sum(edible.values())
                ing = o.ingest_max * p["mu_scale"] * fo["fT"] * fo["fpH"] * fo["fO2"] * total / (o.ks_prey + total) * bio
                for j, xj in edible.items():
                    share = ing * (xj / total if total > 0 else 0.0)
                    dy[NP + j] -= share
                    d["prey"][self.orgs[j].key] = share
                growth = o.yield_bio * ing * nfac
                dy[PI["det"]] += ing - growth                    # unassimilated prey becomes detritus
                dy[PI["o2"]] -= O2_PER_SUBSTRATE * (ing - growth)
                d["mu"] = growth / bio
                d["limiting"] = "prey" if total < o.ks_prey else (
                    "nitrogen" if nfac < 0.5 else _weakest(fo))
            elif o.feeding == "photoautotroph":
                nlim = pools["nh4"] / (o.ks + pools["nh4"])
                mu = fo["base"] * p["light"] * nlim
                growth = mu * bio
                dy[PI["o2"]] += O2_PER_BIOMASS * growth
                d["mu"] = mu
                d["limiting"] = "light" if p["light"] < 0.5 else ("nitrogen" if nlim < 0.5 else _weakest(fo))
            elif o.feeding == "chemolithotroph":
                s = pools["nh4"]
                mu = fo["base"] * s / (o.ks + s)
                growth = mu * bio
                dy[PI["nh4"]] -= growth / max(o.yield_bio, 1e-9)
                dy[PI["o2"]] -= 1.5 * growth / max(o.yield_bio, 1e-9)
                d["mu"] = mu
                d["limiting"] = "ammonia" if s < o.ks else _weakest(fo)
                d["uptake"]["nh4"] = growth / max(o.yield_bio, 1e-9)
            else:                                                 # heterotroph
                avail = {s: pools[s] for s in o.substrates if s in ORGANIC}
                total = sum(avail.values())
                mu = fo["base"] * total / (o.ks + total) * nfac
                growth = mu * bio
                consumed = growth / max(o.yield_bio, 1e-9)
                for s, v in avail.items():
                    take = consumed * (v / total if total > 0 else 0.0)
                    dy[PI[s]] -= take
                    d["uptake"][s] = take
                    for prod, yld in o.products.items():
                        if prod != s:
                            dy[PI[prod]] += yld * take
                respired = consumed * (1 - sum(o.products.values())) if o.products else consumed
                if o.oxygen in ("aerobe", "facultative", "microaerophile"):
                    dy[PI["o2"]] -= O2_PER_SUBSTRATE * max(respired - growth, 0.0) * fo["fO2"]
                d["mu"] = mu
                d["limiting"] = ("food" if total < o.ks else ("nitrogen" if nfac < 0.5 else _weakest(fo)))
            # enzymes released into the medium break polymers down for everyone
            if o.hydrolysis > 0 and pools["poly"] > 0:
                h = min(o.hydrolysis * bio * fo["fT"], pools["poly"] * 2.0)
                dy[PI["poly"]] -= h
                dy[PI["sug"]] += h
                d["hydrolysis"] = h
            growth = d["mu"] * bio
            if o.n_quota > 0 and o.feeding != "chemolithotroph":
                dy[PI["nh4"]] -= o.n_quota * growth
                d["n_limited"] = nfac < 0.5
            dying = o.death * bio
            dy[NP + i] += growth - dying - p["dilution"] * bio
            dy[PI["det"]] += dying
            d["growth"], d["death"] = growth, dying
            det.append(d)

        # recycling, gas exchange and flow-through
        dmin = p["det_rate"] * pools["det"]
        dy[PI["det"]] -= dmin
        dy[PI["poly"]] += dmin * 0.8
        dy[PI["nh4"]] += dmin * 0.08                              # mineralised nitrogen
        # gas exchange; oxygen above saturation always bubbles out, even in a sealed vessel
        exch = p["aeration"] if pools["o2"] <= O2_SAT else max(p["aeration"], 1.0)
        dy[PI["o2"]] += exch * (O2_SAT - pools["o2"])
        if p["dilution"] > 0:
            for k, fresh in (("poly", p["poly0"]), ("sug", p["sug0"]), ("nh4", p["nh40"])):
                dy[PI[k]] += p["dilution"] * (fresh - pools[k])
            for k in ("lac", "ace", "eth", "det"):
                dy[PI[k]] -= p["dilution"] * pools[k]
        return dy, f, det

    def rhs(self, t, y, p):
        return self._rates(y, p)[0]

    def flux_terms(self, y, p):
        dy, f, det = self._rates(y, p)
        out = []
        for i, d in enumerate(det):
            o = d["org"]
            sym = f"X_{o.key}"
            if d.get("growth"):
                out.append(FluxTerm(sym, "growth", d["growth"], "µ·X"))
            if d.get("death"):
                out.append(FluxTerm(sym, "death", -d["death"], "−m·X"))
            if p["dilution"] > 0:
                out.append(FluxTerm(sym, "washout", -p["dilution"] * max(y[NP + i], 0), "−D·X"))
        for j, d in enumerate(det):
            for prey_key, amount in d.get("prey", {}).items():
                out.append(FluxTerm(f"X_{prey_key}", f"eaten by {d['org'].name}", -amount, "−I·X_pred"))
        return out

    def details(self, y, p):
        return self._rates(y, p)[2]

    def ph_series(self, traj) -> np.ndarray:
        pr = traj.config.parameters
        return np.array([water_ph(a, b, pr["buffer"], pr["ph_base"])
                         for a, b in zip(traj.series("lac"), traj.series("ace"))])


def _weakest(fo) -> str:
    name, value = min((("temperature", fo["fT"]), ("pH", fo["fpH"]), ("oxygen", fo["fO2"])), key=lambda x: x[1])
    return name if value < 0.9 else "nothing"


def _pool_labels(p: str) -> tuple[str, str, str]:
    from ..library.organisms import RESOURCES
    name = RESOURCES[p][0]
    unit = "mg N/L" if p == "nh4" else "mg/L"
    return name, unit, name
