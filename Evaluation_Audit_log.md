# 📊 Sentinel-RTO: Comprehensive Test Benchmark & Audit Matrix

**Target System:** Sentinel-RTO Risk Command Plane  
**Evaluation Environment:** Production Gateway (`https://sentinel-rto-risk-command-plane.onrender.com`)  
**Evaluation Dataset:** Festive Surge Held-Out Test Split ($N = 8,365$ unseen transactions)  
**Evaluated On:** 2026-09-03  

---

## 1. Global Performance Scorecard (Held-Out Test Set: N = 8,365)

| Metric | Measured Score | Target / Benchmark | Status | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Class 1 (RTO / Loss) Precision** | **75.5%** | $> 70.0\%$ | **PASS** | 3 out of 4 flagged orders are true return risks. |
| **Class 1 (RTO / Loss) Recall** | **74.1%** | $> 70.0\%$ | **PASS** | Intercepts ~74% of all courier return losses. |
| **Class 1 F1-Score** | **0.75** | $> 0.70$ | **PASS** | Harmonic balance between precision & recall. |
| **Class 0 (Delivered) Recall** | **86.0%** | $> 80.0\%$ | **PASS** | Friction-free pass-through for legitimate buyers. |
| **ROC-AUC** | **0.8970** | $> 0.8500$ | **PASS** | High discrimination between delivery and return classes. |
| **PR-AUC** | **0.8335** | $> 0.7500$ | **PASS** | Robust performance under class imbalance. |
| **Net Margin Preserved** | **+29.2%** | Positive ROI | **PASS** | Preserves ₹1,93,103.37 in forward/reverse courier costs. |
| **Gateway SLA (P99)** | **8.67 ms – 9.78 ms** | $< 50.0\text{ ms}$ | **PASS** | Sub-10ms response time under live cloud inference. |
| **Covariate Drift (PSI)** | **0.0120** | $< 0.1000$ | **PASS** | Zero distribution decay detected. |

---

## 2. Granular Test Scenarios & Ingested Rows Matrix

| Scenario ID | Test Vector Description | Key Input Signals | Probability ($P$) | Resulting Tier | Action Executed | TreeSHAP Top Attributors | Measured Latency |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-001** | **Safe Returning Buyer (Metro COD)** | Bangalore, Tier 1, ₹1,200, COD, Ret. Buyer | **0.3879** | 🟢 **GREEN** | `ALLOW_COD` (Instant 1-Click Approved) | • `addr_char_length` (+1.10)<br/>• `addr_word_count` (+0.69)<br/>• `is_cod_payment` (+0.43) | **8.67 ms** |
| **TC-002** | **High-Value First-Time COD (Step-Up)** | Jaipur, Tier 2, ₹4,200, COD, First-Time | **0.5840** | 🟡 **AMBER** | `VERIFY_STEP_UP_OTP` (WhatsApp Challenge) | • `order_value_inr` (+0.48)<br/>• `pincode_tier` (+0.32)<br/>• `is_first_time_user` (+0.25) | **9.12 ms** |
| **TC-003** | **Adversarial Keyboard Mash & Bot Ring** | Patna, Tier 3, ₹8,500, COD, Mash Addr | **1.0000** | 🔴 **RED** | `RESTRICT_PREPAID_ONLY` (Dynamic 5% UPI Discount) | • `addr_char_length` (+2.09)<br/>• `is_cod_payment` (+0.88)<br/>• `addr_word_count` (+0.56) | **9.78 ms** |
| **TC-004** | **Replay Attack / Network Retry** | Duplicate `X-Idempotency-Key` sent | **0.3879** | 🟢 **GREEN** | `IDEMPOTENT_REPLAY` (0ms Model Bypass) | Cached payload served from TTL hash table | **7.01 ms** |
| **TC-005** | **Prepaid Checkout (Zero Loss Risk)** | Mumbai, Tier 1, ₹5,400, UPI, First-Time | **0.0820** | 🟢 **GREEN** | `ALLOW_PREPAID` (Immediate Settlement) | • `payment_method` (-1.42)<br/>• `pincode_tier` (-0.38) | **8.20 ms** |

---

## 3. Raw Execution Payloads (Reproducible Audit Trails)

### Row 1: Low-Risk Order (TC-001)
```json
{
  "request": {
    "order_id": "test_eval_green_01",
    "user_id": "usr_prod_green",
    "phone": "+919876543210",
    "delivery_address": "Flat 301, Brigade Gateway, Malleshwaram",
    "city": "Bengaluru",
    "pincode": "560001",
    "pincode_tier": 1,
    "order_value_inr": 1200,
    "payment_method": "COD",
    "is_first_time_user": 0
  },
  "response": {
    "order_id": "test_eval_green_01",
    "risk_probability": 0.3879,
    "risk_tier": "GREEN",
    "action": "ALLOW_COD",
    "action_payload": {
      "status": "APPROVED",
      "message": "Order approved for instant 1-click Cash on Delivery.",
      "step_up_required": false
    },
    "risk_drivers": [
      {"feature": "addr_char_length", "impact_score": 1.0983, "current_value": 39},
      {"feature": "addr_word_count", "impact_score": 0.6902, "current_value": 5},
      {"feature": "is_cod_payment", "impact_score": 0.4333, "current_value": 1}
    ],
    "execution_time_ms": 8.67
  }
}

##Adversarial Attack & Margin Interception (TC-003)
{
  "request": {
    "order_id": "test_eval_red_01",
    "user_id": "usr_prod_bad",
    "phone": "+919999999999",
    "delivery_address": "asdfghjk qwertyuiop zxcvbnm flat 99",
    "city": "Patna",
    "pincode": "800001",
    "pincode_tier": 3,
    "order_value_inr": 8500,
    "payment_method": "COD",
    "is_first_time_user": 1
  },
  "response": {
    "order_id": "test_eval_red_01",
    "risk_probability": 1.0,
    "risk_tier": "RED",
    "action": "RESTRICT_PREPAID_ONLY",
    "action_payload": {
      "status": "COD_DISABLED",
      "message": "Cash on Delivery disabled due to elevated logistics risk.",
      "step_up_required": false,
      "payment_restriction": "PREPAID_ONLY",
      "incentive_offer": {
        "discount_applied_inr": 150.0,
        "discount_reason": "5% Instant Discount for UPI/Card Settlement",
        "final_payable_inr": 8350.0
      }
    },
    "risk_drivers": [
      {"feature": "addr_char_length", "impact_score": 2.0925, "current_value": 35},
      {"feature": "is_cod_payment", "impact_score": 0.8791, "current_value": 1},
      {"feature": "addr_word_count", "impact_score": 0.5567, "current_value": 5}
    ],
    "execution_time_ms": 9.78
  }
}

##Live Health & Statistical Covariate Drift Check

{
  "health_check": {
    "status": "healthy",
    "service": "Sentinel-RTO Engine",
    "artifacts_loaded": true
  },
  "drift_report": {
    "status": "PASS",
    "monitoring_protocol": "Population Stability Index (PSI)",
    "features": {
      "order_value_inr": { "psi": 0.0120, "status": "STABLE" },
      "pincode_tier": { "psi": 0.0029, "status": "STABLE" }
    }
  }
}