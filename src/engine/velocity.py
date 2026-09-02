"""
Time-decayed rolling velocity feature engine.
Calculates historical order frequency across identity vectors without future leakage.
"""
import pandas as pd


def compute_rolling_velocity(
    df: pd.DataFrame,
    time_col: str = "created_at",
    entity_col: str = "device_id",
    windows: dict[str, str] = {"1h": "1h", "24h": "24h", "7d": "7d"}
) -> pd.DataFrame:
    """
    Computes expanding/rolling order counts for an entity over defined time windows.
    Ensures zero future leakage using closed='left' windowing.
    """
    # Create indexed copy sorted by time
    temp_df = df[[time_col, entity_col]].copy()
    temp_df["order_count_marker"] = 1
    temp_df = temp_df.sort_values(by=time_col)

    velocity_features = pd.DataFrame(index=df.index)

    for win_name, win_duration in windows.items():
        # Rolling count per entity within lookback window
        # Closed='left' ensures the current transaction is NOT counted in its own history
        counts = (
            temp_df.set_index(time_col)
            .groupby(entity_col)["order_count_marker"]
            .rolling(win_duration, closed="left")
            .sum()
            .reset_index()
        )
        
        col_name = f"velocity_{entity_col}_{win_name}"
        velocity_features[col_name] = counts["order_count_marker"].fillna(0).values

    return velocity_features


def extract_all_velocities(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extracts multi-entity velocity counters across Device, Phone, and IP.
    """
    device_vel = compute_rolling_velocity(df, entity_col="device_id", windows={"1h": "1h", "24h": "24h"})
    phone_vel = compute_rolling_velocity(df, entity_col="phone", windows={"24h": "24h", "7d": "7d"})
    ip_vel = compute_rolling_velocity(df, entity_col="ip_address", windows={"1h": "1h", "24h": "24h"})

    return pd.concat([device_vel, phone_vel, ip_vel], axis=1)