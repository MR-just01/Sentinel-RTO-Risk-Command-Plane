"""
Financial Cost-Matrix Threshold Optimizer & Decision Router.
Optimizes operational decision boundaries on validation data using real INR economics.
"""
import joblib
import numpy as np
import pandas as pd
from pydantic import BaseModel
from src.config import ARTIFACTS_DIR, COST_MATRIX, MODELS_DIR, PROCESSED_DATA_DIR
from src.engine.feature_pipeline import RiskFeaturePipeline


class PolicyThresholds(BaseModel):
    t_low: float = 0.22   # Threshold between ALLOW (Green) and STEP_UP (Amber)
    t_high: float = 0.68  # Threshold between STEP_UP (Amber) and BLOCK_COD (Red)
    min_net_cost_inr: float = 0.0
    baseline_cost_inr: float = 0.0
    net_savings_inr: float = 0.0
    net_savings_pct: float = 0.0


class RiskPolicyEngine:
    def __init__(self, thresholds: PolicyThresholds = None):
        self.thresholds = thresholds or PolicyThresholds()

    @staticmethod
    def calculate_business_cost(
        y_true: np.ndarray,
        y_prob: np.ndarray,
        order_values: np.ndarray,
        t_low: float,
        t_high: float
    ) -> float:
        """
        Calculates total INR loss across a cohort given two thresholds:
        - Zone Green (p < t_low): ALLOW COD
            * FN (y=1): Merchant loses ₹220 logistics.
            * TN (y=0): ₹0 loss (full margin realized).
        - Zone Amber (t_low <= p < t_high): STEP-UP OTP / ₹49 Deposit
            * Direct cost: ₹0.35 OTP dispatch.
            * Legitimate buyers (y=0): 25% abandon cart on friction (loss = 0.25 * 30% * order_value).
            * Fraudsters (y=1): 90% get deterred by OTP, 10% bypass (loss = 0.10 * ₹220).
        - Zone Red (p >= t_high): BLOCK COD / FORCE PREPAY
            * TP (y=1): Merchant saves ₹220 (loss = ₹0).
            * FP (y=0): Merchant loses 100% margin on lost sale (loss = 0.30 * order_value).
        """
        total_cost = 0.0

        # Zone Masks
        green_mask = y_prob < t_low
        amber_mask = (y_prob >= t_low) & (y_prob < t_high)
        red_mask = y_prob >= t_high

        # 1. Green Zone Costs
        # False Negatives (RTO happened with zero friction)
        fn_green = (y_true == 1) & green_mask
        total_cost += np.sum(fn_green) * COST_MATRIX.rto_logistics_loss_inr

        # 2. Amber Zone Costs (Verification step-up)
        amber_count = np.sum(amber_mask)
        total_cost += amber_count * COST_MATRIX.verification_dispatch_cost_inr
        
        # Genuine users dropping out due to friction
        fp_amber = (y_true == 0) & amber_mask
        total_cost += np.sum(order_values[fp_amber] * COST_MATRIX.merchant_gross_margin_rate * COST_MATRIX.friction_churn_rate)
        
        # Fraudsters slipping past OTP
        fn_amber = (y_true == 1) & amber_mask
        total_cost += np.sum(fn_amber) * (0.10 * COST_MATRIX.rto_logistics_loss_inr)

        # 3. Red Zone Costs (Outright COD Block)
        # False Positives: Genuine customers turned away
        fp_red = (y_true == 0) & red_mask
        total_cost += np.sum(order_values[fp_red] * COST_MATRIX.merchant_gross_margin_rate)

        return float(total_cost)

    def optimize_thresholds(self, val_df: pd.DataFrame, pipeline: RiskFeaturePipeline, model) -> PolicyThresholds:
        """
        Grid-searches the 2D threshold surface on the validation split
        to find the global financial loss minimum.
        """
        print("[*] Optimizing financial cost surface on Validation Split...")
        X_val = pipeline.transform(val_df)
        y_val = val_df["is_rto"].values
        order_values = val_df["order_value_inr"].values
        y_prob = model.predict_proba(X_val)[:, 1]

        # Baseline: Merchant has zero AI Risk Manager (allows 100% COD orders)
        baseline_cost = np.sum(y_val == 1) * COST_MATRIX.rto_logistics_loss_inr

        best_cost = float("inf")
        best_t_low = 0.20
        best_t_high = 0.70

        # Grid search with granularity
        t_low_candidates = np.linspace(0.10, 0.45, 36)
        t_high_candidates = np.linspace(0.50, 0.90, 41)

        for tl in t_low_candidates:
            for th in t_high_candidates:
                if tl >= th:
                    continue
                cost = self.calculate_business_cost(y_val, y_prob, order_values, tl, th)
                if cost < best_cost:
                    best_cost = cost
                    best_t_low = round(float(tl), 3)
                    best_t_high = round(float(th), 3)

        savings_inr = baseline_cost - best_cost
        savings_pct = (savings_inr / baseline_cost) * 100

        self.thresholds = PolicyThresholds(
            t_low=best_t_low,
            t_high=best_t_high,
            min_net_cost_inr=round(best_cost, 2),
            baseline_cost_inr=round(baseline_cost, 2),
            net_savings_inr=round(savings_inr, 2),
            net_savings_pct=round(savings_pct, 2)
        )
        return self.thresholds

    def evaluate_decision(self, risk_probability: float) -> tuple[str, str]:
        """
        Maps a calibrated risk score to an autonomous operational decision.
        """
        if risk_probability < self.thresholds.t_low:
            return "ALLOW_COD", "GREEN"
        elif risk_probability < self.thresholds.t_high:
            return "VERIFY_STEP_UP_OTP", "AMBER"
        else:
            return "RESTRICT_PREPAID_ONLY", "RED"

    def save(self, filepath=None):
        if filepath is None:
            filepath = ARTIFACTS_DIR / "policy_thresholds.joblib"
        # Dump as pure dictionary to prevent pickle module-namespace mismatch
        data = {
            "t_low": float(self.thresholds.t_low),
            "t_high": float(self.thresholds.t_high),
            "min_net_cost_inr": float(self.thresholds.min_net_cost_inr),
            "baseline_cost_inr": float(self.thresholds.baseline_cost_inr),
            "net_savings_inr": float(self.thresholds.net_savings_inr),
            "net_savings_pct": float(self.thresholds.net_savings_pct)
        }
        joblib.dump(data, filepath)
        print(f"[+] Saved Policy Thresholds dict to {filepath}")

    @classmethod
    def load(cls, filepath=None):
        if filepath is None:
            filepath = ARTIFACTS_DIR / "policy_thresholds.joblib"
        raw_data = joblib.load(filepath)
        if isinstance(raw_data, dict):
            thresholds = PolicyThresholds(**raw_data)
        elif hasattr(raw_data, "t_low"):
            thresholds = raw_data
        else:
            thresholds = PolicyThresholds(t_low=0.45, t_high=0.90)
        return cls(thresholds=thresholds)


if __name__ == "__main__":
    # Load validation data and trained models
    val_data = pd.read_parquet(PROCESSED_DATA_DIR / "validation.parquet")
    pipe = RiskFeaturePipeline.load()
    cal_model = joblib.load(MODELS_DIR / "calibrated_lightgbm.joblib")

    engine = RiskPolicyEngine()
    results = engine.optimize_thresholds(val_data, pipe, cal_model)
    engine.save()

    print("\n" + "=" * 60)
    print("=== Financial Policy Optimization (Validation Split) ===")
    print(f"Optimal T_Low  (Green -> Amber Boundary) : {results.t_low:.3f}")
    print(f"Optimal T_High (Amber -> Red Boundary)   : {results.t_high:.3f}")
    print(f"Baseline Unprotected RTO Cost          : INR {results.baseline_cost_inr:,.2f}")
    print(f"Sentinel-RTO Net Business Cost         : INR {results.min_net_cost_inr:,.2f}")
    print(f"Net Margin Saved for Merchant          : INR {results.net_savings_inr:,.2f} ({results.net_savings_pct:.1f}%)")
    print("=" * 60)