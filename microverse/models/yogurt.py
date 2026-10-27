"""Yoghurt fermentation: Streptococcus thermophilus + Lactobacillus delbrueckii subsp. bulgaricus in milk.

Mechanisms (each one switchable through its parameters):
* growth = μ_opt × temperature factor (CTMI, Rosso 1993) × pH factor (CPM, Rosso 1995)
           × lactose saturation × protocooperation factor
* protocooperation: L. bulgaricus proteolysis releases peptides that S. thermophilus needs;
  S. thermophilus produces formate that stimulates L. bulgaricus
* acid production: Luedeking–Piret (growth-associated α + non-growth-associated β)
* homolactic fermentation of the glucose half of lactose; galactose is excreted
* pH from a charge balance of lactic acid against a three-buffer model of milk

See docs/models/yogurt.md. Status: EXPLORATORY — parameters are illustrative estimates
chosen to reproduce typical textbook behaviour, not fitted to a dataset.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import brentq

from ..core.model import FluxTerm, Model, StateVar
from ..core.parameters import Evidence, Parameter, ParameterSet, Source

TEXTBOOK = Source(
    key="yogurt_textbook_estimates",
    citation="Order-of-magnitude values from dairy microbiology textbooks and reviews "
             "(e.g. Tamime & Robinson, Yoghurt: Science and Technology, 3rd ed., 2007; "
             "Sieuwerts et al. 2008, Appl Environ Microbiol 74:4997). Not fitted to a dataset.",
    note="Illustrative; requires calibration against measured fermentation curves.",
)
ROSSO = Source(
    key="rosso_cardinal_models",
    citation="Rosso L et al. (1993) J Theor Biol 162:447 (CTMI); Rosso L et al. (1995) "
             "Appl Environ Microbiol 61:610 (cardinal pH model).",
    doi="10.1006/jtbi.1993.1099",
)
BUFFER_FIT = Source(
    key="milk_buffer_fit",
    citation="Three-buffer charge-balance model fitted by MicroVerse to approximate typical milk "
             "acidification points (pH 6.65 → 4.6 at ≈7 g/L lactic acid).",
    note="Fitted to approximate textbook values, not to a measured titration curve.",
)

MW_LACTIC, MW_LACTOSE, MW_GAL = 90.08, 342.30, 180.16
LACTOSE_PER_LACTATE = MW_LACTOSE / (2 * MW_LACTIC)        # g lactose per g lactate (glucose half used)
GAL_PER_LACTATE = MW_GAL / (2 * MW_LACTIC)                # g galactose excreted per g lactate
PKA_LACTIC = 3.86
BUFFERS = ((6.8, 71.3), (5.1, 22.4), (4.4, 66.7))         # (pKa, total mM): phosphate/CCP, citrate, casein carboxyls
PH0 = 6.65

XS, XL, LAC, GAL, ACID, PEP, FORM = range(7)


def ctmi(T, tmin, topt, tmax):
    if T <= tmin or T >= tmax:
        return 0.0
    num = (T - tmax) * (T - tmin) ** 2
    den = (topt - tmin) * ((topt - tmin) * (T - topt) - (topt - tmax) * (topt + tmin - 2 * T))
    return max(num / den, 0.0)


def cpm(ph, phmin, phopt, phmax=8.0):
    if ph <= phmin or ph >= phmax:
        return 0.0
    num = (ph - phmin) * (ph - phmax)
    return max(num / (num - (ph - phopt) ** 2), 0.0)


def _z_cations(scale):
    return sum(scale * t / (1 + 10 ** (k - PH0)) for k, t in BUFFERS) - 10 ** (-PH0) * 1e3


def milk_ph(lactic_g_l: float, buffer_scale: float = 1.0) -> float:
    """pH from the charge balance of lactate + milk buffers (buffer_scale ~ milk solids)."""
    lac = max(lactic_g_l, 0.0) / MW_LACTIC * 1e3
    z = _z_cations(buffer_scale)

    def f(p):
        h = 10 ** (-p) * 1e3
        return (z + h - sum(buffer_scale * t / (1 + 10 ** (k - p)) for k, t in BUFFERS)
                - lac / (1 + 10 ** (PKA_LACTIC - p)))
    return brentq(f, 2.0, 9.0, xtol=1e-6)


class Yogurt(Model):
    id = "yogurt"
    version = "1.0.0"
    title = "Yoghurt fermentation: S. thermophilus + L. bulgaricus in milk"
    time_unit = "h"
    state_vars = (
        StateVar("XS", "S. thermophilus", "10⁸ CFU/mL", "Viable Streptococcus thermophilus"),
        StateVar("XL", "L. bulgaricus", "10⁸ CFU/mL", "Viable Lactobacillus delbrueckii subsp. bulgaricus"),
        StateVar("Lac", "Lactose", "g/L", "Milk sugar (substrate)"),
        StateVar("Gal", "Galactose", "g/L", "Excreted galactose moiety"),
        StateVar("A", "Lactic acid", "g/L", "Produced lactic acid"),
        StateVar("P", "Peptides/amino acids", "mg/L", "Released by L. bulgaricus proteolysis"),
        StateVar("F", "Formate", "mg/L", "Produced by S. thermophilus"),
    )

    def default_parameters(self) -> ParameterSet:
        A, L, C = Evidence.ASSUMED, Evidence.LITERATURE_ESTIMATE, Evidence.CONTROL
        T, R, B = TEXTBOOK, ROSSO, BUFFER_FIT
        ps = [
            # process conditions
            Parameter("T", "Incubation temperature", 43.0, "°C", 20.0, 55.0, C, None,
                      "Temperature of the fermenting milk."),
            Parameter("XS0", "S. thermophilus inoculum", 0.1, "10⁸ CFU/mL", 0.0, 10.0, C, None,
                      "Initial count after inoculation (≈2% starter)."),
            Parameter("XL0", "L. bulgaricus inoculum", 0.1, "10⁸ CFU/mL", 0.0, 10.0, C, None,
                      "Initial count after inoculation."),
            Parameter("Lac0", "Initial lactose", 47.0, "g/L", 1.0, 120.0, L, T,
                      "Lactose in cow's milk is typically 45–50 g/L."),
            Parameter("buf", "Milk buffer strength", 1.0, "× whole milk", 0.5, 2.0, A, B,
                      "Scales the buffer model; >1 mimics milk fortified with milk solids."),
            # S. thermophilus
            Parameter("muS", "S. thermophilus μ_opt", 1.6, "1/h", 0.1, 4.0, L, T,
                      "Maximum specific growth rate in milk at optimal T and pH."),
            Parameter("TminS", "S. thermophilus T_min", 15.0, "°C", 0.0, 30.0, A, R, "Cardinal minimum temperature."),
            Parameter("ToptS", "S. thermophilus T_opt", 42.0, "°C", 30.0, 50.0, L, T, "Optimal growth temperature."),
            Parameter("TmaxS", "S. thermophilus T_max", 50.0, "°C", 44.0, 60.0, A, R, "Cardinal maximum temperature."),
            Parameter("pHminS", "S. thermophilus pH_min", 4.3, "–", 3.5, 5.5, A, R,
                      "Growth stops below this pH (S. thermophilus is the more acid-sensitive partner)."),
            Parameter("aS", "S. thermophilus growth without peptides", 0.45, "fraction", 0.0, 1.0, A, T,
                      "Relative growth rate once free amino acids are exhausted and no peptides are supplied."),
            # L. bulgaricus
            Parameter("muL", "L. bulgaricus μ_opt", 1.0, "1/h", 0.1, 4.0, L, T,
                      "Maximum specific growth rate in milk at optimal T and pH."),
            Parameter("TminL", "L. bulgaricus T_min", 20.0, "°C", 0.0, 35.0, A, R, "Cardinal minimum temperature."),
            Parameter("ToptL", "L. bulgaricus T_opt", 45.0, "°C", 35.0, 52.0, L, T, "Optimal growth temperature."),
            Parameter("TmaxL", "L. bulgaricus T_max", 53.0, "°C", 46.0, 60.0, A, R, "Cardinal maximum temperature."),
            Parameter("pHminL", "L. bulgaricus pH_min", 4.0, "–", 3.2, 5.0, A, R,
                      "L. bulgaricus tolerates lower pH and drives post-acidification."),
            Parameter("aL", "L. bulgaricus growth without formate", 0.35, "fraction", 0.0, 1.0, A, T,
                      "Relative growth rate when S. thermophilus supplies no formate."),
            # interactions and products
            Parameter("kP", "Peptide release by L. bulgaricus", 40.0, "mg/L/h per 10⁸ CFU/mL", 0.0, 200.0, A, T,
                      "Proteolysis of casein by the cell-wall protease PrtB."),
            Parameter("KP", "Peptide half-saturation", 20.0, "mg/L", 0.1, 200.0, A, T, ""),
            Parameter("P0", "Free amino acids/peptides in milk", 10.0, "mg/L", 0.0, 200.0, A, T, ""),
            Parameter("yP", "Peptide use by S. thermophilus", 15.0, "mg/L per 10⁸ CFU/mL", 0.0, 100.0, A, T, ""),
            Parameter("yF", "Formate production by S. thermophilus", 6.0, "mg/L per 10⁸ CFU/mL", 0.0, 50.0, A, T, ""),
            Parameter("KF", "Formate half-saturation", 5.0, "mg/L", 0.1, 100.0, A, T, ""),
            Parameter("F0", "Formate from milk heat treatment", 1.0, "mg/L", 0.0, 50.0, A, T,
                      "Intensive heating of milk generates some formate."),
            Parameter("alpha", "Acid per new biomass (α)", 0.45, "g/L per 10⁸ CFU/mL", 0.0, 3.0, A, T,
                      "Growth-associated lactic acid (Luedeking–Piret)."),
            Parameter("betaS", "S. thermophilus maintenance acid (β)", 0.02, "g/L/h per 10⁸ CFU/mL", 0.0, 0.5, A, T, ""),
            Parameter("betaL", "L. bulgaricus maintenance acid (β)", 0.03, "g/L/h per 10⁸ CFU/mL", 0.0, 0.5, A, T,
                      "Non-growth-associated acid; drives post-acidification."),
        ]
        return ParameterSet({p.symbol: p for p in ps})

    def default_initial_state(self) -> np.ndarray:
        p = self.default_parameters().values()
        return self.initial_state_from(p)

    @staticmethod
    def initial_state_from(p) -> np.ndarray:
        return np.array([p["XS0"], p["XL0"], p["Lac0"], 0.0, 0.0, p["P0"], p["F0"]])

    # ---- rates ----------------------------------------------------------
    def factors(self, y, p) -> dict:
        ph = milk_ph(y[ACID], p["buf"])
        sub = y[LAC] / (0.5 + y[LAC])
        fT_S = ctmi(p["T"], p["TminS"], p["ToptS"], p["TmaxS"])
        fT_L = ctmi(p["T"], p["TminL"], p["ToptL"], p["TmaxL"])
        fpH_S = cpm(ph, p["pHminS"], 6.5)
        fpH_L = cpm(ph, p["pHminL"], 5.8)
        coop_S = p["aS"] + (1 - p["aS"]) * y[PEP] / (p["KP"] + y[PEP])
        coop_L = p["aL"] + (1 - p["aL"]) * y[FORM] / (p["KF"] + y[FORM])
        muS = p["muS"] * fT_S * fpH_S * sub * coop_S
        muL = p["muL"] * fT_L * fpH_L * sub * coop_L
        # maintenance acidification continues below the growth pH limit, down to ~0.5 pH lower
        acid_S = fT_S * cpm(ph, p["pHminS"] - 0.5, 6.5) * sub
        acid_L = fT_L * cpm(ph, p["pHminL"] - 0.5, 5.8) * sub
        return dict(pH=ph, sub=sub, fT_S=fT_S, fT_L=fT_L, fpH_S=fpH_S, fpH_L=fpH_L,
                    coop_S=coop_S, coop_L=coop_L, muS=muS, muL=muL, acid_S=acid_S, acid_L=acid_L)

    def _terms(self, y, p):
        f = self.factors(y, p)
        gS, gL = f["muS"] * y[XS], f["muL"] * y[XL]
        acid_S = p["alpha"] * gS + p["betaS"] * f["acid_S"] * y[XS]
        acid_L = p["alpha"] * gL + p["betaL"] * f["acid_L"] * y[XL]
        prot = p["kP"] * f["fT_L"] * y[XL]
        return f, gS, gL, acid_S, acid_L, prot

    def rhs(self, t, y, p):
        f, gS, gL, aS, aL, prot = self._terms(y, p)
        acid = aS + aL
        return np.array([
            gS, gL,
            -LACTOSE_PER_LACTATE * acid,
            GAL_PER_LACTATE * acid,
            acid,
            prot - p["yP"] * gS,
            p["yF"] * gS,
        ])

    def flux_terms(self, y, p):
        f, gS, gL, aS, aL, prot = self._terms(y, p)
        return [
            FluxTerm("XS", "growth of S. thermophilus", gS, "μ_S·X_S"),
            FluxTerm("XL", "growth of L. bulgaricus", gL, "μ_L·X_L"),
            FluxTerm("Lac", "fermented by S. thermophilus", -LACTOSE_PER_LACTATE * aS, "−1.90·r_A,S"),
            FluxTerm("Lac", "fermented by L. bulgaricus", -LACTOSE_PER_LACTATE * aL, "−1.90·r_A,L"),
            FluxTerm("Gal", "excreted by S. thermophilus", GAL_PER_LACTATE * aS, "1.00·r_A,S"),
            FluxTerm("Gal", "excreted by L. bulgaricus", GAL_PER_LACTATE * aL, "1.00·r_A,L"),
            FluxTerm("A", "acid from S. thermophilus", aS, "α·μ_S·X_S + β_S·X_S"),
            FluxTerm("A", "acid from L. bulgaricus", aL, "α·μ_L·X_L + β_L·X_L"),
            FluxTerm("P", "released by L. bulgaricus proteolysis", prot, "k_P·f_T,L·X_L"),
            FluxTerm("P", "taken up by S. thermophilus", -p["yP"] * gS, "−y_P·μ_S·X_S"),
            FluxTerm("F", "produced by S. thermophilus", p["yF"] * gS, "y_F·μ_S·X_S"),
        ]

    def ph_series(self, traj) -> np.ndarray:
        b = traj.config.parameters["buf"]
        return np.array([milk_ph(a, b) for a in traj.series("A")])
