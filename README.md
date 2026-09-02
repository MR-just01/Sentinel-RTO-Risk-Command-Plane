# Sentinel-RTO: Real-Time Autonomous Risk & Policy Execution Gateway

> Production-grade FinTech risk engine designed for e-commerce checkout protection, mitigating Cash-on-Delivery (COD) Return-to-Origin (RTO) courier loss through real-time ML inference, TreeSHAP attribution, and closed-loop auto-responders. Built for the **Razorpay Buildathon**.

---

## 1. Problem Statement & Economics

In Indian e-commerce, COD Return-to-Origin (RTO) rates hover between **20%–35%**, costing merchants reverse courier logistics (₹140–₹220 per failed shipment), locked inventory, and operational overhead. 

Standard rule-based systems rely on binary PIN code blocks that choke genuine buyer conversion (Gross Merchandise Value loss). **Sentinel-RTO** implements a cost-sensitive, three-tier probabilistic engine that minimizes total economic loss:

$$\text{Loss} = C_{\text{courier}} \times P(\text{RTO}) + C_{\text{friction}} \times (1 - P(\text{RTO}))$$

### Empirical Performance (Held-Out Test Set: Days 76–90 Festive Surge)
* **Net Margin Recovered:** **+29.2%** (₹1,93,103.37 net recovery over baseline)
* **Discrimination (ROC-AUC):** **0.8970**
* **Precision-Recall (PR-AUC):** **0.8335** (Minority class robust)
* **Inference Latency:** **14 ms – 32 ms** (Strictly within the <50 ms checkout budget)

---

## 2. System Architecture

[ CLIENT / CHECKOUT ]
                                      │
                        POST /api/v1/risk/evaluate-order
                        (Header: X-Idempotency-Key)
                                      │
                                      ▼
                     ┌─────────────────────────────────┐
                     │   Idempotency & Replay Cache    │──► (Match: 0ms Replay)
                     └─────────────────────────────────┘
                                      │ (Miss)
                                      ▼
                     ┌─────────────────────────────────┐
                     │ Anti-Evasion Normalization Hub  │
                     │  • Canonical Token Standardizer │
                     │  • Shannon Entropy Filter       │
                     │  • Phonetic Soundex Clustered   │
                     └─────────────────────────────────┘
                                      │
                                      ▼
                     ┌─────────────────────────────────┐
                     │ Calibrated LightGBM Inference   │
                     │   + Native C++ TreeSHAP Engine  │
                     └─────────────────────────────────┘
                                      │
                 ┌────────────────────┴────────────────────┐
                 ▼                                         ▼
       [ Risk Probability P ]                     [ SHAP Attribution ]
                 │                                         │
                 ▼                                         │
   ┌───────────────────────────┐                           │
   │   Risk Policy Engine      │                           │
   │  • GREEN (P < 0.45)       │                           │
   │  • AMBER (0.45 <= P < 0.9)│                           │
   │  • RED   (P >= 0.90)      │                           │
   └───────────────────────────┘                           │
                 │                                         │
                 ├───────────────────┬─────────────────────┘
                 ▼                   ▼
    ┌─────────────────────────┐ ┌──────────────────────────┐
    │ Storefront Auto-Responder│ │  Async Audit Logger      │
    │ • Green: 1-Click COD    │ │  • Background SQLite Log  │
    │ • Amber: WhatsApp OTP   │ │  • PSI Drift Monitoring   │
    │ • Red:   5% UPI Discount│ │                           │
    └─────────────────────────┘ └──────────────────────────┘


    ## 3. Core Technical Defenses

1. **Adversarial Anti-Evasion:**
   * Canonicalizes localized street names (`rd` $\rightarrow$ `road`, `opp` $\rightarrow$ `opposite`).
   * Evaluates Shannon entropy to penalize keyboard-mashed addresses.
   * Encodes order-independent Soundex fingerprints to prevent multi-account abuse to the same physical address.
2. **Deterministic Circuit Breaker & Idempotency:**
   * Uses `X-Idempotency-Key` headers to guarantee zero double-charges or duplicate model inferences on network retries.
3. **Data Drift Monitoring:**
   * Monitors live feature distributions using Population Stability Index (PSI) via `/api/v1/analytics/drift` to alert before model degradation occurs.

---

## 4. Local Quickstart

### Prerequisites
* Python 3.10+
* Node.js 18+

### 1. Start the Risk Engine Backend
```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Start FastAPI server
uvicorn src.services.api:app --reload --port 8000