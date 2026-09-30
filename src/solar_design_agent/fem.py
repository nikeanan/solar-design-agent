"""Small Euler-Bernoulli beam FEM validation model."""

import numpy as np


def cantilever_tip_deflection_fem(
    load_n: float,
    length_m: float,
    width_m: float,
    thickness_m: float,
    youngs_modulus_pa: float,
    elements: int = 8,
) -> float:
    """Return downward tip deflection in metres for a 2D cantilever beam.

    Each node has transverse displacement and rotation degrees of freedom.
    This is a validation model for slender beams, not a general 3D structural
    solver and not a substitute for a certified FEA package.
    """
    if load_n <= 0 or length_m <= 0 or width_m <= 0 or thickness_m <= 0 or youngs_modulus_pa <= 0:
        raise ValueError("load, geometry, and material stiffness must be positive")
    if elements < 1:
        raise ValueError("elements must be at least 1")

    element_length_m = length_m / elements
    inertia_m4 = width_m * thickness_m**3 / 12.0
    stiffness_scale = youngs_modulus_pa * inertia_m4 / element_length_m**3
    element_stiffness = stiffness_scale * np.array(
        [
            [12.0, 6.0 * element_length_m, -12.0, 6.0 * element_length_m],
            [6.0 * element_length_m, 4.0 * element_length_m**2, -6.0 * element_length_m, 2.0 * element_length_m**2],
            [-12.0, -6.0 * element_length_m, 12.0, -6.0 * element_length_m],
            [6.0 * element_length_m, 2.0 * element_length_m**2, -6.0 * element_length_m, 4.0 * element_length_m**2],
        ]
    )
    degrees_of_freedom = 2 * (elements + 1)
    global_stiffness = np.zeros((degrees_of_freedom, degrees_of_freedom))
    for element in range(elements):
        start = 2 * element
        indices = [start, start + 1, start + 2, start + 3]
        global_stiffness[np.ix_(indices, indices)] += element_stiffness

    load_vector = np.zeros(degrees_of_freedom)
    load_vector[-2] = -load_n
    free = np.arange(2, degrees_of_freedom)
    displacement = np.linalg.solve(global_stiffness[np.ix_(free, free)], load_vector[free])
    return float(abs(displacement[-2]))
