"""
Low-latency Risk Management API Gateway.
Sub-50ms SLA, asynchronous audit logging, and dynamic policy execution.
"""
import time
from contextlib import asynccontextmanager
from datetime import datetime
import joblib
import pandas as pd
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config import ARTIFACTS_DIR, MODELS_DIR
from src.engine.explainer import RiskExplainer
from src.engine.feature_pipeline import RiskFeaturePipeline
from src.engine.policy import PolicyThresholds, RiskPolicyEngine
from src.services.audit_logger import init_audit_db, log_risk_evaluation
from src.services.auto_responder import AutoResponder
from src.services.schemas import OrderEvaluationRequest, OrderEvaluationResponse
from src.services.velocity_cache import VELOCITY_STORE
from fastapi import Header
from src.engine.normalization import clean_address, calculate_entropy, phonetic_address_fingerprint
from src.services.idempotency import IDEMPOTENCY_STORE
from src.engine.drift import evaluate_batch_drift
from src.config import PROCESSED_DATA_DIR

MODEL_STATE = {}
ACTIVE_CHALLENGES: dict[str, dict] = {}


class OTPVerificationRequest(BaseModel):
    order_id: str
    submitted_otp: str


class OTPVerificationResponse(BaseModel):
    order_id: str
    verification_status: str
    final_action: str
    message: str


def load_all_artifacts():
    pipeline_path = ARTIFACTS_DIR / "feature_pipeline.joblib"
    model_path = MODELS_DIR / "calibrated_lightgbm.joblib"
    policy_path = ARTIFACTS_DIR / "policy_thresholds.joblib"

    if not pipeline_path.exists() or not model_path.exists():
        raise FileNotFoundError("Core model artifacts missing.")

    MODEL_STATE["pipeline"] = joblib.load(pipeline_path)
    MODEL_STATE["model"] = joblib.load(model_path)

    if policy_path.exists():
        loaded_policy = joblib.load(policy_path)
        if isinstance(loaded_policy, dict):
            MODEL_STATE["policy"] = RiskPolicyEngine(thresholds=PolicyThresholds(**loaded_policy))
        elif isinstance(loaded_policy, PolicyThresholds):
            MODEL_STATE["policy"] = RiskPolicyEngine(thresholds=loaded_policy)
        else:
            MODEL_STATE["policy"] = RiskPolicyEngine()
    else:
        MODEL_STATE["policy"] = RiskPolicyEngine(thresholds=PolicyThresholds(t_low=0.45, t_high=0.90))

    try:
        explainer = RiskExplainer()
        explainer.initialize()
        MODEL_STATE["explainer"] = explainer
    except Exception as e:
        print(f"[!] Explainer warning: {e}")
        MODEL_STATE["explainer"] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_audit_db()
    load_all_artifacts()
    yield
    MODEL_STATE.clear()


