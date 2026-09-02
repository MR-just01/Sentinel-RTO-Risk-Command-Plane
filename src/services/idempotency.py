"""
Idempotency Store for Zero-Cost Replays.
Prevents duplicate scoring, double OTP generation, and false velocity inflation.
"""
import time
from typing import Optional, Dict, Any

class IdempotencyStore:
    def __init__(self, ttl_seconds: int = 120):
        self.ttl = ttl_seconds
        self._store: Dict[str, Dict[str, Any]] = {}

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        self._evict_expired()
        entry = self._store.get(key)
        if entry:
            return entry["response"]
        return None

    def set(self, key: str, response: Dict[str, Any]):
        self._store[key] = {
            "response": response,
            "expires_at": time.time() + self.ttl
        }

    def _evict_expired(self):
        now = time.time()
        expired = [k for k, v in self._store.items() if v["expires_at"] < now]
        for k in expired:
            del self._store[k]

IDEMPOTENCY_STORE = IdempotencyStore(ttl_seconds=120)