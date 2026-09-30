"""Thermomechanical bracket problem coupling FDM temperature to strength."""

from dataclasses import dataclass
from typing import Mapping

from .bracket import BracketConstraints, BracketDesign, BracketProblem
from .engine import optimize_problem
from .thermal import solve_steady_1d_fin


@dataclass(frozen=True)
class ThermoMechanicalConstraints:
    mechanical: BracketConstraints = BracketConstraints()
    conductivity_w_mk: float = 205.0
    convection_w_m2k: float = 12.0
    ambient_temperature_c: float = 25.0
    base_temperature_c: float = 80.0
    heat_generation_w_m3: float = 100_000.0
    strength_temperature_coefficient_per_c: float = 0.001
    thermal_nodes: int = 21

    def __post_init__(self) -> None:
        if self.conductivity_w_mk <= 0 or self.convection_w_m2k <= 0:
            raise ValueError("thermal conductivity and convection must be positive")
        if self.heat_generation_w_m3 < 0:
            raise ValueError("heat generation cannot be negative")
        if self.strength_temperature_coefficient_per_c < 0:
            raise ValueError("strength temperature coefficient cannot be negative")
        if self.thermal_nodes < 3:
            raise ValueError("thermal_nodes must be at least 3")


class ThermoMechanicalBracketProblem:
    """Bracket problem with temperature-dependent allowable stress."""

    def __init__(self, constraints: ThermoMechanicalConstraints | None = None) -> None:
        self.constraints = constraints or ThermoMechanicalConstraints()
        self.mechanical_problem = BracketProblem(self.constraints.mechanical)

    def candidate_designs(self) -> list[BracketDesign]:
        return self.mechanical_problem.candidate_designs()

    def evaluate(self, design: BracketDesign) -> Mapping[str, float]:
        mechanical = self.mechanical_problem.evaluate(design)
        thermal = solve_steady_1d_fin(
            length_m=design.length_m,
            area_m2=design.width_m * design.thickness_m,
            perimeter_m=2.0 * (design.width_m + design.thickness_m),
            conductivity_w_mk=self.constraints.conductivity_w_mk,
            convection_w_m2k=self.constraints.convection_w_m2k,
            ambient_temperature_c=self.constraints.ambient_temperature_c,
            base_temperature_c=self.constraints.base_temperature_c,
            heat_generation_w_m3=self.constraints.heat_generation_w_m3,
            nodes=self.constraints.thermal_nodes,
        )
        peak_temperature_c = float(thermal.temperature_c.max())
        temperature_delta_c = max(0.0, peak_temperature_c - self.constraints.ambient_temperature_c)
        strength_factor = max(0.5, 1.0 - self.constraints.strength_temperature_coefficient_per_c * temperature_delta_c)
        effective_yield_strength_mpa = self.constraints.mechanical.yield_strength_pa * strength_factor / 1_000_000.0
        allowable_stress_mpa = effective_yield_strength_mpa / self.constraints.mechanical.safety_factor
        return {
            **mechanical,
            "peak_temperature_c": peak_temperature_c,
            "effective_yield_strength_mpa": effective_yield_strength_mpa,
            "allowable_stress_mpa": allowable_stress_mpa,
            "thermal_strength_factor": strength_factor,
        }

    def is_feasible(self, design: BracketDesign, metrics: Mapping[str, float]) -> bool:
        return design.length_m > 0 and metrics["stress_mpa"] <= metrics["allowable_stress_mpa"] and metrics["deflection_mm"] <= self.constraints.mechanical.max_deflection_mm

    def score(self, design: BracketDesign, metrics: Mapping[str, float]) -> float:
        return -metrics["mass_kg"] if design.width_m > 0 else float("-inf")


def optimize_thermomechanical_bracket(constraints: ThermoMechanicalConstraints | None = None) -> dict[str, object]:
    """Optimize bracket mass under mechanical and thermal-strength limits."""
    return optimize_problem(ThermoMechanicalBracketProblem(constraints))
