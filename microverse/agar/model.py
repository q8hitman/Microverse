"""Virtual agar plate: colony growth on a nutrient field (2-D reaction–diffusion). Qt-free.

MODEL (qualitative, dimensionless; after Kawasaki et al. 1997, J. Theor. Biol. 188:177, and
Mimura, Sakaguchi & Matsushita 2000, Physica A 282:283)

    ∂n/∂t = ∇²n − μ n b                         nutrient diffuses and is consumed
    ∂b/∂t = ∇·(D(x) n b ∇b) + μ n b − a(n,b) b   active cells: growth, nonlinear spreading
    ∂s/∂t = a(n,b) b                             cells that stopped (stationary/inactive)
    a(n,b) = a0 / ((1 + b/k1)(1 + n/k2))         cells stop where food and neighbours are scarce

TWO ORGANISMS AND ACID (v0.5.1)
    Up to two organisms share the nutrient; each has its own b, s, growth and spreading, and crowding counts
    both. Lactic acid bacteria release lactic acid h in proportion to their growth; it diffuses through the agar,
    and every organism's growth and spreading are multiplied by f(h) = max(0, 1 − h / (buffer · h_stop))².
    Growth stops completely at h_stop (the organism's pH minimum), like the cardinal pH models of the
    liquid labs; lactic acid bacteria tolerate more acid than they make, so they slow down but do not stop.
        ∂n/∂t = ∇²n − Σ μ_i n b_i f_i / Y_i            each organism uses food with its own yield Y_i
        ∂h/∂t = D_h ∇²h + Σ y_acid,i · μ_i n b_i f_i / Y_i    acid ∝ food fermented
    Acid-tolerant organisms (lactic acid bacteria, yeasts, moulds) have a high h_stop; most others a low one.
    This is how acid from a lactic culture can hold back a neighbour on a plate: a benign, food-related
    example of a diffusing inhibitor. Only lactic acid bacteria produce acid here (other fermentations are
    not modelled).

* Spreading needs both nutrient and cells (D·n·b), so a colony edge only advances where it is fed.
  On rich, soft agar colonies are round and compact (Eden-like); on poor, hard agar the edge becomes lobed and
  irregular, the direction of the morphology diagram of B. subtilis studied by Matsushita and colleagues.
  Thin DLA-like branches are NOT reproduced at this grid resolution (see docs/models/agar.md).
  D(x) carries small random agar heterogeneity, which seeds the irregularities.
* Time and space are dimensionless. `HOURS_PER_UNIT` maps model time to an ASSUMED clock time for display.
  Nothing here is calibrated; it is an educational, qualitative model of colony morphology.
* The dish wall is a no-flux boundary for every field (nothing diffuses into the plastic).
* Spot mode uses a finer grid (`spot_res`, default 1.5x finer) with the same physical scale, so a single
  colony's edge and branches are resolved better; time steps shrink with the grid spacing squared.
* Plating: the number of colonies started on a spread plate is a Poisson draw with mean
  density × volume plated × dilution. Colonies that grow into each other are counted as one, as on a
  real plate, so very crowded plates under-count (why the 30–300 rule exists).

Benign teaching organisms only. This module contains no wet-lab procedure.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage

HOURS_PER_UNIT = 1.0                 # assumed display scale: 1 model time unit ≈ 1 h
PUSH = 0.01                          # growth-pressure expansion (assumed)
NUTRIENT_SCALE = 2.0                 # 'rich medium = 1' maps to model n₀ = 2 (the compact-colony regime)
DISH_MM = 90.0                       # standard Petri dish diameter
FOUNDER = 0.02                       # density of a freshly plated cell's blob (invisible: threshold 0.15)
ACID_DIFFUSION = 1.4                 # lactate diffuses ~1.4x faster than glucose in water (≈1.0 vs 0.67 ×10⁻⁹ m²/s)


@dataclass(frozen=True)
class AgarOrganism:
    key: str
    growth: float                    # relative growth rate μ (dimensionless, from μmax)
    spread: float                    # relative spreading on agar: low for non-swarming cells on hard agar (assumed)
    colour: tuple[int, int, int]     # colony colour on the plate (RGB)
    texture: str                     # "smooth", "dry", "fuzzy", "pinpoint"
    note: str
    acid: float = 0.0                # lactic acid released per unit of nutrient used (lactic acid bacteria ≈ 0.9)
    yield_: float = 1.0              # biomass per unit of nutrient used (fermenters keep little as biomass; assumed)
    acid_stop: float = 0.5           # acid level that stops growth at standard buffering, i.e. the organism's
                                     # pH minimum reached (assumed; high = acid tolerant)


ORGANISMS = {
    "ecoli": AgarOrganism("ecoli", 1.0, 0.03, (232, 220, 190), "smooth", "Smooth, cream-coloured colonies."),
    "bsubtilis": AgarOrganism("bsubtilis", 0.8, 1.0, (238, 236, 226), "dry",
                              "Dry, wrinkled, spreading colonies; lobed when food is scarce and agar is hard.", acid_stop=0.35),
    "scerevisiae": AgarOrganism("scerevisiae", 0.35, 0.02, (240, 232, 205), "smooth",
                                "Glossy, round, cream colonies; slower than bacteria.", acid_stop=4.0),
    "llactis": AgarOrganism("llactis", 0.7, 0.02, (236, 236, 228), "pinpoint",
                            "Small, round, whitish colonies; releases lactic acid that spreads into the agar.",
                            acid=0.9, yield_=0.3, acid_stop=2.0),
    "pputida": AgarOrganism("pputida", 0.6, 0.9, (226, 228, 205), "smooth", "Flat, spreading colonies.", acid_stop=0.4),
    "aoryzae": AgarOrganism("aoryzae", 0.25, 1.4, (190, 210, 150), "fuzzy",
                            "Filamentous mould: fuzzy, expanding mycelium, yellow-green as it sporulates.", acid_stop=4.0),
}


@dataclass
class AgarParams:
    organism: str = "ecoli"
    nutrient: float = 1.0            # initial nutrient (1 = rich medium, 0.2 = poor)
    softness: float = 1.0            # 1 = standard 1.5 % agar, >1 softer (easier spreading), <1 harder
    heterogeneity: float = 0.5       # random variation of the agar (seeds branching)
    organism2: str = ""              # optional second organism ("" = one organism)
    buffering: float = 1.0           # agar buffering against acid (1 = ordinary nutrient agar)
    grid: int = 160                  # cells across the dish in spread mode
    spot_res: float = 1.5            # spot mode: grid this many times finer (same dish, same physics)
    a0: float = 0.06
    k1: float = 2.0
    k2: float = 0.5
    d0: float = 0.4
    # nutrient diffusion in model units: glucose D ≈ 0.67×10⁻⁹ m²/s ≈ 2.4 mm²/h; one model length unit is
    # 90/160 = 0.5625 mm and one time unit is HOURS_PER_UNIT h, so dn ≈ 2.4 / 0.5625² ≈ 7.6
    dn: float = 7.6
    seed: int = 1


@dataclass
class Plating:
    """How the plate was inoculated."""
    mode: str = "spread"             # "spread" (dilution plate) or "spot" (one central spot)
    density_cfu_ml: float = 1e7      # culture density
    dilution_exp: int = 5            # plated a 10^-k dilution
    volume_ml: float = 0.1           # volume spread on the plate
    mix2: float = 0.5                # with two organisms: fraction of the cells that are organism 2
    spot_gap_mm: float = 16.0        # with two organisms in spot mode: distance between the two spots
    delay2_h: float = 0.0            # organism 2 is added this long after organism 1 (deferred test; 0 = together)

    @property
    def expected_colonies(self) -> float:
        return self.density_cfu_ml * 10.0 ** (-self.dilution_exp) * self.volume_ml


@dataclass
class AgarRun:
    params: AgarParams
    plating: Plating
    times: list[float] = field(default_factory=list)          # model time of each frame
    frames: list[np.ndarray] = field(default_factory=list)    # colony density (b + s), float16
    nutrient: list[np.ndarray] = field(default_factory=list)  # nutrient field per frame, float16
    started: int = 0                                          # colonies actually started (Poisson draw)
    mask: np.ndarray | None = None
    frames2: list[np.ndarray] = field(default_factory=list)   # organism 2 density per frame (two organisms only)
    acid: list[np.ndarray] = field(default_factory=list)      # lactic acid field per frame (if any producer)
    started2: int = 0                                         # of `started`, how many were organism 2
    mm_per_cell: float = DISH_MM / 160

    @property
    def grid(self) -> int:
        return self.mask.shape[0]

    def counts(self, i: int, threshold: float = 0.15) -> tuple[int, np.ndarray]:
        """Colonies visible in frame i (touching colonies merge, as on a real plate)."""
        lab, n = ndimage.label((self.frames[i].astype(float) > threshold) & self.mask)
        sizes = ndimage.sum(np.ones_like(lab), lab, index=np.arange(1, n + 1)) if n else np.array([])
        return n, np.asarray(sizes)

    def counts_by_species(self, i: int, threshold: float = 0.15) -> tuple[int, int]:
        """Visible colonies of organism 1 and organism 2 in frame i (a merged colony goes to its majority)."""
        if not self.frames2:
            return self.counts(i, threshold)[0], 0
        tot = self.frames[i].astype(float)
        lab, n = ndimage.label((tot > threshold) & self.mask)
        if not n:
            return 0, 0
        f2 = ndimage.sum(self.frames2[i].astype(float), lab, index=np.arange(1, n + 1))
        ft = ndimage.sum(tot, lab, index=np.arange(1, n + 1))
        two = int(np.sum(f2 > 0.5 * ft))
        return n - two, two

    def back_calculated_cfu(self, i: int) -> float:
        n, _ = self.counts(i)
        return n / (10.0 ** (-self.plating.dilution_exp) * self.plating.volume_ml)


def dish_mask(n: int) -> np.ndarray:
    yy, xx = np.mgrid[0:n, 0:n]
    c = (n - 1) / 2
    return (xx - c) ** 2 + (yy - c) ** 2 <= (c - 1) ** 2


# 8-neighbour stencil with isotropic weights (axial 2/3, diagonal 1/6): avoids the square-lattice
# artefact (colonies growing as crosses) of the 4-neighbour scheme.
_NB = [((0, 1), 2 / 3), ((0, -1), 2 / 3), ((1, 0), 2 / 3), ((-1, 0), 2 / 3),
       ((1, 1), 1 / 6), ((1, -1), 1 / 6), ((-1, 1), 1 / 6), ((-1, -1), 1 / 6)]


_K = np.zeros((3, 3))
for (_dy, _dx), _w in _NB:
    _K[1 + _dy, 1 + _dx] = _w


class _Grid:
    """Isotropic 8-neighbour operators with zero weight across the dish wall (a no-flux boundary).

    Fields are zero outside the dish, so Σ_j w·m_j·f_j is just a 3×3 convolution of f, and the
    number of open neighbours is a convolution of the mask (computed once)."""

    def __init__(self, mask: np.ndarray, dx: float):
        self.m = mask.astype(float)
        self.inv_dx2 = 1.0 / dx ** 2
        self.open = self._conv(self.m) * self.m

    @staticmethod
    def _conv(f):
        return ndimage.convolve(f, _K, mode="constant")

    def lap(self, f: np.ndarray) -> np.ndarray:
        return (self._conv(f) * self.m - f * self.open) * self.inv_dx2

    def diffuse(self, f: np.ndarray, d: float, dt: float) -> np.ndarray:
        """Advance ∂f/∂t = d ∇²f by dt with as many stable explicit sub-steps as needed."""
        k = max(1, int(np.ceil(dt * d * self.inv_dx2 * (10 / 3) / 0.45)))
        for _ in range(k):
            f = f + (dt / k) * d * self.lap(f)
        return f

    def div_flux(self, b: np.ndarray, D: np.ndarray) -> np.ndarray:
        """∇·(D ∇b), conservative: neighbours exchange w·(D_i + D_j)/2·(b_j − b_i)."""
        return 0.5 * self.m * (D * self._conv(b) - D * b * self.open + self._conv(D * b) - b * self._conv(D))             * self.inv_dx2


def simulate(params: AgarParams, plating: Plating, t_end: float = 60.0, frames: int = 90,
             progress=None) -> AgarRun:
    rng = np.random.default_rng(params.seed)
    orgs = [ORGANISMS[params.organism]] + ([ORGANISMS[params.organism2]] if params.organism2 else [])
    res = params.spot_res if plating.mode == "spot" else 1.0
    n_grid = int(round(params.grid * res))
    dx = 1.0 / res                                           # model length per cell (1 = a spread-mode cell)
    mm_cell = DISH_MM / n_grid
    mask = dish_mask(n_grid)
    grid = _Grid(mask, dx)
    n = np.where(mask, params.nutrient * NUTRIENT_SCALE, 0.0)
    b = [np.zeros((n_grid, n_grid)) for _ in orgs]
    s = [np.zeros((n_grid, n_grid)) for _ in orgs]
    h = np.zeros((n_grid, n_grid))
    yy, xx = np.mgrid[0:n_grid, 0:n_grid]
    c = (n_grid - 1) / 2
    if plating.mode == "spot":
        k = len(orgs)
        k2 = 1 if len(orgs) == 2 else 0
        gap = plating.spot_gap_mm / mm_cell / 2 if len(orgs) == 2 else 0.0
        founders = [np.zeros((n_grid, n_grid)) for _ in orgs]
        for j in range(len(orgs)):                           # one round spot (two side by side for two organisms)
            cx = c + (gap if j else -gap)
            founders[j][(yy - c) ** 2 + (xx - cx) ** 2 <= (2.5 * res) ** 2] = 0.5
    else:
        k = int(rng.poisson(plating.expected_colonies))
        inside = np.argwhere(mask)
        ok = inside[((inside - c) ** 2).sum(1) <= (c - 4 * res) ** 2]
        pick = ok[rng.integers(0, len(ok), size=k)] if k else np.zeros((0, 2), int)
        which = (rng.random(k) < plating.mix2).astype(int) if len(orgs) == 2 else np.zeros(k, int)
        k2 = int(which.sum())
        founders = [np.zeros((n_grid, n_grid)) for _ in orgs]
        # each founder: a tiny round blob (not one grid cell), below the visibility threshold, so a colony becomes
        # visible only after it has grown, as on a real plate
        for (y, x), j in zip(pick, which):
            founders[j] += FOUNDER * np.exp(-((yy - y) ** 2 + (xx - x) ** 2) / (2 * (1.3 * res) ** 2))
    b[0] = founders[0] * mask
    added2 = len(orgs) < 2
    noise = ndimage.gaussian_filter(rng.standard_normal((n_grid, n_grid)), 1.2 * res)   # agar varies smoothly
    noise /= max(noise.std(), 1e-9)
    hetero = np.clip(1 + params.heterogeneity * noise, 0.05, None)
    D = [params.d0 * params.softness * o.spread * hetero for o in orgs]
    acidic = any(o.acid > 0 for o in orgs)
    run = AgarRun(params, plating, started=k, mask=mask, started2=k2, mm_per_cell=mm_cell)
    dt = 0.1 * dx * dx
    steps = int(round(t_end / dt))
    every = max(1, steps // frames)
    for step in range(steps + 1):
        if not added2 and step * dt >= plating.delay2_h / HOURS_PER_UNIT - 1e-9:
            b[1] = b[1] + founders[1] * mask                 # organism 2 arrives (at once, or after the delay)
            added2 = True
        if step % every == 0:
            run.times.append(step * dt)
            run.frames.append((sum(b) + sum(s)).astype(np.float16))
            run.nutrient.append(n.astype(np.float16))
            if len(orgs) == 2:
                run.frames2.append((b[1] + s[1]).astype(np.float16))
            if acidic:
                run.acid.append(h.astype(np.float16))
            if progress:
                progress(step, steps)
        # Operator splitting. (1) Growth, stopping and cell spreading; explicit Euler is stable only while
        # h_dt · D_eff · Σw / dx² stays small, and where cells pile up on rich, soft agar D_eff = D·n·b gets large,
        # so take as many equal sub-steps as needed.
        d_eff = max(0.1, max(float(np.max(D[j] * n * b[j])) for j in range(len(orgs))) + PUSH)
        sub = max(1, int(np.ceil(dt * d_eff * grid.inv_dx2 * (10 / 3) / 0.45)))
        h_dt = dt / sub
        for _ in range(sub):
            crowd = params.a0 / ((1 + sum(b) / params.k1) * (1 + n / params.k2))
            dn = 0.0
            dh = 0.0
            push = PUSH * np.minimum(n, 1.0)
            for j, o in enumerate(orgs):
                f = np.maximum(0.0, 1.0 - h / (params.buffering * o.acid_stop)) ** 2 if acidic else 1.0
                growth = o.growth * n * b[j] * f
                stop = crowd * b[j]
                used = growth / o.yield_
                dn = dn - used
                if o.acid:
                    dh = dh + o.acid * used
                # plus a small linear, isotropic push of growing cells (growth pressure), so colonies of cells that
                # hardly spread stay round instead of taking the grid's square shape
                b[j] = b[j] + h_dt * (grid.div_flux(b[j], D[j] * n * b[j] * f) + push * grid.lap(b[j]) + growth - stop)
                s[j] = s[j] + h_dt * stop
                b[j] = np.where(mask, np.maximum(b[j], 0.0), 0.0)
            n = np.where(mask, np.maximum(n + h_dt * dn, 0.0), 0.0)
            if acidic:
                h = np.where(mask, np.maximum(h + h_dt * dh, 0.0), 0.0)
        # (2) Diffusion of the small molecules (food, acid), which is much faster than cells spread: cheap
        # sub-steps of a plain diffusion equation.
        n = grid.diffuse(n, params.dn, dt)
        if acidic:
            h = grid.diffuse(h, params.dn * ACID_DIFFUSION, dt)
    return run


def radius_mm(run: AgarRun, i: int) -> float:
    """Equivalent radius of the largest colony in frame i, in mm on a 90 mm dish."""
    n, sizes = run.counts(i)
    if not n:
        return 0.0
    return float(np.sqrt(sizes.max() / np.pi) * run.mm_per_cell)


def fill_fraction(run: AgarRun, i: int) -> float:
    """Area of the largest colony ÷ area of the disc reaching its farthest point (1 = round, lower = lobed)."""
    lab, n = ndimage.label((run.frames[i].astype(float) > 0.15) & run.mask)
    if not n:
        return float("nan")
    sizes = ndimage.sum(np.ones_like(lab), lab, index=np.arange(1, n + 1))
    z = lab == (int(np.argmax(sizes)) + 1)
    ys, xs = np.nonzero(z)
    r = np.hypot(ys - ys.mean(), xs - xs.mean()).max() + 0.5
    return float(min(1.0, z.sum() / (np.pi * r * r)))


def fractal_dimension(img: np.ndarray) -> float:
    """Box-counting dimension of a colony mask (≈2 compact, ≈1.7 branched/DLA-like)."""
    z = img.astype(bool)
    if z.sum() < 20:
        return float("nan")
    ys, xs = np.nonzero(z)                               # crop to the colony so empty agar does not count
    z = z[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    side = max(z.shape)
    z = np.pad(z, ((0, side - z.shape[0]), (0, side - z.shape[1])))
    if side < 16:
        return float("nan")
    sizes, counts = [], []
    s = 2
    while s < min(z.shape) // 2:
        h = z.shape[0] // s * s
        w = z.shape[1] // s * s
        blocks = z[:h, :w].reshape(h // s, s, w // s, s).any(axis=(1, 3)).sum()
        sizes.append(s)
        counts.append(blocks)
        s *= 2
    if len(sizes) < 3:
        return float("nan")
    slope = np.polyfit(np.log(sizes), np.log(np.maximum(counts, 1)), 1)[0]
    return float(min(-slope, 2.0))                       # a filled plane is 2; the estimator overshoots slightly
