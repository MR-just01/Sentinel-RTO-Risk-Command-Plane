"""
SQLite-backed Audit Logger for Compliance and Defense Tracking.
"""
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import numpy as np

DB_PATH = Path("artifacts/risk_audit_log.db")


def custom_json_serializer(obj):
    """Encodes NumPy scalars and datetime objects for standard JSON serialization."""
    if isinstance(obj, (np.integer, np.int32, np.int64)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float32, np.float64)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


def init_audit_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS risk_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                risk_probability REAL NOT NULL,
                risk_tier TEXT NOT NULL,
                action TEXT NOT NULL,
                execution_time_ms REAL NOT NULL,
                shap_factors TEXT NOT NULL,
                raw_payload TEXT NOT NULL
            )
        """)
        conn.commit()


def log_risk_evaluation(
    order_id: str,
    risk_prob: float,
    risk_tier: str,
    action: str,
    execution_time_ms: float,
    shap_factors: list[dict],
    raw_payload: dict
):
    init_audit_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO risk_audit_log (
                order_id, timestamp, risk_probability, risk_tier,
                action, execution_time_ms, shap_factors, raw_payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(order_id),
            datetime.utcnow().isoformat(),
            float(risk_prob),
            str(risk_tier),
            str(action),
            float(execution_time_ms),
            json.dumps(shap_factors, default=custom_json_serializer),
            json.dumps(raw_payload, default=custom_json_serializer)
        ))
        conn.commit()