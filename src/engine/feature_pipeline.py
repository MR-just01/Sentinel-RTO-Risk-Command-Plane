"""
Advanced Risk Feature Extraction Pipeline with fast single-row inference path.
"""
import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import OrdinalEncoder
from src.config import ARTIFACTS_DIR
from src.engine.address_parser import extract_address_features
from src.engine.graph_network import FraudRingSentinel
from src.engine.velocity import extract_all_velocities


class RiskFeaturePipeline:
    def __init__(self):
        self.encoder = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
        self.sentinel = FraudRingSentinel()
        self.categorical_cols = ["city", "category", "payment_method"]
        self.category_priors = {}
        self.pincode_priors = {}
        self.global_rto_prior = 0.25
        self.fitted = False

    def fit(self, df: pd.DataFrame):
        self.encoder.fit(df[self.categorical_cols])
        self.sentinel.update_graph(df)

        if "is_rto" in df.columns:
            self.global_rto_prior = float(df["is_rto"].mean())

            cat_stats = df.groupby("category")["is_rto"].agg(["count", "mean"])
            self.category_priors = (
                (cat_stats["count"] * cat_stats["mean"] + 40 * self.global_rto_prior) / (cat_stats["count"] + 40)
            ).to_dict()

            pin_stats = df.groupby("pincode")["is_rto"].agg(["count", "mean"])
            self.pincode_priors = (
                (pin_stats["count"] * pin_stats["mean"] + 25 * self.global_rto_prior) / (pin_stats["count"] + 25)
            ).to_dict()

        self.fitted = True
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self.fitted:
            raise RuntimeError("Pipeline must be fitted first.")

        # Fast single-row path (Used during online low-latency inference)
        if len(df) == 1:
            row = df.iloc[0]
            addr_text = str(row["delivery_address"])
            
            # Address signals
            addr_len = len(addr_text)
            word_cnt = len(addr_text.split())
            has_digits = int(any(c.isdigit() for c in addr_text))
            vowels = sum(1 for c in addr_text.lower() if c in "aeiou")
            total_letters = sum(1 for c in addr_text if c.isalpha())
            v_ratio = (vowels / total_letters) if total_letters > 0 else 0.0
            is_gibberish = int(v_ratio < 0.15 or v_ratio > 0.70)
            is_short = int(word_cnt < 4)

            # Tabular base
            val = float(row["order_value_inr"])
            items = max(int(row["item_count"]), 1)
            p_tier = int(row["pincode_tier"])
            is_first = int(row["is_first_time_user"])
            is_cod = int(row["payment_method"] == "COD")

            cat_prior = self.category_priors.get(row["category"], self.global_rto_prior)
            pin_prior = self.pincode_priors.get(str(row["pincode"]), self.global_rto_prior)

            # Categorical encoding
            cat_enc = self.encoder.transform([[row["city"], row["category"], row["payment_method"]]])[0]

            # Graph local degrees
            dev_node = f"DEV:{row['device_id']}"
            phone_node = f"PHONE:{row['phone']}"
            dev_deg = self.sentinel.graph.degree(dev_node) if self.sentinel.graph.has_node(dev_node) else 0
            phone_deg = self.sentinel.graph.degree(phone_node) if self.sentinel.graph.has_node(phone_node) else 0
            is_syn = int(dev_deg >= 3 or phone_deg >= 2)

            # Extract live sliding-window velocity from row if injected by API Gateway; fallback to 0.0
            def get_val(key: str, default: float = 0.0) -> float:
                if key in row and pd.notna(row[key]):
                    try:
                        return float(row[key])
                    except (ValueError, TypeError):
                        return default
                return default

            # Construct row
            data_row = {
                "order_value_inr": val,
                "item_count": items,
                "pincode_tier": p_tier,
                "is_first_time_user": is_first,
                "is_cod_payment": is_cod,
                "prior_category_rto": cat_prior,
                "prior_pincode_rto": pin_prior,
                "avg_item_price": val / items,
                "high_value_cod_flag": int(val > 2200 and is_cod == 1),
                "tier3_cod_risk": int(p_tier == 3 and is_cod == 1),
                "cod_first_time_risk": is_first * is_cod,
                "bad_address_cod_risk": int((is_short == 1 or is_gibberish == 1) and is_cod == 1),
                "syndicate_cod_risk": is_syn * is_cod,
                "cat_city": cat_enc[0],
                "cat_category": cat_enc[1],
                "cat_payment_method": cat_enc[2],
                "addr_char_length": addr_len,
                "addr_word_count": word_cnt,
                "addr_has_digits": has_digits,
                "addr_digit_count": sum(1 for c in addr_text if c.isdigit()),
                "addr_landmark_keyword_count": 1 if "near" in addr_text.lower() else 0,
                "addr_has_landmark": 1 if "near" in addr_text.lower() else 0,
                "addr_vowel_ratio": v_ratio,
                "addr_is_gibberish_flag": is_gibberish,
                "addr_is_too_short": is_short,
                
                # Active velocity counters dynamically preserved
                "velocity_device_id_1h": get_val("velocity_device_id_1h", 0.0),
                "velocity_device_id_24h": get_val("velocity_device_id_24h", 0.0),
                "velocity_phone_24h": get_val("velocity_phone_24h", 0.0),
                "velocity_phone_7d": get_val("velocity_phone_7d", 0.0),
                "velocity_ip_address_1h": get_val("velocity_ip_address_1h", 0.0),
                "velocity_ip_address_24h": get_val("velocity_ip_address_24h", 0.0),
                
                "graph_device_degree": dev_deg,
                "graph_phone_degree": phone_deg,
                "graph_is_syndicate_cluster": is_syn,
            }
            return pd.DataFrame([data_row])

        # Batch fallback for training/validation
        addr_feats = extract_address_features(df, address_col="delivery_address")
        
        # Only compute batch velocity if not already present in DataFrame
        vel_cols = [
            "velocity_device_id_1h", "velocity_device_id_24h",
            "velocity_phone_24h", "velocity_phone_7d",
            "velocity_ip_address_1h", "velocity_ip_address_24h"
        ]
        if all(c in df.columns for c in vel_cols):
            vel_feats = df[vel_cols].copy()
        else:
            vel_feats = extract_all_velocities(df)

        graph_feats = self.sentinel.extract_graph_signals(df)

        base_feats = pd.DataFrame(index=df.index)
        base_feats["order_value_inr"] = df["order_value_inr"].astype(float)
        base_feats["item_count"] = df["item_count"].astype(int)
        base_feats["pincode_tier"] = df["pincode_tier"].astype(int)
        base_feats["is_first_time_user"] = df["is_first_time_user"].astype(int)
        base_feats["is_cod_payment"] = (df["payment_method"] == "COD").astype(int)
        base_feats["prior_category_rto"] = df["category"].map(lambda c: self.category_priors.get(c, self.global_rto_prior))
        base_feats["prior_pincode_rto"] = df["pincode"].map(lambda p: self.pincode_priors.get(str(p), self.global_rto_prior))
        base_feats["avg_item_price"] = base_feats["order_value_inr"] / np.maximum(base_feats["item_count"], 1)
        base_feats["high_value_cod_flag"] = ((base_feats["order_value_inr"] > 2200) & (base_feats["is_cod_payment"] == 1)).astype(int)
        base_feats["tier3_cod_risk"] = ((base_feats["pincode_tier"] == 3) & (base_feats["is_cod_payment"] == 1)).astype(int)
        base_feats["cod_first_time_risk"] = (base_feats["is_first_time_user"] * base_feats["is_cod_payment"]).astype(int)
        base_feats["bad_address_cod_risk"] = (((addr_feats["addr_is_too_short"] == 1) | (addr_feats["addr_is_gibberish_flag"] == 1)) & (base_feats["is_cod_payment"] == 1)).astype(int)
        base_feats["syndicate_cod_risk"] = (graph_feats["graph_is_syndicate_cluster"] * base_feats["is_cod_payment"]).astype(int)

        encoded_cats = pd.DataFrame(
            self.encoder.transform(df[self.categorical_cols]),
            columns=[f"cat_{c}" for c in self.categorical_cols],
            index=df.index
        )
        return pd.concat([base_feats, encoded_cats, addr_feats, vel_feats, graph_feats], axis=1)

    def save(self, filepath=None):
        if filepath is None:
            filepath = ARTIFACTS_DIR / "feature_pipeline.joblib"
        joblib.dump(self, filepath)

    @classmethod
    def load(cls, filepath=None):
        if filepath is None:
            filepath = ARTIFACTS_DIR / "feature_pipeline.joblib"
        return joblib.load(filepath)