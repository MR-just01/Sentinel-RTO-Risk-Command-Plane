"""
Central configuration for Sentinel-RTO.
Includes filesystem paths, financial cost matrix parameters, and split thresholds.
"""
from pathlib import Path
from pydantic import BaseModel, Field

# Base Directory paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
ARTIFACTS_DIR = BASE_DIR / "artifacts"
MODELS_DIR = ARTIFACTS_DIR / "models"
EXPLAINER_DIR = ARTIFACTS_DIR / "explainer"


class BusinessCostMatrix(BaseModel):
    """
    Cost assumptions in Indian Rupees (INR) for cost-curve optimization.
    """
    # Logistics loss on an RTO order (Forward + Reverse courier fee + Packaging damage)
    rto_logistics_loss_inr: float = Field(default=220.0, description="Cost of an RTO event (FN)")
    
    # Merchant gross margin rate on legitimate orders
    merchant_gross_margin_rate: float = Field(default=0.30, description="30% profit margin")
    
    # Probability that a legitimate customer churns when friction (OTP / Prepay) is added
    friction_churn_rate: float = Field(default=0.25, description="25% abandon cart on friction")
    
    # Direct cost per automated OTP verification dispatch (WhatsApp / SMS)
    verification_dispatch_cost_inr: float = Field(default=0.35, description="Cost of OTP SMS/WhatsApp (TP/FP)")


class PipelineConfig(BaseModel):
    # Temporal splitting dates (Day 0 to Day 90)
    total_simulation_days: int = 90
    train_end_day: int = 60
    val_end_day: int = 75
    # Day 76 to 90 is strictly the held-out test split

    # Random seed for reproducibility
    random_seed: int = 42

    # Modeling hyperparameters
    target_column: str = "is_rto"
    time_column: str = "created_at"


# Global instances
COST_MATRIX = BusinessCostMatrix()
CONFIG = PipelineConfig()