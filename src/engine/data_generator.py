"""
Realistic synthetic e-commerce data generator for Indian RTO/COD loss prevention.
Includes temporal non-stationarity, attack surges, and leak-free temporal splits.
"""
import random
import uuid
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from src.config import CONFIG, RAW_DATA_DIR, PROCESSED_DATA_DIR

# Indian Location Metadata Pools
CITIES_PINCODES = {
    # Tier 1 (Low base logistics failure)
    "Bengaluru": {"pincodes": ["560001", "560034", "560102", "560068"], "base_rto": 0.08, "tier": 1},
    "Mumbai": {"pincodes": ["400001", "400050", "400072", "400099"], "base_rto": 0.09, "tier": 1},
    "Delhi": {"pincodes": ["110001", "110020", "110085", "110092"], "base_rto": 0.11, "tier": 1},
    # Tier 2 (Moderate base logistics failure)
    "Jaipur": {"pincodes": ["302001", "302015", "302020"], "base_rto": 0.18, "tier": 2},
    "Lucknow": {"pincodes": ["226001", "226010", "226024"], "base_rto": 0.21, "tier": 2},
    # Tier 3/4 (High logistics failure / Serviceability issues)
    "Darbhanga": {"pincodes": ["846001", "846004", "846009"], "base_rto": 0.40, "tier": 3},
    "Murshidabad": {"pincodes": ["742101", "742149"], "base_rto": 0.44, "tier": 3},
    "Alwar": {"pincodes": ["301001", "301019"], "base_rto": 0.36, "tier": 3},
}

CATEGORIES = {
    "Fast Fashion": {"avg_price": 999, "rto_multiplier": 1.4},
    "Footwear": {"avg_price": 1899, "rto_multiplier": 1.3},
    "Electronics": {"avg_price": 4500, "rto_multiplier": 0.7},
    "Home & Kitchen": {"avg_price": 1200, "rto_multiplier": 0.9},
    "Beauty & Wellness": {"avg_price": 650, "rto_multiplier": 0.6},
}

VALID_ADDRESS_TEMPLATES = [
    "Flat {flat_no}, {building}, {street}, Near {landmark}",
    "House No. {flat_no}, 2nd Floor, {street}, Opposite {landmark}",
    "Plot {flat_no}, Sector {sector}, {street}, Behind {landmark}",
    "{flat_no}, Krishna Nagar Main Road, Near {landmark}",
]

SUSPICIOUS_ADDRESS_TEMPLATES = [
    "Near {landmark}",
    "{street} street only",
    "Call me when you reach {landmark}",
    "H.No {flat_no} asdfghjk qwerty",
    "Gali no 4",
    "Near Shiv Temple village post office",
]

LANDMARKS = ["Hanuman Temple", "City Hospital", "Pani Tanki", "Railway Station", "Primary School", "Bus Stand"]
STREETS = ["MG Road", "Station Road", "Gandhi Nagar", "Bypass Road", "Market Street", "Shanti Path"]


