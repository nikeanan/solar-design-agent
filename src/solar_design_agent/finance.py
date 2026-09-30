"""Transparent project-finance calculations for solar design decisions."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FinanceAssumptions:
    electricity_price_usd_per_kwh: float = 0.10
    annual_om_fraction: float = 0.015
    degradation_rate: float = 0.005
    analysis_years: int = 25
    discount_rate: float = 0.08
    incentive_usd: float = 0.0

    def __post_init__(self) -> None:
        if self.electricity_price_usd_per_kwh < 0:
            raise ValueError("electricity price cannot be negative")
        if self.annual_om_fraction < 0 or self.degradation_rate < 0:
            raise ValueError("O&M and degradation rates cannot be negative")
        if self.analysis_years < 1:
            raise ValueError("analysis_years must be at least 1")
        if self.discount_rate < 0:
            raise ValueError("discount rate cannot be negative")
        if self.incentive_usd < 0:
            raise ValueError("incentive cannot be negative")


def calculate_project_finance(
    annual_energy_kwh: float,
    capital_cost_usd: float,
    assumptions: FinanceAssumptions | None = None,
) -> dict[str, float]:
    """Calculate discounted cash flow metrics from annual energy and capex."""
    assumptions = assumptions or FinanceAssumptions()
    if annual_energy_kwh < 0 or capital_cost_usd < 0:
        raise ValueError("energy and capital cost cannot be negative")
    net_capital_cost = max(0.0, capital_cost_usd - assumptions.incentive_usd)
    annual_om_usd = capital_cost_usd * assumptions.annual_om_fraction
    discounted_energy_kwh = 0.0
    npv_usd = -net_capital_cost
    cumulative_cash_flow = -net_capital_cost
    payback_years = float("inf")
    for year in range(1, assumptions.analysis_years + 1):
        energy = annual_energy_kwh * (1.0 - assumptions.degradation_rate) ** (year - 1)
        cash_flow = energy * assumptions.electricity_price_usd_per_kwh - annual_om_usd
        discount_factor = (1.0 + assumptions.discount_rate) ** year
        discounted_energy_kwh += energy / discount_factor
        npv_usd += cash_flow / discount_factor
        previous_cash_flow = cumulative_cash_flow
        cumulative_cash_flow += cash_flow
        if payback_years == float("inf") and cumulative_cash_flow >= 0:
            fraction = -previous_cash_flow / max(1e-12, cash_flow)
            payback_years = (year - 1) + fraction
    present_value_cost = net_capital_cost + sum(
        annual_om_usd / (1.0 + assumptions.discount_rate) ** year
        for year in range(1, assumptions.analysis_years + 1)
    )
    lcoe = present_value_cost / max(1e-12, discounted_energy_kwh)
    lifetime_energy_kwh = annual_energy_kwh * sum(
        (1.0 - assumptions.degradation_rate) ** year for year in range(assumptions.analysis_years)
    )
    return {
        "net_capital_cost_usd": float(net_capital_cost),
        "annual_om_usd": float(annual_om_usd),
        "lifetime_energy_kwh": float(lifetime_energy_kwh),
        "discounted_energy_kwh": float(discounted_energy_kwh),
        "npv_usd": float(npv_usd),
        "simple_payback_years": float(payback_years),
        "lcoe_usd_per_kwh": float(lcoe),
    }
