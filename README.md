# Solar Design Agent

A physics-first prototype for optimizing fixed-tilt photovoltaic array layouts. It compares a conventional baseline against candidate designs while keeping assumptions and constraints explicit.

## Current scope

- Clear-sky, hourly solar geometry using textbook declination and hour-angle equations
- Plane-of-array irradiance approximation for a fixed-tilt array
- Row-spacing and shading penalty approximation
- Module efficiency, temperature, inverter, and wiring losses
- Constrained grid search over tilt, azimuth, and row spacing
- Land and budget feasibility constraints
- Energy or simple economic-value objectives
- JSON design reports for downstream agents and review
- Pareto frontier across annual energy, land use, and capital cost
- Domain-neutral `DesignProblem` engine for future machine and part adapters
- Deterministic tests with no weather download required

This is a research prototype. It does not certify structural or electrical designs and does not perform procurement or construction actions.

## Run

```powershell
python -m pip install -e ".[test]"
solar-optimize --latitude 28.6 --days 365
pytest
```

Run a constrained design study and save a report:

```powershell
solar-optimize --latitude 28.6 --longitude -81.4 --weather-csv .\weather.csv --objective value --max-land-area-m2 250 --max-budget-usd 30000 --electricity-price-usd-per-kwh 0.10 --report-json .\design-report.json
```

The same workflow can be driven by a reproducible JSON job:

```powershell
solar-optimize --config .\solar-job.json
```

The sample [solar-job.json](solar-job.json) keeps the site, weather file,
constraints, objective, and report path together. Relative paths are resolved
from the configuration file, which makes jobs portable and suitable for later
automation or additional engineering-problem adapters.

The NPV objective uses explicit assumptions for electricity price, O&M,
degradation, analysis life, discount rate, and incentives. These assumptions
must be replaced with project-specific contracts, tariffs, financing, taxes,
and incentives before making an investment decision.

The optimizer now searches module count in addition to tilt, azimuth, and row
spacing. It rejects designs exceeding the supplied land or budget limits and
reports estimated land, capital cost, annual revenue, objective value, and the
non-dominated Pareto designs. A small frontier is expected when the budget and
land constraints are tight.
These economic values are transparent planning assumptions, not quotations or
financial advice. The generated `weather.csv` is a synthetic development
fixture; replace it with timezone-aware measured data for a real study.

The command prints the baseline, best feasible candidate, and the main trade-offs. For measured hourly weather, pass a timezone-aware CSV with `timestamp`, `ghi_w_m2`, `dni_w_m2`, `dhi_w_m2`, and optional `temp_air_c` columns:

```powershell
solar-optimize --latitude 28.6 --longitude -81.4 --weather-csv .\weather.csv
```

For a full-year typical meteorological year from PVGIS, use the network-backed
provider:

```powershell
solar-optimize --latitude 28.6 --longitude -81.4 --pvgis-tmy --save-weather-csv .\pvgis-tmy-28.6--81.4.csv --report-json .\pvgis-report.json
```

This downloads hourly PVGIS TMY data, normalizes it to the project schema, and
records `PVGIS TMY` plus the sample count in the JSON report. The saved CSV is
the exact 8,760-row dataset used by the run and can be reused offline with
`--weather-csv`. Network access is required only for the initial download.

The weather-backed path uses pvlib for solar position and plane-of-array irradiance. The clear-sky model remains available as a deterministic offline baseline.

When `--weather-csv` or `--pvgis-tmy` is supplied, the optimizer scores its
candidate designs directly against those hourly observations. Without a
weather source, it uses the deterministic clear-sky baseline model.

The reusable engine in `src/solar_design_agent/engine.py` defines four domain
hooks: `candidate_designs`, `evaluate`, `is_feasible`, and `score`. Solar is
the first production adapter; a manufactured-part adapter can implement the
same contract with its own physics simulation and constraints.

The first manufactured-part adapter is a preliminary cantilever-bracket
sizing model:

```powershell
bracket-optimize --load-n 1000 --length-m 0.20 --max-deflection-mm 2.0 --report-json .\bracket-report.json
```

It evaluates rectangular-section bending stress, tip deflection, mass, and
safety factor, then selects the lightest feasible candidate. This is a
first-order beam model for concept screening, not structural certification;
real designs still require detailed geometry, joints, buckling, fatigue,
materials, manufacturing, and professional review.

The project also includes a small Euler-Bernoulli beam FEM validator in
`src/solar_design_agent/fem.py`. FEM is useful here to cross-check the
analytical bracket model. FDM should be added only when the problem includes a
distributed field such as temperature, and PINNs or ML/DL should be deferred
until a validated simulation dataset exists for surrogate modeling.

The first FDM capability is `solve_steady_1d_fin` in
`src/solar_design_agent/thermal.py`. It solves steady conduction with
convection, a fixed-temperature base, a convective tip, and optional volumetric
heat generation. It is a thermal building block, not a full CFD or multiphysics
solver.

The thermal field is now coupled into a thermomechanical bracket screen:

```powershell
thermo-bracket-optimize --load-n 1000 --length-m 0.20 --base-temperature-c 100 --report-json .\thermo-bracket-report.json
```

The coupling reduces allowable material strength as peak temperature rises.
This is an explicit screening assumption that must be replaced with material
test data for production use.

## Research basis

The implementation follows standard solar-position and irradiance concepts and is designed to integrate with pvlib's validated PV performance models. Optimization is deliberately separated from simulation so that every proposed design can be rerun through a trusted physics model.
# solar-design-agent
