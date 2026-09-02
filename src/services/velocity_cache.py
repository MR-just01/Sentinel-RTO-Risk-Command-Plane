"""
In-memory time-window velocity tracker (sliding window).
"""
import time
from collections import defaultdict


class InMemoryVelocityStore:
    def __init__(self):
        # Maps entity_key -> list of float timestamps
        self.history = defaultdict(list)

    def record_and_count(self, key: str, window_seconds: int = 3600) -> int:
        now = time.time()
        # Keep only events within window
        self.history[key] = [t for t in self.history[key] if now - t <= window_seconds]
        count = len(self.history[key])
        # Record current event
        self.history[key].append(now)
        return count


# Global runtime velocity cache
VELOCITY_STORE = InMemoryVelocityStore()