def generate_synthetic_transactions(num_records: int = 50000) -> pd.DataFrame:
    np.random.seed(CONFIG.random_seed)
    random.seed(CONFIG.random_seed)

    start_date = datetime(2026, 1, 1, 0, 0, 0)
    data = []

    # Syndicate network pool (Fraud Ring)
    syndicate_devices = [f"dev_syndicate_{i}" for i in range(15)]
    syndicate_ips = [f"103.21.24.{i}" for i in range(10)]
    syndicate_addresses = [
        "Near High School village area",
        "Plot 99 xyz colony near null",
        "Deliver at bus stand call first",
    ]

    for i in range(num_records):
        # 1. Temporal assignment
        random_seconds = random.randint(0, CONFIG.total_simulation_days * 86400)
        created_at = start_date + timedelta(seconds=random_seconds)
        day_of_sim = (created_at - start_date).total_seconds() / 86400

        # 2. Realistic Non-Stationary Attack Surge Model
        # Days 0-60 (Train): Baseline normal traffic (8% attack rate)
        # Days 61-75 (Validation): Emerging syndicate exploration (14% attack rate)
        # Days 76-90 (Held-out Test): Coordinated festive sale attack spike (26% attack rate)
        if day_of_sim < CONFIG.train_end_day:
            attack_prob = 0.08
        elif day_of_sim < CONFIG.val_end_day:
            attack_prob = 0.14
        else:
            attack_prob = 0.26

        is_attack = random.random() < attack_prob
        attack_type = "NORMAL"

        if is_attack:
            attack_type = random.choice(["GIBBERISH_ADDRESS", "FRAUD_RING", "IMPULSE_BINGE", "REMOTE_TIER3"])

        # 3. Geo & Location Selection
        if attack_type == "REMOTE_TIER3":
            city = random.choice(["Darbhanga", "Murshidabad", "Alwar"])
        else:
            city = random.choice(list(CITIES_PINCODES.keys()))

        pincode_info = CITIES_PINCODES[city]
        pincode = random.choice(pincode_info["pincodes"])

        # 4. Identity & Network Profile
        if attack_type == "FRAUD_RING":
            device_id = random.choice(syndicate_devices)
            ip_address = random.choice(syndicate_ips)
            user_id = f"user_syn_{random.randint(100, 999)}"
            phone = f"+9198{random.randint(10000000, 99999999)}"
            payment_method = "COD"
        else:
            device_id = f"dev_{uuid.uuid4().hex[:10]}"
            ip_address = f"106.51.{random.randint(1, 254)}.{random.randint(1, 254)}"
            user_id = f"user_{uuid.uuid4().hex[:8]}"
            phone = f"+91{random.choice(['98', '99', '88', '70', '63'])}{random.randint(10000000, 99999999)}"
            payment_method = random.choices(["COD", "PREPAID"], weights=[0.60, 0.40])[0]

        # 5. Cart & Category
        category_name = random.choice(list(CATEGORIES.keys()))
        cat_meta = CATEGORIES[category_name]

        if attack_type == "IMPULSE_BINGE":
            item_count = random.randint(4, 8)
            order_value = round(cat_meta["avg_price"] * item_count * random.uniform(1.2, 1.8), 2)
            payment_method = "COD"
        else:
            item_count = random.choices([1, 2, 3, 4], weights=[0.65, 0.22, 0.09, 0.04])[0]
            order_value = max(299.0, round(np.random.normal(cat_meta["avg_price"] * item_count, 250), 2))

        # 6. Address Text Synthesis
        if attack_type == "GIBBERISH_ADDRESS":
            raw_address = random.choice(SUSPICIOUS_ADDRESS_TEMPLATES).format(
                flat_no=random.randint(1, 999),
                street=random.choice(STREETS),
                landmark=random.choice(LANDMARKS),
                sector=random.randint(1, 60)
            )
        elif attack_type == "FRAUD_RING":
            raw_address = random.choice(syndicate_addresses)
        else:
            raw_address = random.choice(VALID_ADDRESS_TEMPLATES).format(
                flat_no=random.randint(1, 999),
                building=f"{random.choice(['Shree', 'Balaji', 'Sai', 'Green'])} Residency",
                street=random.choice(STREETS),
                landmark=random.choice(LANDMARKS),
                sector=random.randint(1, 60)
            )

        # 7. Ground Truth RTO Risk Engine
        risk_score = pincode_info["base_rto"] * cat_meta["rto_multiplier"]

        if payment_method == "PREPAID":
            risk_score *= 0.15
        else:
            risk_score *= 1.35

        # Attack Vector Penalties
        if attack_type == "GIBBERISH_ADDRESS":
            risk_score += 0.55
        elif attack_type == "FRAUD_RING":
            risk_score += 0.70
        elif attack_type == "IMPULSE_BINGE":
            risk_score += 0.45
        elif attack_type == "REMOTE_TIER3" and payment_method == "COD":
            risk_score += 0.30

        is_first_time = random.random() < 0.45
        if is_first_time and payment_method == "COD":
            risk_score += 0.12

        risk_score = np.clip(risk_score, 0.01, 0.98)
        is_rto = int(random.random() < risk_score)

        data.append({
            "order_id": f"ord_{i+1:06d}",
            "created_at": created_at,
            "user_id": user_id,
            "phone": phone,
            "device_id": device_id,
            "ip_address": ip_address,
            "delivery_address": raw_address,
            "city": city,
            "pincode": pincode,
            "pincode_tier": pincode_info["tier"],
            "category": category_name,
            "order_value_inr": order_value,
            "item_count": item_count,
            "payment_method": payment_method,
            "is_first_time_user": int(is_first_time),
            "attack_profile": attack_type,
            "is_rto": is_rto
        })

    df = pd.DataFrame(data)
    df = df.sort_values(by="created_at").reset_index(drop=True)
    return df


def execute_leak_free_split(df: pd.DataFrame):
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    raw_path = RAW_DATA_DIR / "transactions_raw.parquet"
    df.to_parquet(raw_path, index=False)
    print(f"[+] Saved raw dataset: {raw_path} ({len(df):,} records)")

    start_time = df["created_at"].min()
    train_cutoff = start_time + timedelta(days=CONFIG.train_end_day)
    val_cutoff = start_time + timedelta(days=CONFIG.val_end_day)

    train_df = df[df["created_at"] < train_cutoff].copy()
    val_df = df[(df["created_at"] >= train_cutoff) & (df["created_at"] < val_cutoff)].copy()
    test_df = df[df["created_at"] >= val_cutoff].copy()

    train_path = PROCESSED_DATA_DIR / "train.parquet"
    val_path = PROCESSED_DATA_DIR / "validation.parquet"
    test_path = PROCESSED_DATA_DIR / "held_out_test.parquet"

    train_df.to_parquet(train_path, index=False)
    val_df.to_parquet(val_path, index=False)
    test_df.to_parquet(test_path, index=False)

    print("\n=== Temporal Non-Stationary Split Summary ===")
    print(f"Train Set      (Days 00-60): {len(train_df):,} records | Baseline RTO Rate: {train_df['is_rto'].mean():.2%}")
    print(f"Validation Set (Days 61-75): {len(val_df):,} records | Emerging RTO Rate: {val_df['is_rto'].mean():.2%}")
    print(f"Held-Out Test  (Days 76-90): {len(test_df):,} records | Surge Spike RTO Rate: {test_df['is_rto'].mean():.2%}")


if __name__ == "__main__":
    print("[*] Generating non-stationary Indian e-commerce transaction stream...")
    dataset = generate_synthetic_transactions(num_records=50000)
    execute_leak_free_split(dataset)