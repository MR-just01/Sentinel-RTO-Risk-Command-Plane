"""
Held-Out Test Partition Benchmark Suite.
Verifies PR-AUC, ROC-AUC, and financial savings on the unseen surge dataset.
"""
import joblib
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score
from src.config import ARTIFACTS_DIR, MODELS_DIR, PROCESSED_DATA_DIR
from src.engine.feature_pipeline import RiskFeaturePipeline
from src.engine.policy import RiskPolicyEngine


def test_held_out_generalization_and_savings():
    # 1. Load unseen test set and serialized models
    test_df = pd.read_parquet(PROCESSED_DATA_DIR / "held_out_test.parquet")
    pipeline = RiskFeaturePipeline.load(ARTIFACTS_DIR / "feature_pipeline.joblib")
    model = joblib.load(MODELS_DIR / "calibrated_lightgbm.joblib")
    policy = RiskPolicyEngine.load(ARTIFACTS_DIR / "policy_thresholds.joblib")

    # 2. Extract features and predict probabilities
    X_test = pipeline.transform(test_df)
    y_test = test_df["is_rto"].values
    order_values = test_df["order_value_inr"].values
    y_prob = model.predict_proba(X_test)[:, 1]

    # 3. Evaluate Statistical Metrics
    roc_auc = roc_auc_score(y_test, y_prob)
    pr_auc = average_precision_score(y_test, y_prob)

    print(f"\n[+] Held-Out Test Set Evaluation:")
    print(f"    - ROC-AUC: {roc_auc:.4f}")
    print(f"    - PR-AUC:  {pr_auc:.4f}")

    assert roc_auc >= 0.85, f"ROC-AUC ({roc_auc:.4f}) dropped below standard threshold."
    assert pr_auc >= 0.75, f"PR-AUC ({pr_auc:.4f}) dropped below standard threshold."

    # 4. Evaluate Financial Cost Savings on Unseen Surge Period
    baseline_loss = (y_test == 1).sum() * 220.0
    managed_loss = policy.calculate_business_cost(
        y_true=y_test,
        y_prob=y_prob,
        order_values=order_values,
        t_low=policy.thresholds.t_low,
        t_high=policy.thresholds.t_high
    )

    savings_inr = baseline_loss - managed_loss
    savings_pct = (savings_inr / baseline_loss) * 100

    print(f"    - Unprotected Baseline Loss : INR {baseline_loss:,.2f}")
    print(f"    - Sentinel-RTO Loss         : INR {managed_loss:,.2f}")
    print(f"    - Net Margin Saved          : INR {savings_inr:,.2f} ({savings_pct:.1f}%)")

    assert savings_inr > 0, "Policy caused a net financial loss on the test set!"