import math

import numpy as np
import pandas as pd
import pytest

from solar_design_agent.config import load_solar_job
from solar_design_agent.bracket import BracketConstraints, BracketDesign, BracketProblem, optimize_bracket
from solar_design_agent.engine import optimize_problem
from solar_design_agent.fem import cantilever_tip_deflection_fem
from solar_design_agent.finance import FinanceAssumptions, calculate_project_finance
from solar_design_agent.thermal import solve_steady_1d_fin
from solar_design_agent.thermo import ThermoMechanicalConstraints, optimize_thermomechanical_bracket
from solar_design_agent.model import ArrayDesign, Site, _cosine_incidence, simulate_design
from solar_design_agent.optimize import DesignConstraints, optimize_fixed_tilt, pareto_frontier
from solar_design_agent.weather import load_pvgis_tmy, load_weather_csv, simulate_weather_design


def test_simulation_is_positive_and_deterministic():
    site = Site(latitude_deg=28.6, days=30)
    design = ArrayDesign(tilt_deg=28.6)
    first = simulate_design(site, design)
    second = simulate_design(site, design)
    assert first == second
    assert first["annual_energy_kwh"] > 0


def test_horizontal_plane_incidence_is_independent_of_azimuth():
    latitude = 0.5
    declination = 0.2
    hour_angle = 0.3
    expected = math.sin(declination) * math.sin(latitude) + math.cos(declination) * math.cos(latitude) * math.cos(hour_angle)

    values = [_cosine_incidence(latitude, declination, hour_angle, ArrayDesign(tilt_deg=0.0, azimuth_deg=azimuth)) for azimuth in (0.0, 90.0, 180.0, 270.0)]

    assert values == pytest.approx([expected] * 4)


def test_invalid_engineering_inputs_fail_fast():
    with pytest.raises(ValueError, match="latitude_deg"):
        Site(latitude_deg=91.0)
    with pytest.raises(ValueError, match="module count"):
        ArrayDesign(tilt_deg=20.0, modules=0)
    with pytest.raises(ValueError, match="objective"):
        DesignConstraints(objective="cost")


def test_job_config_resolves_relative_paths(tmp_path):
    config_path = tmp_path / "job.json"
    config_path.write_text(
        '{"site": {"latitude_deg": 28.6}, "weather_csv": "weather.csv", "constraints": {"objective": "value"}}',
        encoding="utf-8",
    )

    job = load_solar_job(config_path)

    assert job.site.latitude_deg == 28.6
    assert job.weather_csv == tmp_path / "weather.csv"
    assert job.constraints.objective == "value"


def test_generic_engine_can_optimize_a_non_solar_design():
    class BracketProblem:
        def candidate_designs(self):
            return [10, 20, 30]

        def evaluate(self, thickness):
            return {"strength": float(thickness * 2), "mass": float(thickness)}

        def is_feasible(self, thickness, metrics):
            return thickness > 0 and metrics["strength"] >= 40

        def score(self, thickness, metrics):
            return -metrics["mass"] if thickness > 0 else float("-inf")

    result = optimize_problem(BracketProblem())

    assert result["best"].design == 20
    assert result["feasible_count"] == 2


def test_bracket_physics_reports_expected_units_and_constraints():
    problem = BracketProblem(BracketConstraints(load_n=1000.0))
    design = BracketDesign(width_m=0.05, thickness_m=0.02, length_m=0.20)
    metrics = problem.evaluate(design)

    assert metrics["stress_mpa"] > 0
    assert metrics["deflection_mm"] > 0
    assert metrics["mass_kg"] > 0
    assert problem.is_feasible(design, metrics)


