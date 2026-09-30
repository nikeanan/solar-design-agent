"""Transparent first-order PV array model for optimization experiments."""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Site:
    latitude_deg: float
    days: int = 365
    peak_irradiance_w_m2: float = 1000.0
    longitude_deg: float = 0.0

    def __post_init__(self) -> None:
        if not -90 <= self.latitude_deg <= 90:
            raise ValueError("latitude_deg must be between -90 and 90")
        if not -180 <= self.longitude_deg <= 180:
            raise ValueError("longitude_deg must be between -180 and 180")
        if self.days < 1:
            raise ValueError("days must be at least 1")
        if self.peak_irradiance_w_m2 <= 0:
            raise ValueError("peak_irradiance_w_m2 must be positive")


@dataclass(frozen=True)
class ArrayDesign:
    tilt_deg: float
    azimuth_deg: float = 180.0
    row_spacing_m: float = 4.0
    module_area_m2: float = 2.0
    module_efficiency: float = 0.21
    modules: int = 100
    inverter_efficiency: float = 0.97
    wiring_efficiency: float = 0.98

    def __post_init__(self) -> None:
        if not 0 <= self.tilt_deg <= 90:
            raise ValueError("tilt_deg must be between 0 and 90")
        if not 0 <= self.azimuth_deg <= 360:
            raise ValueError("azimuth_deg must be between 0 and 360")
        if self.row_spacing_m < 1:
            raise ValueError("row_spacing_m must be at least 1 metre")
        if self.module_area_m2 <= 0 or self.modules < 1:
            raise ValueError("module area and module count must be positive")
        for name, value in (("module_efficiency", self.module_efficiency), ("inverter_efficiency", self.inverter_efficiency), ("wiring_efficiency", self.wiring_efficiency)):
            if not 0 < value <= 1:
                raise ValueError(f"{name} must be greater than 0 and at most 1")


def _solar_declination(day: int) -> float:
    return math.radians(23.44 * math.sin(math.radians(360.0 * (284 + day) / 365.0)))


def _cosine_incidence(latitude: float, declination: float, hour_angle: float, design: ArrayDesign) -> float:
    # Standard fixed-plane incidence relation; south-facing is gamma = 0.
    beta = math.radians(design.tilt_deg)
    gamma = math.radians(design.azimuth_deg - 180.0)
    return (
        math.sin(declination) * math.sin(latitude) * math.cos(beta)
        - math.sin(declination) * math.cos(latitude) * math.sin(beta) * math.cos(gamma)
        + math.cos(declination) * math.cos(latitude) * math.cos(beta) * math.cos(hour_angle)
        + math.cos(declination) * math.sin(latitude) * math.sin(beta) * math.cos(gamma) * math.cos(hour_angle)
        + math.cos(declination) * math.sin(beta) * math.sin(gamma) * math.sin(hour_angle)
    )


def simulate_design(site: Site, design: ArrayDesign) -> dict[str, float]:
    if not 0 <= design.tilt_deg <= 90:
        raise ValueError("tilt_deg must be between 0 and 90")
    if not 1 <= design.row_spacing_m:
        raise ValueError("row_spacing_m must be at least 1 metre")

    latitude = math.radians(site.latitude_deg)
    daily_energy_kwh = 0.0
    shading_loss = 0.0
    samples = 0
    for day in range(1, site.days + 1):
        declination = _solar_declination(day)
        for hour in range(24):
            hour_angle = math.radians(15.0 * (hour - 12.0))
            cos_zenith = math.sin(latitude) * math.sin(declination) + math.cos(latitude) * math.cos(declination) * math.cos(hour_angle)
            if cos_zenith <= 0:
                continue
            incidence = max(0.0, _cosine_incidence(latitude, declination, hour_angle, design))
            plane_irradiance = site.peak_irradiance_w_m2 * incidence
            spacing_ratio = design.row_spacing_m / max(0.1, 2.0 * math.cos(math.radians(design.tilt_deg)))
            shade_factor = min(1.0, max(0.0, spacing_ratio / 2.0))
            loss = 0.12 * (1.0 - shade_factor)
            shading_loss += loss
            samples += 1
            cell_temperature_factor = max(0.80, 1.0 - 0.004 * (25.0 + 0.25 * plane_irradiance - 25.0))
            dc_kw = plane_irradiance * design.module_area_m2 * design.modules * design.module_efficiency * cell_temperature_factor / 1000.0
            daily_energy_kwh += dc_kw * (1.0 - loss) * design.inverter_efficiency * design.wiring_efficiency

    return {
        "annual_energy_kwh": daily_energy_kwh,
        "average_shading_loss": shading_loss / max(1, samples),
        "capacity_kw": design.module_area_m2 * design.modules * design.module_efficiency,
        "energy_density_kwh_m2": daily_energy_kwh / max(1.0, design.modules * design.module_area_m2),
    }
