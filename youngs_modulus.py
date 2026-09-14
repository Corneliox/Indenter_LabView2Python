"""
Young's Modulus & Elasticity Analysis Module
Implements Effective Young's Modulus formulas from proposal document:
- Hayes, Keer et al. (1972)
- Zheng & Mak (1999)
- Three-stage Elasticity E1, E2, E3
"""

import numpy as np
from typing import Optional


def calculate_hayes_kappa(a_over_h: float, nu: float = 0.45) -> float:
    """
    Geometric scaling factor kappa(a/h, nu) for cylindrical flat-ended indenter
    on an elastic layer bounded to a rigid substrate (Hayes et al. 1972).
    Empirical approximation for nu = 0.45:
    kappa ~ 1.0 + 0.65 * (a/h) + 0.20 * (a/h)^2
    """
    return 1.0 + 0.65 * a_over_h + 0.20 * (a_over_h ** 2)


def calculate_effective_youngs_modulus(
    force_n: np.ndarray,
    displacement_mm: np.ndarray,
    indenter_radius_mm: float = 4.5,
    tissue_thickness_mm: float = 12.0,
    poisson_ratio: float = 0.45
) -> dict[str, float]:
    """
    Computes Effective Young's Modulus across 3 loading stages (E1, E2, E3).
    Formula:
        E = [(1 - nu^2) / (2 * a * kappa)] * (dP / dw)
    Where:
        nu = Poisson's ratio (0.45)
        a  = Indenter radius in meters (4.5 mm = 0.0045 m)
        w  = Indentation depth in meters
        P  = Indentation force in Newtons
        kappa = Hayes correction factor
        E is in Pascals (Pa), converted to kiloPascals (kPa).
    """
    # Ensure inputs are sorted by displacement and within loading phase
    if len(displacement_mm) < 10 or len(force_n) < 10:
        return {"E1_kPa": 0.0, "E2_kPa": 0.0, "E3_kPa": 0.0, "E_mean_kPa": 0.0}

    # Filter for increasing displacement (loading phase only)
    max_disp_idx = np.argmax(displacement_mm)
    disp_loading = displacement_mm[:max_disp_idx + 1]
    force_loading = force_n[:max_disp_idx + 1]

    # Convert units to SI (meters and Newtons)
    a_m = indenter_radius_mm * 1e-3
    h_m = tissue_thickness_mm * 1e-3
    w_m = disp_loading * 1e-3
    p_n = force_loading

    a_over_h = a_m / h_m
    kappa = calculate_hayes_kappa(a_over_h, poisson_ratio)
    geometry_factor = (1.0 - (poisson_ratio ** 2)) / (2.0 * a_m * kappa)

    # Segment into 3 displacement ranges: E1 (0-33%), E2 (33-66%), E3 (66-100%)
    max_w = np.max(w_m)
    if max_w <= 1e-5:
        return {"E1_kPa": 0.0, "E2_kPa": 0.0, "E3_kPa": 0.0, "E_mean_kPa": 0.0}

    def fit_slope(w_sub, p_sub):
        if len(w_sub) < 3:
            return 0.0
        # Linear regression dP / dw
        slope, _ = np.polyfit(w_sub, p_sub, 1)
        return max(0.0, slope)

    mask_e1 = (w_m >= 0.05 * max_w) & (w_m <= 0.35 * max_w)
    mask_e2 = (w_m > 0.35 * max_w) & (w_m <= 0.70 * max_w)
    mask_e3 = (w_m > 0.70 * max_w) & (w_m <= 1.00 * max_w)

    slope_e1 = fit_slope(w_m[mask_e1], p_n[mask_e1]) if np.any(mask_e1) else 0.0
    slope_e2 = fit_slope(w_m[mask_e2], p_n[mask_e2]) if np.any(mask_e2) else 0.0
    slope_e3 = fit_slope(w_m[mask_e3], p_n[mask_e3]) if np.any(mask_e3) else 0.0
    slope_all = fit_slope(w_m, p_n)

    # Convert Pa to kPa
    e1_kpa = (geometry_factor * slope_e1) / 1000.0
    e2_kpa = (geometry_factor * slope_e2) / 1000.0
    e3_kpa = (geometry_factor * slope_e3) / 1000.0
    e_mean_kpa = (geometry_factor * slope_all) / 1000.0

    return {
        "E1_kPa": round(float(e1_kpa), 2),
        "E2_kPa": round(float(e2_kpa), 2),
        "E3_kPa": round(float(e3_kpa), 2),
        "E_mean_kPa": round(float(e_mean_kpa), 2)
    }
