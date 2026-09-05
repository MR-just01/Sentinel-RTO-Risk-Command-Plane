"""
In-memory time-window velocity tracker (sliding window).
"""
import time
from collections import defaultdict


class InMemoryVelocityStore:
    def __init__(self):
        # Maps entity_key -> list of float timestamps
        self.history = defaultdict(list)

    def count(self, key: str, window_seconds: int = 3600) -> int:
        """Returns the number of prior events for `key` within the window.
        Does NOT record a new event — call record() once per request instead,
        so querying multiple window sizes for the same key doesn't inflate the count."""
        now = time.time()
        self.history[key] = [t for t in self.history[key] if now - t <= window_seconds]
        return len(self.history[key])

    def record(self, key: str) -> None:
        """Records a single new event for `key`. Call this exactly once per
        request per entity, after all count() calls for that entity."""
        self.history[key].append(time.time())

    def record_and_count(self, key: str, window_seconds: int = 3600) -> int:
        """Back-compat convenience wrapper: counts prior events, then records
        this event. Avoid calling this more than once per key per request —
        use count()/record() separately when checking multiple window sizes."""
        count = self.count(key, window_seconds)
        self.record(key)
        return count

    def clear(self) -> None:
        """Flushes all sliding-window history. Used by the demo/test reset endpoint."""
        self.history.clear()


# Global runtime velocity cache
VELOCITY_STORE = InMemoryVelocityStore()