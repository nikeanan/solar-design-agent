"""CLI for thermomechanical bracket screening."""

import argparse
import json
from dataclasses import asdict

from .thermo import ThermoMechanicalConstraints, optimize_thermomechanical_bracket


def main() -> None:
    parser = argparse.ArgumentParser(description="Thermomechanical cantilever-bracket optimization")
    parser.add_argument("--load-n", type=float, default=1000.0)
    parser.add_argument("--length-m", type=float, default=0.20)
    parser.add_argument("--max-deflection-mm", type=float, default=2.0)
    parser.add_argument("--base-temperature-c", type=float, default=80.0)
    parser.add_argument("--heat-generation-w-m3", type=float, default=100_000.0)
    parser.add_argument("--report-json", type=str)
    args = parser.parse_args()
    mechanical = ThermoMechanicalConstraints().mechanical
    constraints = ThermoMechanicalConstraints(
        mechanical=type(mechanical)(
            load_n=args.load_n,
            max_deflection_mm=args.max_deflection_mm,
            yield_strength_pa=mechanical.yield_strength_pa,
            youngs_modulus_pa=mechanical.youngs_modulus_pa,
            density_kg_m3=mechanical.density_kg_m3,
            safety_factor=mechanical.safety_factor,
        ),
        base_temperature_c=args.base_temperature_c,
        heat_generation_w_m3=args.heat_generation_w_m3,
    )
    result = optimize_thermomechanical_bracket(constraints)
    best = result["best"]
    print("Thermomechanical bracket optimization")
    print(f"Best: width={best.design.width_m * 1000:.1f} mm, thickness={best.design.thickness_m * 1000:.1f} mm, length={best.design.length_m * 1000:.1f} mm")
    print(f"Mass: {best.metrics['mass_kg']:.3f} kg | Stress: {best.metrics['stress_mpa']:.1f} MPa | Deflection: {best.metrics['deflection_mm']:.2f} mm")
    print(f"Peak temperature: {best.metrics['peak_temperature_c']:.2f} C | Thermal strength factor: {best.metrics['thermal_strength_factor']:.3f}")
    print(f"Feasible designs: {result['feasible_count']}")
    if args.report_json:
        report = {
            "constraints": asdict(constraints),
            "best": {"design": asdict(best.design), "metrics": best.metrics, "score": best.score},
            "feasible_count": result["feasible_count"],
            "candidate_count": len(result["evaluations"]),
            "disclaimer": "Thermomechanical first-order screening only; not structural certification.",
        }
        with open(args.report_json, "w", encoding="utf-8") as report_file:
            json.dump(report, report_file, indent=2)
        print(f"Report written: {args.report_json}")


if __name__ == "__main__":
    main()
