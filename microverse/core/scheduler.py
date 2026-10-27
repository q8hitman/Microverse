"""Runs a Model for a RunConfig and returns a Trajectory.

Deterministic: SciPy solve_ivp. Stochastic: tau-leaping with Poisson increments.
"""
from __future__ import annotations

import numpy as np
from scipy.integrate import solve_ivp

from .model import Model
from .trajectory import RunConfig, Trajectory


def make_config(model: Model, *, t_end: float = 200.0, dt_out: float = 0.1,
                mode: str = "deterministic", seed: int = 0, volume_ml: float = 1.0,
                initial_state=None, **param_overrides: float) -> RunConfig:
    params = model.default_parameters().updated(**param_overrides).values()
    y0 = model.default_initial_state() if initial_state is None else np.asarray(initial_state, float)
    return RunConfig(model.id, model.version, params, tuple(float(v) for v in y0),
                     float(t_end), float(dt_out), mode, int(seed), float(volume_ml))


def run(model: Model, config: RunConfig) -> Trajectory:
    if config.model_id != model.id:
        raise ValueError(f"config is for {config.model_id}, not {model.id}")
    if config.mode == "deterministic":
        return _run_deterministic(model, config)
    if config.mode == "stochastic":
        return _run_tau_leap(model, config)
    raise ValueError(f"unknown mode {config.mode!r}")


def _run_deterministic(model: Model, cfg: RunConfig) -> Trajectory:
    p = cfg.parameters
    t_eval = np.arange(0.0, cfg.t_end + 1e-12, cfg.dt_out)

    def f(t, y):
        return model.rhs(t, np.maximum(y, 0.0), p)

    sol = solve_ivp(f, (0.0, cfg.t_end), np.array(cfg.initial_state), method=cfg.solver,
                    t_eval=t_eval, rtol=1e-8, atol=1e-10)
    if not sol.success:
        raise RuntimeError(f"solver failed: {sol.message}")
    y = np.maximum(sol.y.T, 0.0)
    return Trajectory(cfg, sol.t, y, tuple(s.symbol for s in model.state_vars))


def _run_tau_leap(model: Model, cfg: RunConfig) -> Trajectory:
    """Fixed-step tau-leaping in individual units.

    The model's `reactions()` define state changes in model units per event;
    `propensities()` returns events per day for the given culture volume.
    """
    rng = np.random.default_rng(cfg.seed)
    p = dict(cfg.parameters, _volume_ml=cfg.volume_ml)
    reactions = model.reactions(p)
    if not reactions:
        raise ValueError(f"model {model.id} has no stochastic formulation")
    change = np.array([r.change for r in reactions])          # (n_reactions, n_vars)
    tau = min(cfg.dt_out, 0.01)
    steps_per_out = max(1, int(round(cfg.dt_out / tau)))
    n_out = int(round(cfg.t_end / cfg.dt_out)) + 1
    y = np.array(cfg.initial_state, float)
    quanta = model.state_quanta(p)
    snap = np.zeros_like(y) if quanta is None else 0.5 * np.asarray(quanta)
    out = np.empty((n_out, len(y)))
    out[0] = y
    events: list[str] = []
    alive = y > 0
    for k in range(1, n_out):
        for _ in range(steps_per_out):
            a = np.maximum(model.propensities(y, p), 0.0)
            fires = rng.poisson(a * tau)
            y = np.maximum(y + fires @ change, 0.0)
            y[y < snap] = 0.0              # less than half an individual left: extinct
        out[k] = y
        now_alive = y > 0
        for i, (was, now) in enumerate(zip(alive, now_alive)):
            if was and not now:
                events.append(f"t={k * cfg.dt_out:.1f} d: {model.state_vars[i].symbol} reached zero (extinction in this replicate)")
        alive = now_alive
    t = np.arange(n_out) * cfg.dt_out
    return Trajectory(cfg, t, out, tuple(s.symbol for s in model.state_vars), events)
