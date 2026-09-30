"""One-dimensional finite-difference thermal model for engineering studies."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ThermalResult:
    """Temperature field and mesh for a steady 1D conduction problem."""

    x_m: np.ndarray
    temperature_c: np.ndarray


def solve_steady_1d_fin(
    length_m: float,
    area_m2: float,
    perimeter_m: float,
    conductivity_w_mk: float,
    convection_w_m2k: float,
    ambient_temperature_c: float,
    base_temperature_c: float,
    heat_generation_w_m3: float = 0.0,
    nodes: int = 21,
) -> ThermalResult:
    """Solve a straight fin with a fixed-temperature base and convective tip.

    The governing equation is ``k A T'' - h P (T - T_inf) + q''' A = 0``.
    The base is fixed at ``base_temperature_c`` and the tip loses heat by
    convection. All geometry is SI; temperatures are degrees C and heat
    quantities are watts or watts per cubic metre.
    """
    if length_m <= 0 or area_m2 <= 0 or perimeter_m <= 0:
        raise ValueError("fin dimensions must be positive")
    if conductivity_w_mk <= 0 or convection_w_m2k <= 0:
        raise ValueError("conductivity and convection must be positive")
    if heat_generation_w_m3 < 0:
        raise ValueError("heat generation cannot be negative")
    if nodes < 3:
        raise ValueError("nodes must be at least 3")

    spacing_m = length_m / (nodes - 1)
    unknown_count = nodes - 1
    matrix = np.zeros((unknown_count, unknown_count))
    right_hand_side = np.zeros(unknown_count)
    axial_conductance = conductivity_w_mk * area_m2 / spacing_m
    convection_conductance = convection_w_m2k * perimeter_m * spacing_m
    source = heat_generation_w_m3 * area_m2 * spacing_m

    for row in range(unknown_count - 1):
        matrix[row, row] = 2.0 * axial_conductance + convection_conductance
        if row > 0:
            matrix[row, row - 1] = -axial_conductance
        else:
            right_hand_side[row] += axial_conductance * base_temperature_c
        matrix[row, row + 1] = -axial_conductance
        right_hand_side[row] += convection_conductance * ambient_temperature_c + source

    tip_row = unknown_count - 1
    matrix[tip_row, tip_row] = axial_conductance + convection_w_m2k * area_m2
    matrix[tip_row, tip_row - 1] = -axial_conductance
    right_hand_side[tip_row] = convection_w_m2k * area_m2 * ambient_temperature_c + source / 2.0

    temperatures = np.empty(nodes)
    temperatures[0] = base_temperature_c
    temperatures[1:] = np.linalg.solve(matrix, right_hand_side)
    positions = np.linspace(0.0, length_m, nodes)
    return ThermalResult(x_m=positions, temperature_c=temperatures)
