"""CLI for preliminary cantilever-bracket sizing."""

import argparse
import json
from dataclasses import asdict

from .bracket import BracketConstraints, optimize_bracket


def main() -> None:
    parser = argparse.ArgumentParser(description="Preliminary cantilever-bracket mass optimization")
    parser.add_argument("--load-n", type=float, default=1000.0)
    parser.add_argument("--length-m", type=float, default=0.20)
    parser.add_argument("--max-deflection-mm", type=float, default=2.0)
    parser.add_argument("--yield-strength-mpa", type=float, default=150.0)
    parser.add_argument("--youngs-modulus-gpa", type=float, default=69.0)
    parser.add_argument("--density-kg-m3", type=float, default=2700.0)
    parser.add_argument("--safety-factor", type=float, default=2.0)
    parser.add_argument("--report-json", type=str)
    args = parser.parse_args()
    constraints = BracketConstraints(
        load_n=args.load_n,
        max_deflection_mm=args.max_deflection_mm,
        yield_strength_pa=args.yield_strength_mpa * 1_000_000.0,
        youngs_modulus_pa=args.youngs_modulus_gpa * 1_000_000_000.0,
        density_kg_m3=args.density_kg_m3,
        safety_factor=args.safety_factor,
    )
    result = optimize_bracket(constraints)
    best = result["best"]
    print("Preliminary bracket optimization")
    print(f"Best: width={best.design.width_m * 1000:.1f} mm, thickness={best.design.thickness_m * 1000:.1f} mm, length={best.design.length_m * 1000:.1f} mm")
    print(f"Mass: {best.metrics['mass_kg']:.3f} kg | Stress: {best.metrics['stress_mpa']:.1f} MPa | Deflection: {best.metrics['deflection_mm']:.2f} mm")
    print(f"Safety factor: {best.metrics['safety_factor']:.2f} | Feasible designs: {result['feasible_count']}")
    if args.report_json:
        report = {
            "constraints": asdict(constraints),
            "best": {"design": asdict(best.design), "metrics": best.metrics, "score": best.score},
            "feasible_count": result["feasible_count"],
            "candidate_count": len(result["evaluations"]),
            "disclaimer": "Preliminary beam-model sizing only; not structural certification.",
        }
        with open(args.report_json, "w", encoding="utf-8") as report_file:
            json.dump(report, report_file, indent=2)
        print(f"Report written: {args.report_json}")


if __name__ == "__main__":
    main()
