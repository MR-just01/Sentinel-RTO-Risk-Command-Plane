"""
API Latency SLA and Throughput Benchmark Suite.
Ensures inference stays strictly below the 50ms SLA.
"""
import time
import pytest
from fastapi.testclient import TestClient
from src.services.api import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_sub_50ms_latency_sla(client):
    payload = {
        "order_id": "ord_benchmark_1",
        "user_id": "user_perf_test",
        "phone": "+919876543210",
        "device_id": "dev_perf_test_1",
        "ip_address": "106.51.55.99",
        "delivery_address": "House No. 14, 2nd Floor, MG Road, Near Hanuman Temple",
        "city": "Bengaluru",
        "pincode": "560001",
        "pincode_tier": 1,
        "category": "Fast Fashion",
        "order_value_inr": 1299.0,
        "item_count": 2,
        "payment_method": "COD",
        "is_first_time_user": 1
    }

    # Warm-up request to pre-compile execution paths
    for _ in range(5):
        client.post("/api/v1/risk/evaluate-order", json=payload)

    server_latencies = []
    e2e_latencies = []

    # Measure 50 consecutive calls
    for _ in range(50):
        t0 = time.perf_counter()
        response = client.post("/api/v1/risk/evaluate-order", json=payload)
        t1 = time.perf_counter()

        assert response.status_code == 200
        data = response.json()
        server_latencies.append(data["execution_time_ms"])
        e2e_latencies.append((t1 - t0) * 1000)

    p95_server = sorted(server_latencies)[int(len(server_latencies) * 0.95)]
    avg_server = sum(server_latencies) / len(server_latencies)

    p95_e2e = sorted(e2e_latencies)[int(len(e2e_latencies) * 0.95)]
    avg_e2e = sum(e2e_latencies) / len(e2e_latencies)

    print(f"\n[+] API Server Latency -> Avg: {avg_server:.2f}ms | P95: {p95_server:.2f}ms")
    print(f"[+] Total E2E Latency   -> Avg: {avg_e2e:.2f}ms | P95: {p95_e2e:.2f}ms")

    assert p95_server < 50.0, f"Server P95 latency ({p95_server:.2f}ms) exceeded 50ms SLA!"