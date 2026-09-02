"""
Statistical Data Drift Monitor using Population Stability Index (PSI).
Monitors features to detect distribution shift prior to model degradation.
"""
import numpy as np
import pandas as pd

def calculate_psi(baseline: np.ndarray, current: np.ndarray, num_bins: int = 10) -> float:
    """
    Computes Population Stability Index (PSI).
    PSI < 0.10: No significant distribution change.
    PSI 0.10 - 0.25: Moderate shift; alert engineering.
    PSI > 0.25: Significant drift; trigger model retraining pipeline.
    """
    baseline = baseline[~np.isnan(baseline)]
    current = current[~np.isnan(current)]
    
    if len(baseline) == 0 or len(current) == 0:
        return 0.0

    # Determine bin edges from baseline percentiles
    quantiles = np.linspace(0, 100, num_bins + 1)
    bin_edges = np.percentile(baseline, quantiles)
    bin_edges[0] -= 1e-5
    bin_edges[-1] += 1e-5
    
    # Avoid zero counts with small epsilon Laplace smoothing
    eps = 1e-4
    b_counts, _ = np.histogram(baseline, bins=bin_edges)
    c_counts, _ = np.histogram(current, bins=bin_edges)
    
    b_dist = (b_counts + eps) / (len(baseline) + eps * num_bins)
    c_dist = (c_counts + eps) / (len(current) + eps * num_bins)
    
    psi_value = np.sum((c_dist - b_dist) * np.log(c_dist / b_dist))
    return float(round(psi_value, 4))


def evaluate_batch_drift(baseline_df: pd.DataFrame, current_df: pd.DataFrame) -> dict:
    """Evaluates PSI across critical continuous features."""
    monitored_features = ["order_value_inr", "pincode_tier"]
    report = {}
    
    for feat in monitored_features:
        if feat in baseline_df.columns and feat in current_df.columns:
            psi = calculate_psi(baseline_df[feat].values, current_df[feat].values)
            report[feat] = {
                "psi": psi,
                "status": "STABLE" if psi < 0.10 else ("MODERATE_DRIFT" if psi < 0.25 else "CRITICAL_DRIFT")
            }
            
    return report