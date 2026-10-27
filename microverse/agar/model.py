"""Virtual agar plate: colony growth on a nutrient field (2-D reaction–diffusion). Qt-free.

MODEL (qualitative, dimensionless; after Kawasaki et al. 1997, J. Theor. Biol. 188:177, and
Mimura, Sakaguchi & Matsushita 2000, Physica A 282:283)

    ∂n/∂t = ∇²n − μ n b                         nutrient diffuses and is consumed
    ∂b/∂t = ∇·(D(x) n b ∇b) + μ n b − a(n,b) b   active cells: growth, nonlinear spreading
    ∂s/∂t = a(n,b) b                             cells that stopped (stationary/inactive)
    a(n,b) = a0 / ((1 + b/k1)(1 + n/k2))         cells stop where food and neighbours are scarce

* Spreading needs both nutrient and cells (D·n·b), so a colony edge only advances where it is fed.
  On rich, soft agar colonies are round and compact (Eden-like); on poor, hard agar the same equations
  produce branched (dendritic, DLA-like) colonies — the morphology diagram of B. subtilis studied by
  Matsushita and colleagues. D(x) carries small random agar heterogeneity, which seeds the branches.
* Time and space are dimensionless. `HOURS_PER_UNIT` maps model time to an ASSUMED clock time for display.
  Nothing here is calibrated; it is an educational, qualitative model of colony morphology.
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


@dataclass(frozen=True)
class AgarOrganism:
    key: str
    growth: float                    # relative growth rate μ (dimensionless, from μmax)
    spread: float                    # relative spreading on agar: low for non-swarming cells on hard agar (assumed)
    colour: tuple[int, int, int]     # colony colour on the plate (RGB)
    texture: str                     # "smooth", "dry", "fuzzy", "pinpoint"
    note: str


ORGANISMS = {
    "ecoli": AgarOrganism("ecoli", 1.0, 0.03, (232, 220, 190), "smooth", "Smooth, cream-coloured colonies."),
    "bsubtilis": AgarOrganism("bsubtilis", 0.8, 1.0, (238, 236, 226), "dry",
                              "Dry, wrinkled, spreading colonies; branched when food is scarce and agar is hard."),
    "scerevisiae": AgarOrganism("scerevisiae", 0.35, 0.02, (240, 232, 205), "smooth",
                                "Glossy, round, cream colonies; slower than bacteria."),
    "llactis": AgarOrganism("llactis", 0.7, 0.02, (236, 236, 228), "pinpoint", "Small, round, whitish colonies."),
    "pputida": AgarOrganism("pputida", 0.6, 0.9, (226, 228, 205), "smooth", "Flat, spreading colonies."),
    "aoryzae": AgarOrganism("aoryzae", 0.25, 1.4, (190, 210, 150), "fuzzy",
                            "Filamentous mould: fuzzy, expanding mycelium, yellow-green as it sporulates."),
}


@dataclass
class AgarParams:
    organism: str = "ecoli"
    nutrient: float = 1.0            # initial nutrient (1 = rich medium, 0.2 = poor)
    softness: float = 1.0            # 1 = standard 1.5 % agar, >1 softer (easier spreading), <1 harder
    heterogeneity: float = 0.5       # random variation of the agar (seeds branching)
    grid: int = 160
    a0: float = 0.06
    k1: float = 2.0
    k2: float = 0.5
    d0: float = 0.4
    seed: int = 1


@dataclass
class Plating:
    """How the plate was inoculated."""
    mode: str = "spread"             # "spread" (dilution plate) or "spot" (one central spot)
    density_cfu_ml: float = 1e7      # culture density
    dilution_exp: int = 5            # plated a 10^-k dilution
    volume_ml: float = 0.1           # volume spread on the plate

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

    def counts(self, i: int, threshold: float = 0.15) -> tuple[int, np.ndarray]:
        """Colonies visible in frame i (touching colonies merge, as on a real plate)."""
        lab, n = ndimage.label((self.frames[i].astype(float) > threshold) & self.mask)
        sizes = ndimage.sum(np.ones_like(lab), lab, index=np.arange(1, n + 1)) if n else np.array([])
        return n, np.asarray(sizes)

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


def _lap(f: np.ndarray) -> np.ndarray:
    out = np.zeros_like(f)
    for (dy, dx), w in _NB:
        out += w * (np.roll(f, (dy, dx), axis=(0, 1)) - f)
    return out


def _div_flux(b: np.ndarray, D: np.ndarray) -> np.ndarray:
    """∇·(D ∇b), conservative: each pair of neighbours exchanges w·D_face·(b_j − b_i)."""
    out = np.zeros_like(b)
    for (dy, dx), w in _NB:
        bj = np.roll(b, (dy, dx), axis=(0, 1))
        Dj = np.roll(D, (dy, dx), axis=(0, 1))
        out += w * 0.5 * (D + Dj) * (bj - b)
    return out


def simulate(params: AgarParams, plating: Plating, t_end: float = 60.0, frames: int = 90,
             progress=None) -> AgarRun:
    rng = np.random.default_rng(params.seed)
    org = ORGANISMS[params.organism]
    n_grid = params.grid
    mask = dish_mask(n_grid)
    n = np.where(mask, params.nutrient * NUTRIENT_SCALE, 0.0)
    b = np.zeros((n_grid, n_grid))
    s = np.zeros_like(b)
    yy, xx = np.mgrid[0:n_grid, 0:n_grid]
    if plating.mode == "spot":
        k = 1
        c = (n_grid - 1) / 2
        b[(yy - c) ** 2 + (xx - c) ** 2 <= 2.5 ** 2] = 0.5             # a round inoculation spot
    else:
        k = int(rng.poisson(plating.expected_colonies))
        inside = np.argwhere(mask)
        r = (n_grid - 1) / 2
        ok = inside[((inside - r) ** 2).sum(1) <= (r - 4) ** 2]
        pick = ok[rng.integers(0, len(ok), size=k)] if k else np.zeros((0, 2), int)
        for y, x in pick:                                   # each founder: a tiny round blob, not one grid cell
            b += 0.5 * np.exp(-((yy - y) ** 2 + (xx - x) ** 2) / (2 * 1.3 ** 2))
    noise = ndimage.gaussian_filter(rng.standard_normal(b.shape), 1.2)   # agar varies smoothly, not per cell
    noise /= max(noise.std(), 1e-9)
    hetero = np.clip(1 + params.heterogeneity * noise, 0.05, None)
    D = params.d0 * params.softness * org.spread * hetero
    mu = org.growth
    run = AgarRun(params, plating, started=k, mask=mask)
    dt = 0.1
    steps = int(round(t_end / dt))
    every = max(1, steps // frames)
    for step in range(steps + 1):
        if step % every == 0:
            run.times.append(step * dt)
            run.frames.append((b + s).astype(np.float16))
            run.nutrient.append(n.astype(np.float16))
            if progress:
                progress(step, steps)
        growth = mu * n * b
        stop = params.a0 / ((1 + b / params.k1) * (1 + n / params.k2)) * b
        Db = D * n * b
        n = n + dt * (_lap(n) - growth)
        # plus a small linear, isotropic push of growing cells (growth pressure), so colonies of cells that
        # hardly spread stay round instead of taking the grid's square shape
        b = b + dt * (_div_flux(b, Db) + PUSH * np.minimum(n, 1.0) * _lap(b) + growth - stop)
        s = s + dt * stop
        n = np.where(mask, np.maximum(n, 0.0), 0.0)
        b = np.where(mask, np.maximum(b, 0.0), 0.0)
    return run


def radius_mm(run: AgarRun, i: int) -> float:
    """Equivalent radius of the largest colony in frame i, in mm on a 90 mm dish."""
    n, sizes = run.counts(i)
    if not n:
        return 0.0
    cell_mm = DISH_MM / run.params.grid
    return float(np.sqrt(sizes.max() / np.pi) * cell_mm)


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
