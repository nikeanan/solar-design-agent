"""Preliminary cantilever-bracket sizing problem for the generic engine."""

from dataclasses import dataclass
from itertools import product
from typing import Mapping

from .engine import optimize_problem


@dataclass(frozen=True)
class BracketDesign:
    width_m: float
    thickness_m: float
    length_m: float

    def __post_init__(self) -> None:
        if self.width_m <= 0 or self.thickness_m <= 0 or self.length_m <= 0:
            raise ValueError("bracket dimensions must be positive")


@dataclass(frozen=True)
class BracketConstraints:
    load_n: float = 1000.0
    max_deflection_mm: float = 2.0
    yield_strength_pa: float = 150_000_000.0
    youngs_modulus_pa: float = 69_000_000_000.0
    density_kg_m3: float = 2700.0
    safety_factor: float = 2.0

    def __post_init__(self) -> None:
        if self.load_n <= 0 or self.max_deflection_mm <= 0:
            raise ValueError("load and maximum deflection must be positive")
        if self.yield_strength_pa <= 0 or self.youngs_modulus_pa <= 0 or self.density_kg_m3 <= 0:
            raise ValueError("material properties must be positive")
        if self.safety_factor < 1:
            raise ValueError("safety_factor must be at least 1")


class BracketProblem:
    """Finite rectangular-bracket design space with cantilever beam equations."""

    def __init__(self, constraints: BracketConstraints | None = None) -> None:
        self.constraints = constraints or BracketConstraints()

    def candidate_designs(self) -> list[BracketDesign]:
        return [
            BracketDesign(width_m=width, thickness_m=thickness, length_m=length)
            for width, thickness, length in product(
                (0.03, 0.04, 0.05, 0.06, 0.08),
                (0.003, 0.004, 0.005, 0.006, 0.008, 0.010, 0.012, 0.015, 0.020),
                (0.10, 0.15, 0.20),
            )
        ]

    def evaluate(self, design: BracketDesign) -> Mapping[str, float]:
        cross_section_inertia_m4 = design.width_m * design.thickness_m**3 / 12.0
        moment_nm = self.constraints.load_n * design.length_m
        stress_pa = 6.0 * moment_nm / (design.width_m * design.thickness_m**2)
        deflection_m = self.constraints.load_n * design.length_m**3 / (3.0 * self.constraints.youngs_modulus_pa * cross_section_inertia_m4)
        mass_kg = design.width_m * design.thickness_m * design.length_m * self.constraints.density_kg_m3
        allowable_stress_pa = self.constraints.yield_strength_pa / self.constraints.safety_factor
        return {
            "stress_mpa": stress_pa / 1_000_000.0,
            "deflection_mm": deflection_m * 1000.0,
            "mass_kg": mass_kg,
            "safety_factor": self.constraints.yield_strength_pa / stress_pa,
            "allowable_stress_mpa": allowable_stress_pa / 1_000_000.0,
        }

    def is_feasible(self, design: BracketDesign, metrics: Mapping[str, float]) -> bool:
        return design.width_m > 0 and metrics["stress_mpa"] <= metrics["allowable_stress_mpa"] and metrics["deflection_mm"] <= self.constraints.max_deflection_mm

    def score(self, design: BracketDesign, metrics: Mapping[str, float]) -> float:
        return -metrics["mass_kg"] if design.width_m > 0 else float("-inf")


def optimize_bracket(constraints: BracketConstraints | None = None) -> dict[str, object]:
    """Optimize preliminary bracket mass subject to strength and deflection."""
    problem = BracketProblem(constraints)
    return optimize_problem(problem)
