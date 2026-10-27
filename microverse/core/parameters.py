"""Parameters with units, bounds and provenance.

Every number that enters a model carries where it came from and how much it
can be trusted. The UI and reports read these fields directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum


class Evidence(str, Enum):
    MEASURED = "measured"                    # direct measurement, cited
    LITERATURE_ESTIMATE = "literature_estimate"
    FITTED = "fitted"                        # calibrated to a named dataset
    DERIVED = "derived"                      # computed from other parameters
    ASSUMED = "assumed"                      # exploratory, flagged in UI
    CONTROL = "control"                      # set by the experimenter (e.g. dilution rate)


@dataclass(frozen=True)
class Source:
    key: str
    citation: str
    doi: str = ""
    url: str = ""
    licence: str = ""
    note: str = ""


@dataclass(frozen=True)
class Parameter:
    symbol: str
    name: str
    value: float
    unit: str
    lower: float
    upper: float
    evidence: Evidence
    source: Source | None = None
    description: str = ""
    verified_against_source: bool = False

    def with_value(self, value: float) -> "Parameter":
        if not (self.lower <= value <= self.upper):
            raise ValueError(
                f"{self.symbol}={value} outside allowed range [{self.lower}, {self.upper}] {self.unit}"
            )
        return replace(self, value=float(value))


@dataclass
class ParameterSet:
    """Ordered collection of parameters; values can be overridden, metadata cannot."""

    params: dict[str, Parameter] = field(default_factory=dict)

    def __getitem__(self, symbol: str) -> float:
        return self.params[symbol].value

    def values(self) -> dict[str, float]:
        return {k: p.value for k, p in self.params.items()}

    def updated(self, **overrides: float) -> "ParameterSet":
        new = dict(self.params)
        for k, v in overrides.items():
            if k not in new:
                raise KeyError(f"unknown parameter {k!r}")
            new[k] = new[k].with_value(v)
        return ParameterSet(new)
