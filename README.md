# Sentinel-RTO: Real-Time Autonomous Risk & Policy Execution Gateway

> Production-grade FinTech risk engine designed for e-commerce checkout protection, mitigating Cash-on-Delivery (COD) Return-to-Origin (RTO) courier loss through real-time ML inference, TreeSHAP attribution, and closed-loop auto-responders. Built for the **Razorpay Buildathon**.

---
## 🚀 Live Demonstration
* **Risk Mission Control (Frontend):**https://sentinel-risk-manager-blush.vercel.app
* **API Documentation (FastAPI Swagger):**https://sentinel-rto-risk-command-plane.onrender.com/docs
Live System Health Check: GET [https://sentinel-rto-risk-command-plane.onrender.com/health](https://sentinel-rto-risk-command-plane.onrender.com/health)

Real-time PSI Drift Monitor: GET [https://sentinel-rto-risk-command-plane.onrender.com/api/v1/analytics/drift](https://sentinel-rto-risk-command-plane.onrender.com/api/v1/analytics/drift)

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

```mermaid
flowchart TD
    A["🛒 Client Checkout<br/><code>POST /api/v1/risk/evaluate-order</code><br/><i>Header: X-Idempotency-Key</i>"] --> B{"Idempotency Cache"}

    B -- "Match (Hit)" --> C["⚡ 0ms Replay Cached Payload"]
    
    B -- "Miss" --> D["🛡️ Anti-Evasion Normalization Hub<br/>• Canonical Token Standardizer<br/>• Shannon Entropy Filter<br/>• Phonetic Soundex Clustered"]
    
    D --> E["🧠 Calibrated LightGBM Engine<br/>• Real-Time Probability Scoring<br/>• Native C++ TreeSHAP Attribution"]
    
    E --> F["⚖️ Risk Policy Engine<br/>Cost-Sensitive Decision Boundaries"]
    
    F -->|P < 0.45| G["🟢 GREEN TIER<br/>• 1-Click COD Approved<br/>• 0ms Added Friction"]
    F -->|0.45 <= P < 0.90| H["🟡 AMBER TIER<br/>• Step-Up WhatsApp OTP Challenge<br/>• DLR Handset Telemetry"]
    F -->|P >= 0.90| I["🔴 RED TIER<br/>• COD Disabled (Margin Protection)<br/>• Dynamic 5% Instant UPI Incentive"]

    G --> J["📝 Async Background Engine<br/>• SQLite Audit Ledger Logging<br/>• Population Stability Index (PSI) Monitoring"]
    H --> J
    I --> J

    classDef green fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#ecfdf5;
    classDef amber fill:#78350f,stroke:#f59e0b,stroke-width:2px,color:#fffbeb;
    classDef red fill:#7f1d1d,stroke:#ef4444,stroke-width:2px,color:#fef2f2;
    classDef neutral fill:#0f172a,stroke:#334155,stroke-width:1.5px,color:#f8fafc;

    class G green;
    class H amber;
    class I red;
    class A,B,C,D,E,F,J neutral;
   ```

   ### Measured Precision & Recall (Held-Out Test Set: N = 8,365)

| Metric | Class 0 (Delivered) | Class 1 (RTO / Loss) | Overall / Macro |
| :--- | :--- | :--- | :--- |
| **Precision** | 86.0% | **75.5%** | 81.0% |
| **Recall** | 86.0% | **74.1%** | 80.0% |
| **F1-Score** | 0.86 | **0.75** | 0.80 |
| **Support** | 5,357 | 3,008 | 8,365 |

* **Operational Operating Threshold ($T_{\text{eval}}$):** 0.45
* **ROC-AUC:** 0.8970 | **PR-AUC:** 0.8335
* **Net Margin Impact:** +29.2% recovery (₹1,93,103.37 preserved)

 📄 Complete Test Audit Trail: See Evaluation_Audit_Log.md for the complete record of test cases, raw JSON input/output rows, and latency benchmarks.

 ## 3. Core Technical Defenses

1. **Adversarial Anti-Evasion:**
   * Canonicalizes localized street names (`rd` $\rightarrow$ `road`, `opp` $\rightarrow$ `opposite`).
   * Evaluates Shannon entropy to penalize keyboard-mashed addresses.
   * Encodes order-independent Soundex fingerprints to prevent multi-account abuse to the same physical address.
2. **Deterministic Circuit Breaker & Idempotency:**
   * Uses `X-Idempotency-Key` headers to guarantee zero double-charges or duplicate model inferences on network retries.
3. **Data Drift Monitoring:**
   * Monitors live feature distributions using Population Stability Index (PSI) via `/api/v1/analytics/drift` to alert before model degradation occurs.
```
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