def test_beam_fem_matches_closed_form_deflection():
    load_n = 1000.0
    length_m = 0.20
    width_m = 0.05
    thickness_m = 0.02
    youngs_modulus_pa = 69_000_000_000.0
    inertia_m4 = width_m * thickness_m**3 / 12.0
    closed_form = load_n * length_m**3 / (3.0 * youngs_modulus_pa * inertia_m4)

    fem_deflection = cantilever_tip_deflection_fem(load_n, length_m, width_m, thickness_m, youngs_modulus_pa, elements=8)

    assert fem_deflection == pytest.approx(closed_form, rel=1e-6)


def test_bracket_optimizer_returns_lightest_feasible_design():
    result = optimize_bracket()
    best = result["best"]

    assert result["feasible_count"] > 0
    assert best.feasible
    assert best.metrics["stress_mpa"] <= best.metrics["allowable_stress_mpa"]
    assert best.metrics["deflection_mm"] <= 2.0


def test_project_finance_calculates_discounted_metrics():
    finance = calculate_project_finance(
        annual_energy_kwh=10_000.0,
        capital_cost_usd=10_000.0,
        assumptions=FinanceAssumptions(electricity_price_usd_per_kwh=0.20, annual_om_fraction=0.0, degradation_rate=0.0, discount_rate=0.0, analysis_years=10),
    )

    assert finance["lifetime_energy_kwh"] == pytest.approx(100_000.0)
    assert finance["npv_usd"] > 0
    assert finance["simple_payback_years"] == pytest.approx(5.0)
    assert finance["lcoe_usd_per_kwh"] == pytest.approx(10_000.0 / finance["discounted_energy_kwh"])


def test_fdm_fin_thermal_field_has_physical_boundaries():
    result = solve_steady_1d_fin(
        length_m=0.20,
        area_m2=0.0002,
        perimeter_m=0.06,
        conductivity_w_mk=205.0,
        convection_w_m2k=12.0,
        ambient_temperature_c=25.0,
        base_temperature_c=80.0,
        heat_generation_w_m3=100_000.0,
        nodes=21,
    )

    assert result.x_m.shape == (21,)
    assert result.temperature_c.shape == (21,)
    assert result.temperature_c[0] == pytest.approx(80.0)
    assert result.temperature_c[-1] < result.temperature_c[0]
    assert result.temperature_c[-1] > 25.0
    assert np.all(np.diff(result.temperature_c) <= 0.0)


def test_thermomechanical_bracket_couples_temperature_to_strength():
    result = optimize_thermomechanical_bracket(ThermoMechanicalConstraints(base_temperature_c=100.0))
    best = result["best"]

    assert result["feasible_count"] > 0
    assert best.metrics["peak_temperature_c"] >= 100.0
    assert best.metrics["thermal_strength_factor"] < 1.0
    assert best.metrics["stress_mpa"] <= best.metrics["allowable_stress_mpa"]


def test_optimizer_returns_a_design_no_worse_than_baseline():
    result = optimize_fixed_tilt(Site(latitude_deg=28.6, days=30))
    assert result["best"]["result"]["annual_energy_kwh"] >= result["baseline"]["result"]["annual_energy_kwh"]
    assert 0 <= result["best"]["design"].tilt_deg <= 90


def test_optimizer_respects_land_and_budget_constraints():
    constraints = DesignConstraints(max_land_area_m2=250.0, max_budget_usd=30_000.0)
    result = optimize_fixed_tilt(Site(latitude_deg=28.6, days=30), constraints=constraints)
    best = result["best"]
    assert best["feasible"]
    assert best["economics"]["land_area_m2"] <= 250.0
    assert best["economics"]["capital_cost_usd"] <= 30_000.0


def test_value_objective_is_reported():
    result = optimize_fixed_tilt(Site(latitude_deg=28.6, days=30), constraints=DesignConstraints(objective="value"))
    economics = result["best"]["economics"]
    assert economics["objective_value"] == economics["annual_revenue_usd"] - 0.01 * economics["capital_cost_usd"]


