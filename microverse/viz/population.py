"""Persistent visual populations: the bridge between a population model and a microscope picture.

WHY THIS EXISTS
The models compute biomass per litre, not individual cells. The old scenes turned that number into
pictures with an immigration–death process: every frame each drawn cell vanished with probability
dt/0.6 s and new cells were dropped at random positions. Cells therefore lived ≈0.6 real seconds,
popped in and out everywhere — even while playback was paused — and the per-species dilution factor
jumped in 2× steps. That was the "spawning" the owner saw.

WHAT THIS DOES INSTEAD
* Every drawn unit (cell, chain, colony, organism) is an `Agent` with a persistent id and position.
* The number of drawn cells follows the model through REPRESENTATIVE BIOLOGICAL TRANSITIONS:
  more cells → existing cells divide in the way that species divides (fission, budding, autospores,
  hyphal branching…); fewer cells → cells lyse, are eaten by a predator in view, or swim out of view.
  A new cell can only appear from a parent, or by drifting/swimming in from the edge of the field
  when none is in view.
* Biology follows SIMULATION time: while playback is paused the model state is constant, so no new
  divisions or deaths are started (transitions already needed finish, so a slider jump settles);
  swimming runs on REAL time, so a paused sample still looks alive, like a slide under a microscope.
* Agents are cohorts: one drawn cell stands for `concentration` cells of that species (shown in the
  legend). An animated division is a visual summary of population growth, not a resolved event.

The module is Qt-free so it can be unit-tested.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

import numpy as np

from ..library.morphology import MorphSpec

LIVE, DIVIDING, DYING, GRAZED, ENTERING, LEAVING = range(6)
STATE_NAMES = ("live", "dividing", "dying", "being eaten", "entering view", "leaving view")

# cells gained per completed division, by division style (autospores decide at start)
GAIN = {"autospores": 3}


@dataclass(slots=True)
class Agent:
    id: int
    x: float                     # µm, field coordinates
    y: float
    heading: float               # rad; long-axis direction for cells, swimming direction for swimmers
    n: int = 1                   # cells in this unit (chain/packet length)
    size: float = 1.0            # individual size factor (natural variation)
    grow: float = 1.0            # maturity 0..1 of a newborn (drawn size scales with it)
    phase: float = 0.0           # animation phase (cilia beat, wobble, pseudopodia)
    state: int = LIVE
    progress: float = 0.0        # 0..1 progress of the current transition
    duration: float = 1.0        # real seconds the transition takes at current speed
    gain: int = 1                # cells this division will add
    timer: float = 0.0           # motility timer (run length, tumble, reversal, contraction)
    tumbling: bool = False
    vx: float = 0.0              # current velocity (µm/s) — kept so motion is continuous
    vy: float = 0.0
    parent: int = -1
    prey_of: int = -1            # predator agent id when being eaten
    tail_fade: float = 0.0       # 0..1 fading of the last cell of a chain
    variant: float = 0.0         # 0..1, stable per-agent appearance variation
    ax: float = 0.0              # anchor (sessile stalk base / hyphal origin is x,y itself)
    ay: float = 0.0
    contract: float = 0.0        # 0..1 stalk contraction (Vorticella)

    @property
    def counted(self) -> bool:
        return self.state in (LIVE, DIVIDING, ENTERING)


class VisualPopulation:
    """Drawn units of one species inside one microscope field."""

    def __init__(self, spec: MorphSpec, width_um: float, height_um: float, seed: int = 0,
                 id_start: int = 0):
        self.spec = spec
        self.w, self.h = width_um, height_um
        self.rng = random.Random(seed)
        self.agents: list[Agent] = []
        self._next_id = id_start
        self.events = {"divisions": 0, "losses": 0, "grazed": 0, "entered": 0, "left": 0}
        self._mature_s = 2.5 * spec.division_s
        self._prev_target: float | None = None
        self._rate = 0.0                              # smoothed d ln(target) / d(real seconds)

    # ------------------------------------------------------------------ counting
    def cells(self) -> int:
        """Cells currently counted (live, dividing or entering; not those dying or being eaten)."""
        return sum(a.n - (1 if a.tail_fade > 0 else 0) for a in self.agents if a.counted)

    def committed(self) -> int:
        """Cells counted plus the cells that divisions already under way will add."""
        return self.cells() + sum(a.gain for a in self.agents if a.state == DIVIDING)

    def by_id(self, aid: int) -> Agent | None:
        for a in self.agents:
            if a.id == aid:
                return a
        return None

    # ------------------------------------------------------------------ creation
    def _new_id(self) -> int:
        self._next_id += 1
        return self._next_id

    def _make(self, x, y, heading, **kw) -> Agent:
        r = self.rng
        a = Agent(self._new_id(), x, y, heading, size=max(0.4, r.gauss(1.0, self.spec.size_cv)),
                  phase=r.random() * 10, variant=r.random(), timer=r.expovariate(1.0), **kw)
        a.ax, a.ay = x, y
        return a

    def seed(self, n_cells: float) -> None:
        """The first look at the sample: place the inoculum at rest (no animation)."""
        self.agents.clear()
        n = int(round(max(n_cells, 0)))
        r, s = self.rng, self.spec
        while n > 0:
            k = min(n, max(1, r.randint(1, max(1, s.max_chain))) if s.max_chain > 1 else 1)
            a = self._make(r.uniform(0, self.w), r.uniform(0, self.h), r.uniform(0, 2 * math.pi), n=k)
            a.grow = r.uniform(0.7, 1.0)
            self.agents.append(a)
            n -= k

    # ------------------------------------------------------------------ main step
    def step(self, target: float, dt_real: float, advancing: bool, motion_scale: float = 1.0,
             predators: list[Agent] | None = None) -> None:
        """Reconcile with `target` cells and move everything.

        Nothing new happens while simulation time stands still (the target is constant), but transitions
        already needed are finished, so after a jump of the time slider the view settles to the new
        state in about a second and then stays put."""
        if advancing and self._prev_target is not None and dt_real > 0:
            inst = (math.log(target + 1.0) - math.log(self._prev_target + 1.0)) / dt_real
            self._rate += (inst - self._rate) * min(1.0, dt_real * 4.0)
        elif not advancing:
            self._rate *= math.exp(-dt_real * 4.0)
        self._prev_target = target
        self._reconcile(target, predators or [])
        self._advance_transitions(dt_real, predators or [])
        self._move(dt_real * motion_scale, predators or [])
        self._separate(dt_real)

    # ------------------------------------------------------------------ reconciliation
    def _pressure_duration(self, base: float, gap: float, alive: int) -> float:
        """Transitions speed up when the model changes faster than one division per cell can show:
        a division must not take longer than the population's current doubling (or halving) time."""
        pressure = gap / max(alive, 1)
        dur = base / max(1.0, 1.5 * pressure)
        if abs(self._rate) > 1e-9:
            dur = min(dur, 0.6 * math.log(2) / abs(self._rate))
        return float(min(base, max(0.1, dur)))

    def _reconcile(self, target: float, predators: list[Agent]) -> None:
        s, r = self.spec, self.rng
        committed = self.committed()
        alive = self.cells()
        gap = target - committed
        if gap >= 0.75:                               # need more cells
            if alive == 0 and not any(a.state == DIVIDING for a in self.agents):
                self._enter()
                return
            dur = self._pressure_duration(s.division_s, gap, alive)
            self._mature_s = 2.5 * dur                  # fast growth also means daughters mature faster
            cands = [a for a in self.agents if a.state == LIVE and a.grow > 0.25]
            r.shuffle(cands)
            cands.sort(key=lambda a: -a.grow)           # mature cells divide first
            for a in self.agents:                     # speed up divisions already under way, too
                if a.state == DIVIDING and a.duration > dur:
                    a.duration = dur
            need = gap
            for a in cands:
                if need < 0.75:
                    break
                g = GAIN.get(s.division, 1)
                if s.division == "autospores":
                    g = int(min(3, max(1, round(need))))
                elif s.division in ("chain_fission", "packet_fission"):
                    g = int(min(a.n, max(1, math.ceil(need))))   # cells of a chain divide together
                a.state, a.progress, a.duration, a.gain = DIVIDING, 0.0, dur * r.uniform(0.85, 1.15), g
                need -= g
        else:
            self._mature_s = 2.5 * s.division_s
        if gap <= -0.75:                              # need fewer cells
            need = int(math.floor(-gap + 0.25))
            dur = self._pressure_duration(0.9, -gap, alive)
            for a in self.agents:
                if a.state in (DYING, GRAZED, LEAVING) and a.duration > dur:
                    a.duration = dur
            live = [a for a in self.agents if a.state == LIVE]
            r.shuffle(live)
            for a in self._order_for_loss(live, predators):
                if need <= 0:
                    break
                if a.n > 1 and a.n > need:            # one cell at the end of a chain lyses
                    if a.tail_fade == 0:
                        a.tail_fade = 1e-6
                        need -= 1
                    continue
                need -= a.n
                pred = self._nearest(a, predators) if predators else None
                reach = 0.25 * min(self.w, self.h)            # only prey near a mouth can be eaten
                if pred is not None and self._dist2(a, pred) <= reach ** 2:
                    a.state, a.prey_of = GRAZED, pred.id
                elif s.motility not in ("none", "sessile", "hyphal") and self._near_edge(a):
                    a.state = LEAVING
                else:
                    a.state = DYING
                a.progress, a.duration = 0.0, dur * r.uniform(0.85, 1.15)

    def _order_for_loss(self, live: list[Agent], predators: list[Agent]) -> list[Agent]:
        if predators:                                 # prey closest to a predator are eaten first
            return sorted(live, key=lambda a: self._dist2(a, self._nearest(a, predators)))
        return sorted(live, key=lambda a: a.grow)     # otherwise smaller/younger first

    @staticmethod
    def _dist2(a: Agent, b: Agent | None) -> float:
        return float("inf") if b is None else (a.x - b.x) ** 2 + (a.y - b.y) ** 2

    def _nearest(self, a: Agent, predators: list[Agent]) -> Agent | None:
        best, bd = None, float("inf")
        for p in predators:
            d = (a.x - p.x) ** 2 + (a.y - p.y) ** 2
            if d < bd:
                best, bd = p, d
        return best

    def _near_edge(self, a: Agent) -> bool:
        m = 0.12
        return a.x < self.w * m or a.x > self.w * (1 - m) or a.y < self.h * m or a.y > self.h * (1 - m)

    def _enter(self) -> None:
        """No cell in view but the model has some: one drifts or swims in from the edge."""
        r, s = self.rng, self.spec
        side = r.randrange(4)
        L = s.length_um
        if side == 0:
            x, y, hd = -L * 0.6, r.uniform(0.1, 0.9) * self.h, 0.0
        elif side == 1:
            x, y, hd = self.w + L * 0.6, r.uniform(0.1, 0.9) * self.h, math.pi
        elif side == 2:
            x, y, hd = r.uniform(0.1, 0.9) * self.w, -L * 0.6, math.pi / 2
        else:
            x, y, hd = r.uniform(0.1, 0.9) * self.w, self.h + L * 0.6, -math.pi / 2
        hd += r.uniform(-0.4, 0.4)
        if s.motility == "hyphal":                    # a hypha grows in from the edge, it does not move
            x, y = min(max(x, 0.0), self.w), min(max(y, 0.0), self.h)
        a = self._make(x, y, hd)
        a.state, a.progress, a.duration = ENTERING, 0.0, 1.6
        if s.motility == "hyphal":
            a.grow = 0.05
        self.agents.append(a)
        self.events["entered"] += 1

    # ------------------------------------------------------------------ transitions
    def _advance_transitions(self, dt: float, predators: list[Agent]) -> None:
        s = self.spec
        born: list[Agent] = []
        gone: set[int] = set()
        for a in self.agents:
            if a.grow < 1.0:                          # newborns grow (simulation-driven, so only while advancing)
                a.grow = min(1.0, a.grow + dt / self._mature_s)
            if a.tail_fade > 0:
                a.tail_fade += dt / 0.8
                if a.tail_fade >= 1:
                    a.tail_fade, a.n = 0.0, max(1, a.n - 1)
                    self.events["losses"] += 1
            if a.state == LIVE:
                continue
            a.progress += dt / max(a.duration, 1e-6)
            if a.state == ENTERING:
                inside = 0 <= a.x <= self.w and 0 <= a.y <= self.h
                if a.progress >= 1 and inside:
                    a.state = LIVE
                continue
            if a.progress < 1:
                continue
            if a.state == DIVIDING:
                born.extend(self._divide(a))
                self.events["divisions"] += 1
            else:                                     # DYING / GRAZED / LEAVING complete
                if a.state == LEAVING and 0 <= a.x <= self.w and 0 <= a.y <= self.h and a.progress < 4:
                    continue                          # keep swimming out
                gone.add(a.id)
                key = {DYING: "losses", GRAZED: "grazed", LEAVING: "left"}[a.state]
                self.events[key] += 1
        if gone:
            self.agents = [a for a in self.agents if a.id not in gone]
        self.agents.extend(born)

    def _divide(self, a: Agent) -> list[Agent]:
        """Complete a division. The mother keeps its id (identity persists); daughters get new ids."""
        s, r = self.spec, self.rng
        a.state, a.progress = LIVE, 0.0
        L = s.length_um * a.size
        W = s.width_um * a.size
        ux, uy = math.cos(a.heading), math.sin(a.heading)
        px, py = -uy, ux
        out: list[Agent] = []

        def child(x, y, hd, grow=1.0, n=1, size=None):
            c = self._make(x, y, hd, n=n, parent=a.id)
            c.grow = grow
            if size is not None:
                c.size = size
            c.vx, c.vy = a.vx, a.vy
            if s.motility in ("none",):               # non-motile daughters drift apart (mixing in the sample)
                ang = math.atan2(y - a.y, x - a.x) if (x, y) != (a.x, a.y) else r.uniform(0, 2 * math.pi)
                v = max(s.length_um * 1.5, self.w * 0.03) * r.uniform(0.7, 1.5)
                c.vx, c.vy = math.cos(ang) * v, math.sin(ang) * v
                a.vx, a.vy = a.vx - c.vx * 0.5, a.vy - c.vy * 0.5
            out.append(c)
            return c

        d = s.division
        if d in ("chain_fission", "packet_fission"):
            a.n += a.gain
            mx = max(s.max_chain, 1)
            cell = s.length_um * a.size * 0.95 * (0.55 + 0.45 * a.grow)     # centre spacing as drawn
            while a.n > mx:                           # the chain breaks where it is: no drawn cell moves
                total = a.n
                k = max(1, total // 2) if total <= 2 * mx else mx
                a.n = total - k
                cx, cy = a.x, a.y
                a.x, a.y = cx - ux * cell * k / 2, cy - uy * cell * k / 2
                child(cx + ux * cell * (total - k) / 2, cy + uy * cell * (total - k) / 2,
                      a.heading + r.uniform(-0.1, 0.1), n=k)
        elif d in ("binary_fission", "transverse_fission"):
            off = L * 0.27
            mx, my = a.x, a.y
            a.x, a.y = mx - ux * off, my - uy * off
            child(mx + ux * off, my + uy * off, a.heading + r.uniform(-0.15, 0.15), size=a.size)
            a.heading += r.uniform(-0.15, 0.15)
        elif d in ("longitudinal_fission", "diatom_valve", "coenobium"):
            off = W * 0.55
            mx, my = a.x, a.y
            a.x, a.y = mx - px * off, my - py * off
            size = a.size * (0.97 if d == "diatom_valve" else 1.0)   # MacDonald–Pfitzer size reduction
            child(mx + px * off, my + py * off, a.heading + r.uniform(-0.1, 0.1), size=size)
        elif d == "budding":
            off = L * 0.5 + L * 0.33
            ang = a.heading + a.variant * 0.6 - 0.3
            child(a.x + math.cos(ang) * off, a.y + math.sin(ang) * off, ang, grow=0.6)
        elif d == "autospores":
            k = a.gain + 1
            rr = L * 0.22
            base = r.uniform(0, 2 * math.pi)
            mx, my = a.x, a.y
            for j in range(k):
                ang = base + 2 * math.pi * j / k
                x, y = mx + math.cos(ang) * rr, my + math.sin(ang) * rr
                if j == 0:
                    a.x, a.y, a.grow = x, y, 0.5
                else:
                    child(x, y, ang, grow=0.5)
        elif d == "amoeboid_fission":
            off = L * 0.3
            mx, my = a.x, a.y
            a.x, a.y = mx - ux * off, my - uy * off
            child(mx + ux * off, my + uy * off, a.heading + math.pi + r.uniform(-0.5, 0.5))
        elif d == "parthenogenesis":
            off = L * 0.65
            child(a.x - ux * off, a.y - uy * off, a.heading + r.uniform(-1.0, 1.0), grow=0.45)
        elif d == "hyphal_extension":
            tipx, tipy = a.x + ux * L * a.grow, a.y + uy * L * a.grow
            side = 1 if r.random() < 0.5 else -1
            c = child(tipx, tipy, a.heading + side * r.uniform(0.45, 0.9), grow=0.05)
            c.ax, c.ay = tipx, tipy
        else:
            child(a.x + ux * L * 0.5, a.y + uy * L * 0.5, a.heading)
        a.gain = 1
        return out

    # ------------------------------------------------------------------ movement
    def _move(self, dt: float, predators: list[Agent]) -> None:
        if dt <= 0:
            return
        s, r = self.spec, self.rng
        mot = s.motility
        for a in self.agents:
            a.phase += dt
            if a.state == GRAZED:
                p = next((q for q in predators if q.id == a.prey_of), None)
                if p is not None:                     # drawn into the predator's mouth
                    k = min(1.0, dt * 3.0)
                    a.x += (p.x - a.x) * k
                    a.y += (p.y - a.y) * k
                continue
            if a.state == DYING:
                continue                              # lysing cells stop moving
            if a.state == DIVIDING and mot in ("none", "sessile", "hyphal"):
                continue
            speed = s.speed_um_s * (0.4 + 0.6 * a.grow)
            if a.state == ENTERING and mot == "hyphal":
                continue
            if a.state == ENTERING:
                v = max(speed, s.length_um * 0.5 + 2.0)
                a.vx, a.vy = math.cos(a.heading) * v, math.sin(a.heading) * v
            elif a.state == LEAVING:
                cx, cy = self.w / 2, self.h / 2
                ang = math.atan2(a.y - cy, a.x - cx)
                a.heading += _angdiff(ang, a.heading) * min(1.0, dt * 2)
                v = max(speed, 6.0)
                a.vx, a.vy = math.cos(a.heading) * v, math.sin(a.heading) * v
            elif mot == "none":
                self._brownian(a, dt)
            elif mot == "run_tumble":
                self._run_tumble(a, dt, speed, reverse=False)
            elif mot == "run_reverse":
                self._run_tumble(a, dt, speed, reverse=True)
            elif mot == "slow_swim":
                a.heading += r.gauss(0, 1.2) * math.sqrt(dt)
                self._towards(a, speed, dt, 2.0)
            elif mot == "ciliary":
                a.heading += (0.9 + 0.4 * a.variant) * dt * (1 if a.variant > 0.5 else -1) \
                    + r.gauss(0, 0.5) * math.sqrt(dt)
                self._towards(a, speed, dt, 4.0)
            elif mot == "flagellar":
                a.heading += 1.2 * math.sin(a.phase * 4.0) * dt + r.gauss(0, 0.4) * math.sqrt(dt)
                self._towards(a, speed, dt, 3.0)
            elif mot == "amoeboid":
                a.heading += r.gauss(0, 0.15) * math.sqrt(dt)
                self._towards(a, speed * (0.6 + 0.4 * math.sin(a.phase * 0.7)), dt, 0.5)
            elif mot == "gliding":
                a.timer -= dt
                if a.timer <= 0:
                    a.timer = r.uniform(8, 20)
                    a.heading += math.pi
                self._towards(a, speed, dt, 1.0)
            elif mot == "corona":
                a.heading += r.gauss(0, 0.6) * math.sqrt(dt)
                self._towards(a, speed, dt, 3.0)
            elif mot == "creeping":
                a.timer -= dt
                if a.timer <= 0:
                    a.timer = r.uniform(2, 6)
                    a.tumbling = not a.tumbling
                    a.heading += r.uniform(-1.2, 1.2)
                self._towards(a, 0.0 if a.tumbling else speed, dt, 2.0)
            elif mot == "sessile":
                a.timer -= dt
                if a.timer <= 0 and a.contract <= 0:
                    a.timer, a.contract = r.uniform(8, 25), 1.0
                a.contract = max(0.0, a.contract - dt * 1.5)
                a.vx = a.vy = 0.0
            else:                                     # hyphal: no movement
                a.vx = a.vy = 0.0
            a.x += a.vx * dt
            a.y += a.vy * dt
            if a.state in (LIVE, DIVIDING):
                self._walls(a)

    def _separate(self, dt: float) -> None:
        """Cells are solid: overlapping neighbours are pushed apart over a fraction of a second.
        This is what spreads daughter cells and autospores after a division."""
        s = self.spec
        if s.motility == "hyphal" or dt <= 0:
            return
        movers = [a for a in self.agents if a.state in (LIVE, DIVIDING)]
        if len(movers) < 2:
            return
        xy = np.array([(a.x, a.y) for a in movers])
        base = 0.5 * (s.length_um * 0.6 + s.width_um * 0.4)
        rad = np.array([base * a.size * (0.55 + 0.45 * a.grow) * math.sqrt(a.n) for a in movers])
        d = xy[:, None, :] - xy[None, :, :]
        dist = np.sqrt((d ** 2).sum(-1)) + np.eye(len(movers))
        overlap = rad[:, None] + rad[None, :] - dist
        np.fill_diagonal(overlap, 0.0)
        overlap = np.clip(overlap, 0.0, None)
        if not overlap.any():
            return
        push = (d / dist[..., None] * overlap[..., None]).sum(1) * 0.5
        k = min(1.0, dt * 3.0)
        for a, (px, py) in zip(movers, push):
            if px or py:
                a.x += px * k
                a.y += py * k
                self._walls(a)

    def _towards(self, a: Agent, speed: float, dt: float, inertia: float) -> None:
        """Velocity relaxes towards the heading direction (no instantaneous jumps)."""
        k = min(1.0, dt * inertia)
        tx, ty = math.cos(a.heading) * speed, math.sin(a.heading) * speed
        a.vx += (tx - a.vx) * k
        a.vy += (ty - a.vy) * k

    def _brownian(self, a: Agent, dt: float) -> None:
        r = self.rng
        radius = max(self.spec.width_um * a.size / 2, 0.2)
        diff = 0.22 / radius                          # Stokes–Einstein in water at ≈25 °C, µm²/s
        sd = math.sqrt(2 * diff * dt)
        a.x += r.gauss(0, sd)
        a.y += r.gauss(0, sd)
        a.heading += r.gauss(0, math.sqrt(2 * 0.1 / radius ** 3 * dt)) if radius < 5 else 0.0
        decay = math.exp(-dt / 3.0)                   # drift after a division fades over ≈3 s
        a.vx *= decay
        a.vy *= decay

    def _run_tumble(self, a: Agent, dt: float, speed: float, reverse: bool) -> None:
        r = self.rng
        a.timer -= dt
        if a.timer <= 0:
            if a.tumbling or reverse:
                a.tumbling = False
                a.timer = r.expovariate(1 / (1.5 if reverse else 1.0))       # run ≈1 s (Berg 2004)
                if reverse:
                    a.heading += math.pi + r.gauss(0, 0.35)
            else:
                a.tumbling = True
                a.timer = r.expovariate(1 / 0.12)                            # tumble ≈0.1 s
        if a.tumbling:
            a.heading += r.gauss(0, 6.0) * math.sqrt(dt)                     # mean reorientation ≈70°
            self._towards(a, 0.0, dt, 12.0)
        else:
            a.heading += r.gauss(0, 0.3) * math.sqrt(dt)                     # rotational diffusion
            self._towards(a, speed, dt, 10.0)

    def _walls(self, a: Agent) -> None:
        """Reflecting coverslip edges: a cell turns back instead of teleporting to the other side."""
        if a.x < 0:
            a.x, a.vx = -a.x, abs(a.vx)
            a.heading = math.pi - a.heading
        elif a.x > self.w:
            a.x, a.vx = 2 * self.w - a.x, -abs(a.vx)
            a.heading = math.pi - a.heading
        if a.y < 0:
            a.y, a.vy = -a.y, abs(a.vy)
            a.heading = -a.heading
        elif a.y > self.h:
            a.y, a.vy = 2 * self.h - a.y, -abs(a.vy)
            a.heading = -a.heading
        a.x = min(max(a.x, 0.0), self.w)
        a.y = min(max(a.y, 0.0), self.h)


def _angdiff(a: float, b: float) -> float:
    return (a - b + math.pi) % (2 * math.pi) - math.pi
