"""The Model contract: pure computation, no UI, no I/O."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np

from .parameters import ParameterSet


@dataclass(frozen=True)
class StateVar:
    symbol: str
    name: str
    unit: str
    description: str = ""


@dataclass(frozen=True)
class Reaction:
    """One stochastic event channel: a propensity and the state change it causes."""

    name: str
    change: tuple[float, ...]          # change of each state variable, in model units
    description: str = ""


@dataclass(frozen=True)
class FluxTerm:
    """A named term of a right-hand side, used by the explanation engine."""

    target: str        # state variable it acts on
    name: str
    value: float       # signed contribution to d(target)/dt
    formula: str


class Model(ABC):
    id: str
    version: str
    title: str
    state_vars: tuple[StateVar, ...]

    @abstractmethod
    def default_parameters(self) -> ParameterSet: ...

    @abstractmethod
    def default_initial_state(self) -> np.ndarray: ...

    @abstractmethod
    def rhs(self, t: float, y: np.ndarray, p: dict[str, float]) -> np.ndarray: ...

    @abstractmethod
    def flux_terms(self, y: np.ndarray, p: dict[str, float]) -> list[FluxTerm]:
        """Decompose rhs into named terms; must sum to rhs per variable."""

    # Optional stochastic formulation. `p` includes `_volume_ml`, because the size
    # of one individual in concentration units depends on the culture volume.
    def reactions(self, p: dict[str, float]) -> tuple[Reaction, ...]:
        return ()

    def propensities(self, y: np.ndarray, p: dict[str, float]) -> np.ndarray:
        raise NotImplementedError

    def state_quanta(self, p: dict[str, float]) -> np.ndarray | None:
        """Size of one individual per state variable; values below half a quantum mean zero."""
        return None

    def jacobian(self, y: np.ndarray, p: dict[str, float]) -> np.ndarray:
        """Finite-difference Jacobian; models may override with an analytic one."""
        n = len(y)
        J = np.zeros((n, n))
        f0 = self.rhs(0.0, y, p)
        for j in range(n):
            h = 1e-6 * max(1.0, abs(y[j]))
            yp = y.copy()
            yp[j] += h
            J[:, j] = (self.rhs(0.0, yp, p) - f0) / h
        return J

    def index(self, symbol: str) -> int:
        for i, s in enumerate(self.state_vars):
            if s.symbol == symbol:
                return i
        raise KeyError(symbol)
