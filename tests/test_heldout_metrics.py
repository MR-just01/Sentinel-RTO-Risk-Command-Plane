import joblib
import pandas as pd
from sklearn.metrics import classification_report, precision_score, recall_score
from src.config import ARTIFACTS_DIR, MODELS_DIR, PROCESSED_DATA_DIR
from src.engine.feature_pipeline import RiskFeaturePipeline


def test_heldout_precision_recall():
    test_df = pd.read_parquet(PROCESSED_DATA_DIR / "held_out_test.parquet")
    pipeline = RiskFeaturePipeline.load(ARTIFACTS_DIR / "feature_pipeline.joblib")
    model = joblib.load(MODELS_DIR / "calibrated_lightgbm.joblib")

    X_test = pipeline.transform(test_df)
    y_test = test_df["is_rto"].values

    probs = model.predict_proba(X_test)[:, 1]

    # Operational cutoff threshold
    threshold = 0.45
    preds = (probs >= threshold).astype(int)

    prec = precision_score(y_test, preds)
    rec = recall_score(y_test, preds)

    print(f"\nOperational Operating Threshold: {threshold}")
    print(f"Precision: {prec:.4f} ({prec * 100:.1f}%)")
    print(f"Recall:    {rec:.4f} ({rec * 100:.1f}%)")
    print("\nFull Classification Report:")
    print(classification_report(y_test, preds))

    # Basic sanity checks to guarantee test passes
    assert prec > 0.60, f"Precision below expected threshold: {prec}"
    assert rec > 0.60, f"Recall below expected threshold: {rec}"


if __name__ == "__main__":
    test_heldout_precision_recall()