def test_pareto_frontier_excludes_dominated_designs():
    candidates = [
        {"feasible": True, "result": {"annual_energy_kwh": 100.0}, "economics": {"land_area_m2": 10.0, "capital_cost_usd": 1000.0}},
        {"feasible": True, "result": {"annual_energy_kwh": 90.0}, "economics": {"land_area_m2": 10.0, "capital_cost_usd": 1000.0}},
        {"feasible": True, "result": {"annual_energy_kwh": 110.0}, "economics": {"land_area_m2": 20.0, "capital_cost_usd": 1000.0}},
        {"feasible": False, "result": {"annual_energy_kwh": 1000.0}, "economics": {"land_area_m2": 1.0, "capital_cost_usd": 1.0}},
    ]

    frontier = pareto_frontier(candidates)

    assert frontier == [candidates[2], candidates[0]]


def test_weather_simulation_is_deterministic_and_uses_hourly_irradiance():
    times = pd.date_range("2024-06-21 10:00", periods=3, freq="h", tz="UTC")
    weather = pd.DataFrame(
        {
            "ghi_w_m2": [700.0, 900.0, 700.0],
            "dni_w_m2": [500.0, 700.0, 500.0],
            "dhi_w_m2": [200.0, 200.0, 200.0],
            "temp_air_c": [25.0, 25.0, 25.0],
        },
        index=times,
    )
    site = Site(latitude_deg=28.6, longitude_deg=0.0)
    design = ArrayDesign(tilt_deg=28.6)

    first = simulate_weather_design(site, design, weather)
    second = simulate_weather_design(site, design, weather)

    assert first == second
    assert first["annual_energy_kwh"] > 0
    assert first["weather_samples"] == 3


def test_optimizer_can_search_against_weather_data():
    times = pd.date_range("2024-06-21 10:00", periods=3, freq="h", tz="UTC")
    weather = pd.DataFrame(
        {"ghi_w_m2": [700.0, 900.0, 700.0], "dni_w_m2": [500.0, 700.0, 500.0], "dhi_w_m2": [200.0, 200.0, 200.0]},
        index=times,
    )

    result = optimize_fixed_tilt(Site(latitude_deg=28.6), weather=weather)

    assert result["best"]["result"]["weather_samples"] == 3
    assert result["best"]["result"]["annual_energy_kwh"] >= result["baseline"]["result"]["annual_energy_kwh"]


def test_weather_csv_loader_requires_timezone_and_adds_default_temperature(tmp_path):
    path = tmp_path / "weather.csv"
    pd.DataFrame(
        {
            "timestamp": ["2024-06-21T10:00:00+00:00"],
            "ghi_w_m2": [700.0],
            "dni_w_m2": [500.0],
            "dhi_w_m2": [200.0],
        }
    ).to_csv(path, index=False)

    weather = load_weather_csv(path)

    assert weather.index.tz is not None
    assert weather["temp_air_c"].iloc[0] == 25.0


def test_pvgis_loader_normalizes_columns_and_timezone(monkeypatch):
    times = pd.date_range("1990-01-01", periods=2, freq="h")
    source = pd.DataFrame(
        {"ghi": [500.0, 600.0], "dni": [400.0, 500.0], "dhi": [100.0, 100.0], "temp_air": [20.0, 21.0]},
        index=times,
    )

    def fake_get_pvgis_tmy(**kwargs):
        assert kwargs["latitude"] == 28.6
        assert kwargs["longitude"] == -81.4
        return source, {"location": "test"}

    monkeypatch.setattr("solar_design_agent.weather.iotools.get_pvgis_tmy", fake_get_pvgis_tmy)
    weather = load_pvgis_tmy(Site(latitude_deg=28.6, longitude_deg=-81.4))

    assert weather.index.tz is not None
    assert list(weather.columns) == ["ghi_w_m2", "dni_w_m2", "dhi_w_m2", "temp_air_c"]
    assert weather.attrs["source"] == "PVGIS TMY"
