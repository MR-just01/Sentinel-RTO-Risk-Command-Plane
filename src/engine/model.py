"""
Regularized LightGBM Model with Platt Probability Calibration.
"""
import joblib
import lightgbm as lgb
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import average_precision_score, roc_auc_score

from src.config import CONFIG, MODELS_DIR, PROCESSED_DATA_DIR
from src.engine.feature_pipeline import RiskFeaturePipeline


def train_and_calibrate_engine():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    print("[*] Loading temporal dataset splits...")
    train_df = pd.read_parquet(PROCESSED_DATA_DIR / "train.parquet")
    val_df = pd.read_parquet(PROCESSED_DATA_DIR / "validation.parquet")
    test_df = pd.read_parquet(PROCESSED_DATA_DIR / "held_out_test.parquet")

    print("[*] Fitting Feature Pipeline...")
    pipeline = RiskFeaturePipeline()
    pipeline.fit(train_df)
    pipeline.save()

    print("[*] Transforming feature matrices...")
    X_train = pipeline.transform(train_df)
    y_train = train_df[CONFIG.target_column].values

    X_val = pipeline.transform(val_df)
    y_val = val_df[CONFIG.target_column].values

    X_test = pipeline.transform(test_df)
    y_test = test_df[CONFIG.target_column].values

    print(f"[*] Training Regularized LightGBM on {len(X_train):,} records ({X_train.shape[1]} features)...")
    base_lgb = lgb.LGBMClassifier(
        n_estimators=350,
        learning_rate=0.03,
        num_leaves=31,
        max_depth=6,
        min_child_samples=30,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=2.0,
        random_state=CONFIG.random_seed,
        n_jobs=-1,
        verbose=-1
    )
    base_lgb.fit(X_train, y_train)

    print("[*] Calibrating probabilities via Platt Scaling...")
    calibrated_model = CalibratedClassifierCV(
        estimator=base_lgb,
        method="sigmoid",
        cv="prefit"
    )
    calibrated_model.fit(X_val, y_val)

    # Evaluate on Unseen Held-Out Test Set
    y_pred_proba = calibrated_model.predict_proba(X_test)[:, 1]
    roc_auc = roc_auc_score(y_test, y_pred_proba)
    pr_auc = average_precision_score(y_test, y_pred_proba)

    print("\n" + "=" * 56)
    print("=== Model Evaluation (Held-Out Unseen Test Partition) ===")
    print(f"ROC-AUC Score : {roc_auc:.4f}")
    print(f"PR-AUC Score  : {pr_auc:.4f}")
    print("=" * 56)

    joblib.dump(calibrated_model, MODELS_DIR / "calibrated_lightgbm.joblib")
    joblib.dump(base_lgb, MODELS_DIR / "base_lightgbm.joblib")
    print(f"[+] Serialized model artifacts to {MODELS_DIR}")


if __name__ == "__main__":
    train_and_calibrate_engine()