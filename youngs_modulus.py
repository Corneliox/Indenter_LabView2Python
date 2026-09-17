"""
Young's Modulus & Elasticity Analysis Module
Implements Effective Young's Modulus formulas:
- Hayes, Keer et al. (1972) & Zheng & Mak (1999)
- Legacy MATLAB compatibility: s3_e_20170718_polyfit_index_kUS.m
- Dual Calculation Modes:
  1. 'matlab_polyfit': 2nd-degree polynomial fitting evaluated at strain ratios (0.05, 0.10, 0.15) of thickness h, with E23 calculation.
  2. 'piecewise_linear': Piecewise linear regression across displacement depth percentages (5-35%, 35-70%, 70-100%).
"""

import numpy as np
from typing import Optional, Union


# Hayes lookup table from legacy MATLAB script (s3_e_20170718_polyfit_index_kUS.m, index_k_serial)
# Column 0: a/h ratio, Column 1: geometric factor kappa
HAYES_LOOKUP_TABLE = np.array([
    [0.2, 1.252],
    [0.4, 1.599],
    [0.6, 2.031],
    [0.8, 2.532],
    [1.0, 3.085],
    [1.5, 4.638],
    [2.0, 6.380],
    [2.5, 8.265],
    [3.0, 10.26],
    [3.5, 12.32],
    [4.0, 14.45],
    [5.0, 18.80],
    [6.0, 23.23],
    [7.0, 27.69],
    [8.0, 32.15]
])


def calculate_hayes_kappa(a_over_h: float, nu: float = 0.45, use_matlab_table: bool = True) -> float:
    """
    Geometric scaling factor kappa(a/h, nu) for cylindrical flat-ended indenter
    on an elastic layer bounded to a rigid substrate (Hayes et al. 1972).

    If use_matlab_table is True:
        Fits a 2nd-degree polynomial to index_k_serial exactly reproducing
        MATLAB s3_e_20170718_polyfit_index_kUS.m (lines 122-123).
    Else:
        Uses the empirical quadratic approximation:
        kappa ~ 1.0 + 0.65 * (a/h) + 0.20 * (a/h)^2
    """
    if use_matlab_table:
        x = HAYES_LOOKUP_TABLE[:, 0]
        y = HAYES_LOOKUP_TABLE[:, 1]
        p = np.polyfit(x, y, 2)
        kappa = float(np.polyval(p, a_over_h))
        return max(1.0, kappa)
    else:
        return 1.0 + 0.65 * a_over_h + 0.20 * (a_over_h ** 2)


def calculate_youngs_modulus_matlab(
    force_n: np.ndarray,
    displacement_mm: np.ndarray,
    indenter_radius_mm: float = 4.5,
    tissue_thickness_mm: float = 12.0,
    poisson_ratio: float = 0.45,
    ratios: tuple[float, float, float] = (0.05, 0.10, 0.15)
) -> dict[str, Union[float, str]]:
    """
    Exact mathematical replication of legacy MATLAB script:
    's3_e_20170718_polyfit_index_kUS.m'

    Steps:
    1. Filter increasing displacement (loading phase).
    2. Fit 2nd-degree polynomial: P(w) = c2 * w^2 + c1 * w + c0.
    3. Evaluate secant modulus at ed = h * ratio:
       E_i = (P(ed_i) / ed_i) * [(1 - nu^2) / (2 * a * kappa)]
    4. Compute incremental modulus E23:
       E23 = [(P(ed3) - P(ed2)) / (ed3 - ed2)] * Geometry_Factor
    """
    if len(displacement_mm) < 10 or len(force_n) < 10:
        return {"E1_kPa": 0.0, "E2_kPa": 0.0, "E3_kPa": 0.0, "E23_kPa": 0.0, "E_mean_kPa": 0.0, "mode": "matlab_polyfit"}

    max_disp_idx = np.argmax(displacement_mm)
    disp_loading = displacement_mm[:max_disp_idx + 1]
    force_loading = force_n[:max_disp_idx + 1]

    max_w = float(np.max(disp_loading))
    if max_w <= 1e-4:
        return {"E1_kPa": 0.0, "E2_kPa": 0.0, "E3_kPa": 0.0, "E23_kPa": 0.0, "E_mean_kPa": 0.0, "mode": "matlab_polyfit"}

    # Biomechanical geometric scaling
    a_m = indenter_radius_mm * 1e-3
    a_over_h = indenter_radius_mm / tissue_thickness_mm

    kappa = calculate_hayes_kappa(a_over_h, poisson_ratio, use_matlab_table=True)
    geometry_factor = (1.0 - (poisson_ratio ** 2)) / (2.0 * a_m * kappa)  # in 1/m

    # Fit 2nd-order polynomial matching MATLAB: p2 = polyfit(data_w, data_f, 2)
    p2 = np.polyfit(disp_loading, force_loading, 2)

    e_young3 = []
    e_force3 = []
    e_deform3 = []

    for r in ratios:
        ed = tissue_thickness_mm * r
        ed_i = min(ed, max_w)
        if ed_i < 1e-5:
            ed_i = 1e-5

        ef_i = float(np.polyval(p2, ed_i))
        # E = (Force / disp_meters) * geometry_factor / 1000.0 (in kPa)
        ee_i = (ef_i / (ed_i * 1e-3)) * geometry_factor / 1000.0

        e_young3.append(max(0.0, ee_i))
        e_force3.append(ef_i)
        e_deform3.append(ed_i)

    # Chord modulus between stage 2 (10% h) and stage 3 (15% h)
    delta_w_m = (e_deform3[2] - e_deform3[1]) * 1e-3
    if delta_w_m > 1e-5:
        e_young23 = ((e_force3[2] - e_force3[1]) / delta_w_m) * geometry_factor / 1000.0
    else:
        e_young23 = e_young3[2]

    e_young23 = max(0.0, e_young23)
    e_mean = float(np.mean(e_young3))

    return {
        "E1_kPa": round(float(e_young3[0]), 2),
        "E2_kPa": round(float(e_young3[1]), 2),
        "E3_kPa": round(float(e_young3[2]), 2),
        "E23_kPa": round(float(e_young23), 2),
        "E_mean_kPa": round(float(e_mean), 2),
        "mode": "matlab_polyfit"
    }


