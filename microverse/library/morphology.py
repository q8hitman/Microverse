"""Morphology specifications: how each organism LOOKS, MOVES and DIVIDES under the microscope.

The simulation models are population models (biomass per litre). They say nothing about the shape
of an individual cell. These specs therefore come from the descriptive literature (typical textbook
ranges, e.g. Bergey's Manual, Brock Biology of Microorganisms, Pennak's Fresh-Water Invertebrates)
and are used ONLY by the renderer. They are not predictions: a drawn cell shows what a typical cell
of that species looks like, not what this simulation computed for an individual.

Every spec carries `provenance` so the UI can say where the picture comes from.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# --- vocabularies (kept small and explicit so the renderer can switch on them)
SHAPES = ("coccus", "ovococcus", "rod", "club_rod", "oval", "sphere", "coenobium", "boat", "spindle",
          "pear", "slipper", "amoeboid", "bell", "rotifer_lorica", "rotifer_bdelloid", "hypha", "packet")
ARRANGEMENTS = ("single", "pairs", "chains", "packets", "colony", "mycelium")
MOTILITY = {
    "none": "Non-motile: moves only by Brownian motion and gentle drift",
    "run_tumble": "Peritrichous flagella: straight runs interrupted by random tumbles",
    "run_reverse": "Polar flagellum: runs that reverse direction",
    "slow_swim": "Weakly motile: slow, wandering swimming",
    "ciliary": "Cilia: fast swimming along a helical path while the cell rotates",
    "flagellar": "One long anterior flagellum: forward swimming with a side-to-side wobble",
    "amoeboid": "Crawling: the cell flows into pseudopodia, slowly changing direction",
    "gliding": "Gliding along the surface through the raphe, back and forth",
    "sessile": "Attached by a stalk; the stalk contracts now and then",
    "corona": "Swims with the ciliated corona, wide gentle turns",
    "creeping": "Creeps like a leech, alternating with short swims",
    "hyphal": "Does not move: grows by extending hyphal tips",
}
DIVISION = {
    "binary_fission": "Binary fission: the cell elongates, constricts in the middle and splits in two",
    "chain_fission": "Fission in one plane: daughter cells stay attached, so chains grow longer and then break",
    "packet_fission": "Division in alternating planes: cells stay together as packets",
    "budding": "Budding: a small bud grows out of the mother cell and separates",
    "autospores": "Autospores: the mother cell swells, divides inside its wall and releases 4 small daughters",
    "coenobium": "Each cell of the colony forms a new daughter colony inside its wall",
    "diatom_valve": "Valve division: each daughter keeps one half of the silica shell, so one is slightly smaller",
    "transverse_fission": "Transverse fission: the cell pinches across its middle into a front and a back daughter",
    "longitudinal_fission": "Longitudinal fission: the cell splits along its length, from the front end",
    "amoeboid_fission": "The amoeba rounds up, then pinches into two that crawl apart",
    "parthenogenesis": "Females carry eggs that hatch into small juveniles (no males needed)",
    "hyphal_extension": "Hyphae extend at their tips and branch behind the tip",
}


@dataclass(frozen=True)
class MorphSpec:
    shape: str
    length_um: float                   # typical longest dimension of one unit (cell, colony, organism)
    width_um: float
    arrangement: str = "single"
    max_chain: int = 1                 # cells per chain/packet before it breaks
    motility: str = "none"
    speed_um_s: float = 0.0            # typical swimming/crawling speed (order of magnitude)
    division: str = "binary_fission"
    division_s: float = 1.2            # visual duration of one division at normal playback (real seconds)
    features: tuple[str, ...] = ()
    size_cv: float = 0.15              # cell-to-cell variation in size
    colour: str = "#9da7b3"            # natural colour in brightfield
    provenance: str = "literature_estimate"
    reference: str = ""
    notes: str = ""

    @property
    def aspect(self) -> float:
        return self.width_um / max(self.length_um, 1e-9)

    def describe(self) -> tuple[str, str]:
        return MOTILITY.get(self.motility, self.motility), DIVISION.get(self.division, self.division)


BERGEY = "Bergey's Manual of Systematic Bacteriology; Madigan et al., Brock Biology of Microorganisms"
PROTIST = "Lee, Leedale & Bradbury, Illustrated Guide to the Protozoa; Patterson, Free-living Freshwater Protozoa"
ALGAE = "Wehr & Sheath, Freshwater Algae of North America; Round, Crawford & Mann, The Diatoms"
ROTIFER = "Wallace & Snell in Thorp & Covich, Ecology and Classification of North American Freshwater Invertebrates"
FUNGI = "Carlile, Watkinson & Gooday, The Fungi; Samson et al., Food and Indoor Fungi"
MOTION = ("Speeds: Berg (2004) E. coli in Motion; Sleigh & Blake (1977) ciliary propulsion; typical values, "
          "order of magnitude only")

SPECS: dict[str, MorphSpec] = {
    # --- lactic acid bacteria
    "sthermophilus": MorphSpec("coccus", 0.8, 0.8, "chains", 10, division="chain_fission",
                               colour="#c9c2d6", reference=BERGEY,
                               notes="Pairs and chains of spherical-to-ovoid cells, 0.7–0.9 µm."),
    "lbulgaricus": MorphSpec("rod", 5.0, 0.65, "single", division="binary_fission", size_cv=0.35,
                             colour="#cfc5b4", reference=BERGEY,
                             notes="Long slender rods 0.5–0.8 × 2–9 µm, single or in short chains."),
    "llactis": MorphSpec("ovococcus", 1.0, 0.8, "chains", 6, division="chain_fission", colour="#c8c4d8",
                         reference=BERGEY, notes="Ovoid cocci elongated along the chain axis."),
    "lplantarum": MorphSpec("rod", 3.5, 1.0, "pairs", 2, division="chain_fission", size_cv=0.25,
                            colour="#d0c6b0", reference=BERGEY),
    "leuconostoc": MorphSpec("ovococcus", 1.0, 0.65, "chains", 8, division="chain_fission", colour="#cbc6d6",
                             reference=BERGEY, features=("capsule",),
                             notes="Lenticular cocci in pairs and chains; dextran capsule on sucrose."),
    "pfreudenreichii": MorphSpec("club_rod", 2.0, 0.6, "single", division="binary_fission", size_cv=0.3,
                                 colour="#d6c3cf", reference=BERGEY,
                                 notes="Pleomorphic 'diphtheroid' rods, often V or Y arrangements."),
    "aaceti": MorphSpec("rod", 1.5, 0.6, "pairs", 2, "slow_swim", 8.0, "chain_fission", colour="#d4cdb0",
                        features=("peritrichous_flagella",), reference=BERGEY,
                        notes="Motility is strain-dependent; drawn as weakly motile."),
    # --- other bacteria
    "bsubtilis": MorphSpec("rod", 4.0, 0.8, "chains", 3, "run_tumble", 25.0, "chain_fission",
                           features=("peritrichous_flagella", "endospore"), colour="#cfd2c0",
                           reference=BERGEY + "; " + MOTION),
    "ecoli": MorphSpec("rod", 2.0, 0.6, "single", 1, "run_tumble", 25.0, "binary_fission",
                       features=("peritrichous_flagella",), colour="#d3c9c4", reference=BERGEY + "; " + MOTION,
                       notes="Runs ≈1 s at ≈20–30 µm/s, tumbles ≈0.1 s (Berg 2004)."),
    "pputida": MorphSpec("rod", 2.5, 0.7, "single", 1, "run_reverse", 35.0, "binary_fission",
                         features=("polar_flagellum",), colour="#c8d0c0", reference=BERGEY + "; " + MOTION),
    "azotobacter": MorphSpec("oval", 3.0, 2.0, "pairs", 2, "slow_swim", 15.0, "chain_fission",
                             features=("peritrichous_flagella", "capsule"), colour="#c6d3c8", reference=BERGEY,
                             notes="Unusually large ovoid cells, often in pairs."),
    "nitrosomonas": MorphSpec("rod", 1.5, 0.8, "single", 1, "none", 0.0, "binary_fission",
                              features=("membranes",), colour="#c4c6c8", reference=BERGEY,
                              notes="Short rods with peripheral intracytoplasmic membranes."),
    "synechococcus": MorphSpec("rod", 2.5, 1.1, "single", 1, "none", 0.0, "binary_fission",
                               features=("thylakoids",), colour="#7fb7a6", reference=ALGAE,
                               notes="Cylindrical cells; blue-green pigment (phycocyanin + chlorophyll)."),
    "methanosarcina": MorphSpec("packet", 2.0, 2.0, "packets", 8, "none", 0.0, "packet_fission",
                                colour="#c9c0d6", reference=BERGEY,
                                notes="Irregular cocci in packets/aggregates (sarcina-like)."),
    "halobacterium": MorphSpec("rod", 4.0, 0.6, "single", 1, "slow_swim", 3.0, "binary_fission",
                               features=("polar_flagellum", "gas_vesicles"), colour="#e0a3a0", size_cv=0.3,
                               reference=BERGEY, notes="Archaeon; pink-red from bacterioruberin; slow swimmer."),
    # --- yeasts
    "scerevisiae": MorphSpec("oval", 6.0, 5.0, "single", 1, "none", 0.0, "budding", 1.6,
                             features=("vacuole", "bud_scar"), colour="#e2d7b8", reference=FUNGI,
                             notes="Multilateral budding; bud separates when it reaches ≈2/3 of the mother."),
    "klactis": MorphSpec("oval", 5.0, 4.0, "single", 1, "none", 0.0, "budding", 1.6, features=("vacuole",),
                         colour="#e0d8bc", reference=FUNGI),
    # --- filamentous fungi
    "aoryzae": MorphSpec("hypha", 60.0, 6.0, "mycelium", motility="hyphal", division="hyphal_extension",
                         division_s=2.0, features=("septa", "conidiophore"), colour="#cfe0c4", reference=FUNGI),
    "proqueforti": MorphSpec("hypha", 50.0, 3.5, "mycelium", motility="hyphal", division="hyphal_extension",
                             division_s=2.0, features=("septa", "penicillus"), colour="#b9d8c0", reference=FUNGI),
    "roligosporus": MorphSpec("hypha", 70.0, 10.0, "mycelium", motility="hyphal",
                              division="hyphal_extension", division_s=1.8, features=("aseptate", "sporangium"),
                              colour="#d8e2cf", reference=FUNGI),
    # --- algae
    "chlorella": MorphSpec("sphere", 5.0, 5.0, "single", 1, "none", 0.0, "autospores", 2.0,
                           features=("cup_chloroplast", "pyrenoid"), size_cv=0.25, colour="#3f9b3a",
                           reference=ALGAE, notes="Reproduces by 2–16 (usually 4) autospores; no flagella."),
    "scenedesmus": MorphSpec("coenobium", 20.0, 10.0, "colony", 4, "none", 0.0, "coenobium", 2.0,
                             features=("spines", "chloroplast"), colour="#4a9e3f", reference=ALGAE,
                             notes="Flat colonies (coenobia) of 4 cells side by side, spines on the end cells."),
    "navicula": MorphSpec("boat", 30.0, 8.0, "single", 1, "gliding", 3.0, "diatom_valve", 2.0,
                          features=("raphe", "striae", "plastids"), colour="#b89a48", reference=ALGAE,
                          notes="Gliding speed ≈1–10 µm/s; daughter cells shrink slightly (MacDonald–Pfitzer)."),
    "euglena": MorphSpec("spindle", 50.0, 12.0, "single", 1, "flagellar", 80.0, "longitudinal_fission", 2.0,
                         features=("flagellum", "eyespot", "chloroplasts", "pellicle"), colour="#5daa4a",
                         reference=PROTIST + "; " + MOTION),
    # --- protists
    "tetrahymena": MorphSpec("pear", 50.0, 28.0, "single", 1, "ciliary", 300.0, "transverse_fission", 1.6,
                             features=("cilia", "oral_apparatus", "macronucleus", "contractile_vacuole"),
                             colour="#d8cfae", reference=PROTIST + "; " + MOTION),
    "paramecium": MorphSpec("slipper", 220.0, 60.0, "single", 1, "ciliary", 900.0, "transverse_fission", 1.8,
                            features=("cilia", "oral_groove", "macronucleus", "contractile_vacuole",
                                      "food_vacuoles"), colour="#dcd3b0", reference=PROTIST + "; " + MOTION,
                            notes="Swims ≈1 mm/s along a left-handed helix while rotating."),
    "vorticella": MorphSpec("bell", 60.0, 40.0, "single", 1, "sessile", 0.0, "longitudinal_fission", 2.0,
                            features=("stalk", "cilia", "macronucleus"), colour="#dad2b0", reference=PROTIST,
                            notes="Bell on a contractile stalk; after division one daughter swims off as a "
                                  "telotroch (not drawn)."),
    "amoeba": MorphSpec("amoeboid", 500.0, 300.0, "single", 1, "amoeboid", 2.0, "amoeboid_fission", 2.4,
                        features=("pseudopodia", "nucleus", "contractile_vacuole", "food_vacuoles"),
                        colour="#cfc6d8", size_cv=0.2, reference=PROTIST,
                        notes="Crawls ≈1–3 µm/s; drawn speed is real time."),
    # --- rotifers
    "brachionus": MorphSpec("rotifer_lorica", 250.0, 140.0, "single", 1, "corona", 500.0, "parthenogenesis",
                            2.4, features=("lorica", "spines", "corona", "mastax", "foot", "eggs"),
                            colour="#d9cfb8", reference=ROTIFER,
                            notes="Amictic females carry 1–3 eggs attached to the lorica."),
    "philodina": MorphSpec("rotifer_bdelloid", 400.0, 90.0, "single", 1, "creeping", 120.0, "parthenogenesis",
                           2.4, features=("corona", "mastax", "telescoping"), colour="#e6c1b6", reference=ROTIFER,
                           notes="Bdelloid: all-female, viviparous in many species; red pigment in the gut."),
}


def spec_for(key: str) -> MorphSpec:
    """Morphology for an organism key; falls back to a plain rod so new records still render."""
    if key in SPECS:
        return SPECS[key]
    from .organisms import ORGANISMS
    o = ORGANISMS.get(key)
    size = o.size_um if o else 2.0
    return MorphSpec("rod", size, size * 0.4, provenance="assumed", notes="No morphology record yet.")
