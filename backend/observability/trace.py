"""
Trace context — every pipeline run gets a UUID that follows
the request from data fetch through to order placement.
"""
import time
import uuid


def generate_trace_id() -> str:
    """Generate a new UUID trace ID."""
    return str(uuid.uuid4())


class TraceContext:
    """
    Lightweight context object passed explicitly through the pipeline.
    Not thread-local — pass as a parameter.

    Attributes:
        trace_id:   UUID string identifying this pipeline run.
        symbol:     Stock symbol being analysed.
        start_time: monotonic clock value at construction.
    """

    def __init__(self, trace_id: str, symbol: str):
        self.trace_id   = trace_id
        self.symbol     = symbol
        self.start_time = time.monotonic()

    def elapsed_ms(self) -> int:
        """Return milliseconds elapsed since TraceContext was created."""
        return int((time.monotonic() - self.start_time) * 1000)

    def __repr__(self) -> str:
        return f"TraceContext(trace_id={self.trace_id}, symbol={self.symbol})"
