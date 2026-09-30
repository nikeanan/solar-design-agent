"""Config-driven solar optimization jobs."""

from dataclasses import dataclass
import json
from pathlib import Path

from .model import Site
from .optimize import DesignConstraints


@dataclass(frozen=True)
class SolarJob:
    site: Site
    constraints: DesignConstraints
    weather_csv: Path | None = None
    pvgis_tmy: bool = False
    save_weather_csv: Path | None = None
    report_json: Path | None = None


def _relative_path(raw_path: str | None, config_path: Path) -> Path | None:
    if raw_path is None:
        return None
    path = Path(raw_path)
    return path if path.is_absolute() else config_path.parent / path


def load_solar_job(path: str | Path) -> SolarJob:
    """Load and validate a JSON optimization job."""
    config_path = Path(path).resolve()
    with config_path.open(encoding="utf-8") as config_file:
        raw = json.load(config_file)
    if not isinstance(raw, dict):
        raise ValueError("job configuration must be a JSON object")
    if "site" not in raw:
        raise ValueError("job configuration must contain a site object")
    site = Site(**raw["site"])
    constraints = DesignConstraints(**raw.get("constraints", {}))
    weather_csv = _relative_path(raw.get("weather_csv"), config_path)
    pvgis_tmy = bool(raw.get("pvgis_tmy", False))
    if weather_csv is not None and pvgis_tmy:
        raise ValueError("job configuration cannot specify both weather_csv and pvgis_tmy")
    return SolarJob(
        site=site,
        constraints=constraints,
        weather_csv=weather_csv,
        pvgis_tmy=pvgis_tmy,
        save_weather_csv=_relative_path(raw.get("save_weather_csv"), config_path),
        report_json=_relative_path(raw.get("report_json"), config_path),
    )
