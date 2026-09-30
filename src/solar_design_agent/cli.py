"""Command-line entry point."""

import argparse
import json
from .config import load_solar_job
from .model import Site
from .optimize import DesignConstraints, optimize_fixed_tilt
from .weather import load_pvgis_tmy, load_weather_csv, simulate_weather_design


def main() -> None:
    parser = argparse.ArgumentParser(description="Optimize a fixed-tilt PV array layout")
    parser.add_argument("--config", type=str, help="JSON job configuration")
    parser.add_argument("--latitude", type=float, default=28.6)
    parser.add_argument("--longitude", type=float, default=0.0)
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--weather-csv", type=str, help="Hourly weather CSV for pvlib-backed simulation")
    parser.add_argument("--pvgis-tmy", action="store_true", help="Download a full-year PVGIS typical meteorological year")
    parser.add_argument("--save-weather-csv", type=str, help="Save the selected weather data as a normalized CSV")
    parser.add_argument("--objective", choices=("energy", "value", "npv"), default="energy")
    parser.add_argument("--max-land-area-m2", type=float, default=float("inf"))
    parser.add_argument("--max-budget-usd", type=float, default=float("inf"))
    parser.add_argument("--electricity-price-usd-per-kwh", type=float, default=0.10)
    parser.add_argument("--annual-om-fraction", type=float, default=0.015)
    parser.add_argument("--degradation-rate", type=float, default=0.005)
    parser.add_argument("--analysis-years", type=int, default=25)
    parser.add_argument("--discount-rate", type=float, default=0.08)
    parser.add_argument("--incentive-usd", type=float, default=0.0)
    parser.add_argument("--report-json", type=str, help="Write the selected design and assumptions to JSON")
    args = parser.parse_args()
    if args.config:
        job = load_solar_job(args.config)
        site = job.site
        constraints = job.constraints
        weather_csv = job.weather_csv
        pvgis_tmy = job.pvgis_tmy
        save_weather_csv = job.save_weather_csv
        report_json = job.report_json
    else:
        site = Site(latitude_deg=args.latitude, longitude_deg=args.longitude, days=args.days)
        if args.weather_csv and args.pvgis_tmy:
            parser.error("choose only one of --weather-csv or --pvgis-tmy")
        constraints = DesignConstraints(objective=args.objective, max_land_area_m2=args.max_land_area_m2, max_budget_usd=args.max_budget_usd, electricity_price_usd_per_kwh=args.electricity_price_usd_per_kwh, annual_om_fraction=args.annual_om_fraction, degradation_rate=args.degradation_rate, analysis_years=args.analysis_years, discount_rate=args.discount_rate, incentive_usd=args.incentive_usd)
        weather_csv = args.weather_csv
        pvgis_tmy = args.pvgis_tmy
        save_weather_csv = args.save_weather_csv
        report_json = args.report_json
    weather = None
    weather_source = None
    weather_result = None
    if weather_csv:
        weather = load_weather_csv(weather_csv)
        weather_source = str(weather_csv)
    elif pvgis_tmy:
        weather = load_pvgis_tmy(site)
        weather_source = "PVGIS TMY"
    result = optimize_fixed_tilt(site, constraints=constraints, weather=weather)
    baseline = result["baseline"]
    best = result["best"]
    print("Solar Design Agent prototype")
    print(f"Baseline: tilt={baseline['design'].tilt_deg:.1f} deg, spacing={baseline['design'].row_spacing_m:.1f} m, energy={baseline['result']['annual_energy_kwh']:.2f} kWh")
    print(f"Best:     tilt={best['design'].tilt_deg:.1f} deg, azimuth={best['design'].azimuth_deg:.1f} deg, spacing={best['design'].row_spacing_m:.1f} m, energy={best['result']['annual_energy_kwh']:.2f} kWh")
    improvement = 100.0 * (best["result"]["annual_energy_kwh"] / baseline["result"]["annual_energy_kwh"] - 1.0)
    if not baseline["feasible"]:
        print("Baseline is infeasible under the supplied land or budget constraints")
    elif constraints.objective == "energy":
        print(f"Energy improvement: {improvement:.2f}%")
    elif constraints.objective == "npv":
        print(f"NPV: ${best['economics']['npv_usd']:,.2f} | Payback: {best['economics']['simple_payback_years']:.2f} years | LCOE: ${best['economics']['lcoe_usd_per_kwh']:.3f}/kWh")
    else:
        print(f"Value objective: ${best['economics']['objective_value']:,.2f} per year-equivalent")
        print(f"Energy change under value objective: {improvement:.2f}%")
    print(f"Feasible designs: {result['feasible_count']}")
    print(f"Pareto designs: {len(result['pareto_frontier'])}")
    print(f"Land: {best['economics']['land_area_m2']:.1f} m2 | Capital cost: ${best['economics']['capital_cost_usd']:,.0f} | Annual revenue: ${best['economics']['annual_revenue_usd']:,.0f}")
    print(f"NPV: ${best['economics']['npv_usd']:,.0f} | LCOE: ${best['economics']['lcoe_usd_per_kwh']:.3f}/kWh")
    if weather is not None:
        if save_weather_csv:
            weather_to_save = weather.copy()
            weather_to_save.index.name = "timestamp"
            weather_to_save.to_csv(save_weather_csv)
            print(f"Weather dataset written: {save_weather_csv}")
        weather_result = simulate_weather_design(site, best["design"], weather)
        print(f"Weather-backed energy: {weather_result['annual_energy_kwh']:.2f} kWh")
    if report_json:
        report = {"site": vars(site), "constraints": vars(constraints), "weather_source": weather_source, "weather_samples": len(weather) if weather is not None else 0, "weather_result": weather_result, "baseline": {"design": vars(baseline["design"]), "result": baseline["result"], "economics": baseline["economics"], "feasible": baseline["feasible"]}, "best": {"design": vars(best["design"]), "result": best["result"], "economics": best["economics"]}, "feasible_count": result["feasible_count"], "pareto_frontier": [{"design": vars(item["design"]), "result": item["result"], "economics": item["economics"]} for item in result["pareto_frontier"]]}
        with open(report_json, "w", encoding="utf-8") as report_file:
            json.dump(report, report_file, indent=2)
        print(f"Report written: {report_json}")


if __name__ == "__main__":
    main()