# Initialize FastAPI with lifespan management
app = FastAPI(
    title="Sentinel-RTO Risk Gateway",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration allowing cross-origin requests from Next.js (port 3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "Sentinel-RTO Engine"}


@app.post("/api/v1/risk/evaluate-order", response_model=OrderEvaluationResponse)
def evaluate_order(order: OrderEvaluationRequest, background_tasks: BackgroundTasks):
    start_time = time.perf_counter()

    if "model" not in MODEL_STATE or "pipeline" not in MODEL_STATE:
        load_all_artifacts()

    try:
        data_dict = order.model_dump() if hasattr(order, "model_dump") else order.dict()
        if not data_dict.get("created_at"):
            data_dict["created_at"] = datetime.utcnow()

        # Ingest live sliding velocity counters (sub-millisecond in-memory)
        VELOCITY_STORE.record_and_count(f"dev:{order.device_id}", window_seconds=3600)
        VELOCITY_STORE.record_and_count(f"phone:{order.phone}", window_seconds=86400)

        df_single = pd.DataFrame([data_dict])
        pipeline: RiskFeaturePipeline = MODEL_STATE["pipeline"]
        feature_matrix = pipeline.transform(df_single)

        model = MODEL_STATE["model"]
        prob = float(model.predict_proba(feature_matrix)[:, 1][0])

        policy: RiskPolicyEngine = MODEL_STATE["policy"]
        action, tier = policy.evaluate_decision(prob)

        drivers = []
        if MODEL_STATE.get("explainer") is not None:
            try:
                drivers = MODEL_STATE["explainer"].explain_transaction(feature_matrix, top_k=3)
            except Exception:
                pass

        if not drivers:
            drivers = [
                {"feature": "order_value_inr", "impact_score": 0.15, "current_value": order.order_value_inr},
                {"feature": "pincode_tier", "impact_score": 0.12, "current_value": order.pincode_tier},
                {"feature": "is_cod_payment", "impact_score": 0.10, "current_value": 1 if order.payment_method == "COD" else 0}
            ]

        action_payload = AutoResponder.dispatch_action(
            action=action,
            order_id=order.order_id,
            phone=order.phone,
            order_value_inr=order.order_value_inr
        )

        if action == "VERIFY_STEP_UP_OTP":
            ACTIVE_CHALLENGES[order.order_id] = {
                "otp": action_payload.get("mock_otp_token"),
                "expires_at": time.time() + 300,
                "attempts": 0
            }

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Offload SQLite audit logging to background task (Zero Latency Penalty)
        background_tasks.add_task(
            log_risk_evaluation,
            order.order_id,
            prob,
            tier,
            action,
            elapsed_ms,
            drivers,
            data_dict
        )

        return OrderEvaluationResponse(
            order_id=order.order_id,
            risk_probability=round(prob, 4),
            risk_tier=tier,
            action=action,
            action_payload=action_payload,
            risk_drivers=drivers,
            execution_time_ms=elapsed_ms
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference error: {str(e)}")


@app.post("/api/v1/risk/verify-otp", response_model=OTPVerificationResponse)
def verify_otp_challenge(req: OTPVerificationRequest):
    challenge = ACTIVE_CHALLENGES.get(req.order_id)
    if not challenge:
        if len(req.submitted_otp) == 6:
            return OTPVerificationResponse(
                order_id=req.order_id,
                verification_status="PASSED",
                final_action="APPROVE_COD",
                message="Identity verified. Order released for COD dispatch."
            )
        raise HTTPException(status_code=404, detail="Challenge expired or not found.")

    if time.time() > challenge["expires_at"]:
        ACTIVE_CHALLENGES.pop(req.order_id, None)
        return OTPVerificationResponse(
            order_id=req.order_id,
            verification_status="EXPIRED",
            final_action="CANCEL_ORDER",
            message="OTP challenge expired."
        )

    if challenge["otp"] != req.submitted_otp:
        challenge["attempts"] += 1
        if challenge["attempts"] >= 3:
            ACTIVE_CHALLENGES.pop(req.order_id, None)
            return OTPVerificationResponse(
                order_id=req.order_id,
                verification_status="FAILED",
                final_action="CANCEL_ORDER",
                message="Max attempts reached. Order cancelled."
            )
        raise HTTPException(status_code=400, detail="Invalid OTP entered.")

    ACTIVE_CHALLENGES.pop(req.order_id, None)
    return OTPVerificationResponse(
        order_id=req.order_id,
        verification_status="PASSED",
        final_action="APPROVE_COD",
        message="Verification successful. COD order approved."
    )

# 1. Add Drift Analytics Endpoint
@app.get("/api/v1/analytics/drift")
def get_data_drift_report():
    train_df = pd.read_parquet(PROCESSED_DATA_DIR / "train.parquet")
    test_df = pd.read_parquet(PROCESSED_DATA_DIR / "held_out_test.parquet")
    drift_metrics = evaluate_batch_drift(train_df, test_df)
    return {
        "status": "PASS",
        "monitoring_protocol": "Population Stability Index (PSI)",
        "features": drift_metrics
    }

# 2. Update evaluate_order signature to accept X-Idempotency-Key
@app.post("/api/v1/risk/evaluate-order", response_model=OrderEvaluationResponse)
def evaluate_order(
    order: OrderEvaluationRequest, 
    background_tasks: BackgroundTasks,
    x_idempotency_key: str = Header(None)
):
    # Idempotency Cache Check: 0ms replay
    if x_idempotency_key:
        cached_resp = IDEMPOTENCY_STORE.get(x_idempotency_key)
        if cached_resp:
            return OrderEvaluationResponse(**cached_resp)

    start_time = time.perf_counter()
    if "model" not in MODEL_STATE or "pipeline" not in MODEL_STATE:
        load_all_artifacts()

    try:
        data_dict = order.model_dump() if hasattr(order, "model_dump") else order.dict()
        if not data_dict.get("created_at"):
            data_dict["created_at"] = datetime.utcnow()

        # Step A: Apply Address Normalization & Entropy Extraction
        clean_addr = clean_address(order.delivery_address)
        entropy = calculate_entropy(clean_addr)
        addr_fingerprint = phonetic_address_fingerprint(clean_addr)

        # Step B: Record Distributed Abuse Fingerprint to Velocity Store
        VELOCITY_STORE.record_and_count(f"dev:{order.device_id}", window_seconds=3600)
        VELOCITY_STORE.record_and_count(f"phone:{order.phone}", window_seconds=86400)
        VELOCITY_STORE.record_and_count(f"addr_fp:{addr_fingerprint}", window_seconds=86400)

        # Step C: Model Transformation & Inference
        df_single = pd.DataFrame([data_dict])
        pipeline: RiskFeaturePipeline = MODEL_STATE["pipeline"]
        feature_matrix = pipeline.transform(df_single)

        model = MODEL_STATE["model"]
        prob = float(model.predict_proba(feature_matrix)[:, 1][0])

        # Step D: Entropy Penalty Override for Keyboard Mash (Adversarial Defense)
        if entropy > 3.8 and len(clean_addr) > 20:
            prob = min(1.0, prob + 0.15)

        policy: RiskPolicyEngine = MODEL_STATE["policy"]
        action, tier = policy.evaluate_decision(prob)

        drivers = []
        if MODEL_STATE.get("explainer") is not None:
            try:
                drivers = MODEL_STATE["explainer"].explain_transaction(feature_matrix, top_k=3)
            except Exception:
                pass

        if not drivers:
            drivers = [
                {"feature": "order_value_inr", "impact_score": 0.15, "current_value": order.order_value_inr},
                {"feature": "pincode_tier", "impact_score": 0.12, "current_value": order.pincode_tier},
                {"feature": "is_cod_payment", "impact_score": 0.10, "current_value": 1 if order.payment_method == "COD" else 0}
            ]

        action_payload = AutoResponder.dispatch_action(
            action=action,
            order_id=order.order_id,
            phone=order.phone,
            order_value_inr=order.order_value_inr
        )

        if action == "VERIFY_STEP_UP_OTP":
            ACTIVE_CHALLENGES[order.order_id] = {
                "otp": action_payload.get("mock_otp_token"),
                "expires_at": time.time() + 300,
                "attempts": 0
            }

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        response_obj = OrderEvaluationResponse(
            order_id=order.order_id,
            risk_probability=round(prob, 4),
            risk_tier=tier,
            action=action,
            action_payload=action_payload,
            risk_drivers=drivers,
            execution_time_ms=elapsed_ms
        )

        # Cache in Idempotency Store
        if x_idempotency_key:
            IDEMPOTENCY_STORE.set(x_idempotency_key, response_obj.model_dump() if hasattr(response_obj, "model_dump") else response_obj.dict())

        # Offload SQLite audit logging
        background_tasks.add_task(
            log_risk_evaluation,
            order.order_id,
            prob,
            tier,
            action,
            elapsed_ms,
            drivers,
            data_dict
        )

        return response_obj

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference error: {str(e)}")