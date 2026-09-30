"""Constrained design search kept separate from the physics model."""

from dataclasses import dataclass, replace
import math
import pandas as pd
from .model import ArrayDesign, Site, simulate_design
from .weather import simulate_weather_design
from .finance import FinanceAssumptions, calculate_project_finance


@dataclass(frozen=True)
class DesignConstraints:
    """Project constraints and economic assumptions for a design search."""

    max_land_area_m2: float = math.inf
    max_budget_usd: float = math.inf
    electricity_price_usd_per_kwh: float = 0.10
    module_cost_usd: float = 250.0
    rack_cost_usd_per_m2: float = 120.0
    inverter_cost_usd_per_kw: float = 110.0
    modules_per_row: int = 10
    objective: str = "energy"
    annual_om_fraction: float = 0.015
    degradation_rate: float = 0.005
    analysis_years: int = 25
    discount_rate: float = 0.08
    incentive_usd: float = 0.0

    def __post_init__(self) -> None:
        if self.max_land_area_m2 <= 0 or self.max_budget_usd <= 0:
            raise ValueError("land area and budget limits must be positive")
        if self.electricity_price_usd_per_kwh < 0:
            raise ValueError("electricity price cannot be negative")
        if self.objective not in {"energy", "value", "npv"}:
            raise ValueError("objective must be 'energy', 'value', or 'npv'")
        if self.modules_per_row < 1:
            raise ValueError("modules_per_row must be at least 1")
        FinanceAssumptions(
            electricity_price_usd_per_kwh=self.electricity_price_usd_per_kwh,
            annual_om_fraction=self.annual_om_fraction,
            degradation_rate=self.degradation_rate,
            analysis_years=self.analysis_years,
            discount_rate=self.discount_rate,
            incentive_usd=self.incentive_usd,
        )


def estimate_design_economics(design: ArrayDesign, result: dict[str, float], constraints: DesignConstraints) -> dict[str, float]:
    """Return transparent land, cost, revenue, and objective values."""
    if constraints.modules_per_row < 1:
        raise ValueError("modules_per_row must be at least 1")
    module_width_m = 1.1
    module_length_m = design.module_area_m2 / module_width_m
    rows = math.ceil(design.modules / constraints.modules_per_row)
    row_length_m = min(design.modules, constraints.modules_per_row) * module_length_m
    land_area_m2 = rows * design.row_spacing_m * row_length_m
    capital_cost_usd = (
        design.modules * constraints.module_cost_usd
        + design.module_area_m2 * design.modules * constraints.rack_cost_usd_per_m2
        + result["capacity_kw"] * constraints.inverter_cost_usd_per_kw
    )
    annual_revenue_usd = result["annual_energy_kwh"] * constraints.electricity_price_usd_per_kwh
    finance = calculate_project_finance(
        result["annual_energy_kwh"],
        capital_cost_usd,
        FinanceAssumptions(
            electricity_price_usd_per_kwh=constraints.electricity_price_usd_per_kwh,
            annual_om_fraction=constraints.annual_om_fraction,
            degradation_rate=constraints.degradation_rate,
            analysis_years=constraints.analysis_years,
            discount_rate=constraints.discount_rate,
            incentive_usd=constraints.incentive_usd,
        ),
    )
    if constraints.objective == "energy":
        objective_value = result["annual_energy_kwh"]
    elif constraints.objective == "value":
        objective_value = annual_revenue_usd - 0.01 * capital_cost_usd
    elif constraints.objective == "npv":
        objective_value = finance["npv_usd"]
    else:
        raise ValueError("objective must be 'energy' or 'value'")
    return {
        "land_area_m2": float(land_area_m2),
        "capital_cost_usd": float(capital_cost_usd),
        "annual_revenue_usd": float(annual_revenue_usd),
        "objective_value": float(objective_value),
        **finance,
    }


def pareto_frontier(candidates: list[dict]) -> list[dict]:
    """Return feasible designs not dominated on energy, land, and cost.

    Energy is maximized; land area and capital cost are minimized. A design is
    dominated when another feasible design is at least as good on every metric
    and strictly better on one or more metrics.
    """
    feasible = [candidate for candidate in candidates if candidate["feasible"]]
    frontier = []
    for candidate in feasible:
        candidate_economics = candidate["economics"]
        dominated = any(
            other is not candidate
            and other["result"]["annual_energy_kwh"] >= candidate["result"]["annual_energy_kwh"]
            and other["economics"]["land_area_m2"] <= candidate_economics["land_area_m2"]
            and other["economics"]["capital_cost_usd"] <= candidate_economics["capital_cost_usd"]
            and (
                other["result"]["annual_energy_kwh"] > candidate["result"]["annual_energy_kwh"]
                or other["economics"]["land_area_m2"] < candidate_economics["land_area_m2"]
                or other["economics"]["capital_cost_usd"] < candidate_economics["capital_cost_usd"]
            )
            for other in feasible
        )
        if not dominated:
            frontier.append(candidate)
    return sorted(frontier, key=lambda item: item["result"]["annual_energy_kwh"], reverse=True)


def optimize_fixed_tilt(
    site: Site,
    baseline: ArrayDesign | None = None,
    constraints: DesignConstraints | None = None,
    weather: pd.DataFrame | None = None,
) -> dict:
    constraints = constraints or DesignConstraints()
    baseline = baseline or ArrayDesign(tilt_deg=max(0.0, site.latitude_deg), row_spacing_m=4.0)
    simulate = simulate_weather_design if weather is not None else simulate_design
    baseline_result = simulate(site, baseline, weather) if weather is not None else simulate(site, baseline)
    baseline_economics = estimate_design_economics(baseline, baseline_result, constraints)
    baseline_feasible = baseline_economics["land_area_m2"] <= constraints.max_land_area_m2 and baseline_economics["capital_cost_usd"] <= constraints.max_budget_usd
    candidates = []
    tilt_step = 10 if weather is not None else 5
    azimuth_values = range(170, 191, 10) if weather is not None else range(150, 211, 10)
    spacing_values = (2.0, 4.0, 6.0, 8.0) if weather is not None else (2.0, 3.0, 4.0, 5.0, 6.0, 8.0)
    for tilt in range(0, 91, tilt_step):
        for azimuth in azimuth_values:
            for spacing in spacing_values:
                for modules in (50, 100, 150, 200):
                    design = replace(baseline, tilt_deg=float(tilt), azimuth_deg=float(azimuth), row_spacing_m=spacing, modules=modules)
                    result = simulate(site, design, weather) if weather is not None else simulate(site, design)
                    economics = estimate_design_economics(design, result, constraints)
                    feasible = economics["land_area_m2"] <= constraints.max_land_area_m2 and economics["capital_cost_usd"] <= constraints.max_budget_usd
                    candidates.append({"design": design, "result": result, "economics": economics, "feasible": feasible})
    feasible_candidates = [item for item in candidates if item["feasible"]]
    if not feasible_candidates:
        raise ValueError("no feasible design satisfies the land and budget constraints")
    best = max(feasible_candidates, key=lambda item: item["economics"]["objective_value"])
    frontier = pareto_frontier(candidates)
    return {"baseline": {"design": baseline, "result": baseline_result, "economics": baseline_economics, "feasible": baseline_feasible}, "best": best, "candidates": candidates, "feasible_count": len(feasible_candidates), "pareto_frontier": frontier}