def calculate_youngs_modulus_linear(
    force_n: np.ndarray,
    displacement_mm: np.ndarray,
    indenter_radius_mm: float = 4.5,
    tissue_thickness_mm: float = 12.0,
    poisson_ratio: float = 0.45
) -> dict[str, Union[float, str]]:
    """
    Computes Effective Young's Modulus using piecewise linear regression:
    E1: 5% - 35% max displacement
    E2: 35% - 70% max displacement
    E3: 70% - 100% max displacement
    E_mean: overall slope across 0 - 100%
    """
    if len(displacement_mm) < 10 or len(force_n) < 10:
        return {"E1_kPa": 0.0, "E2_kPa": 0.0, "E3_kPa": 0.0, "E23_kPa": 0.0, "E_mean_kPa": 0.0, "mode": "piecewise_linear"}

    max_disp_idx = np.argmax(displacement_mm)
    disp_loading = displacement_mm[:max_disp_idx + 1]
    force_loading = force_n[:max_disp_idx + 1]

    a_m = indenter_radius_mm * 1e-3
    w_m = disp_loading * 1e-3
    p_n = force_loading

    a_over_h = indenter_radius_mm / tissue_thickness_mm
    kappa = calculate_hayes_kappa(a_over_h, poisson_ratio, use_matlab_table=True)
    geometry_factor = (1.0 - (poisson_ratio ** 2)) / (2.0 * a_m * kappa)

    max_w = np.max(w_m)
    if max_w <= 1e-5:
        return {"E1_kPa": 0.0, "E2_kPa": 0.0, "E3_kPa": 0.0, "E23_kPa": 0.0, "E_mean_kPa": 0.0, "mode": "piecewise_linear"}

    def fit_slope(w_sub, p_sub):
        if len(w_sub) < 3:
            return 0.0
        slope, _ = np.polyfit(w_sub, p_sub, 1)
        return max(0.0, slope)

    mask_e1 = (w_m >= 0.05 * max_w) & (w_m <= 0.35 * max_w)
    mask_e2 = (w_m > 0.35 * max_w) & (w_m <= 0.70 * max_w)
    mask_e3 = (w_m > 0.70 * max_w) & (w_m <= 1.00 * max_w)

    slope_e1 = fit_slope(w_m[mask_e1], p_n[mask_e1]) if np.any(mask_e1) else 0.0
    slope_e2 = fit_slope(w_m[mask_e2], p_n[mask_e2]) if np.any(mask_e2) else 0.0
    slope_e3 = fit_slope(w_m[mask_e3], p_n[mask_e3]) if np.any(mask_e3) else 0.0
    slope_all = fit_slope(w_m, p_n)

    e1_kpa = (geometry_factor * slope_e1) / 1000.0
    e2_kpa = (geometry_factor * slope_e2) / 1000.0
    e3_kpa = (geometry_factor * slope_e3) / 1000.0
    e_mean_kpa = (geometry_factor * slope_all) / 1000.0

    return {
        "E1_kPa": round(float(e1_kpa), 2),
        "E2_kPa": round(float(e2_kpa), 2),
        "E3_kPa": round(float(e3_kpa), 2),
        "E23_kPa": round(float((e2_kpa + e3_kpa) / 2.0), 2),
        "E_mean_kPa": round(float(e_mean_kpa), 2),
        "mode": "piecewise_linear"
    }


def calculate_effective_youngs_modulus(
    force_n: np.ndarray,
    displacement_mm: np.ndarray,
    indenter_radius_mm: float = 4.5,
    tissue_thickness_mm: float = 12.0,
    poisson_ratio: float = 0.45,
    method: str = "matlab_polyfit",
    ratios: tuple[float, float, float] = (0.05, 0.10, 0.15)
) -> dict[str, Union[float, str]]:
    """
    Unified entry point for Young's Modulus calculation.
    Supports 'matlab_polyfit' (default) and 'piecewise_linear'.
    """
    if method == "piecewise_linear":
        return calculate_youngs_modulus_linear(
            force_n=force_n,
            displacement_mm=displacement_mm,
            indenter_radius_mm=indenter_radius_mm,
            tissue_thickness_mm=tissue_thickness_mm,
            poisson_ratio=poisson_ratio
        )
    else:
        return calculate_youngs_modulus_matlab(
            force_n=force_n,
            displacement_mm=displacement_mm,
            indenter_radius_mm=indenter_radius_mm,
            tissue_thickness_mm=tissue_thickness_mm,
            poisson_ratio=poisson_ratio,
            ratios=ratios
        )
