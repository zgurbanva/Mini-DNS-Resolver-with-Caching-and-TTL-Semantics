"""Thread-safe resolver counters and recent-query ring buffer for demos / dashboard."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console
from rich.table import Table

_console = Console(stderr=True)


@dataclass
class ResolverStats:
    """Counters updated from asyncio handlers; use threading.Lock."""

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    hits: int = 0
    misses: int = 0
    negative_hits: int = 0
    tcp_fallbacks: int = 0
    upstream_errors: int = 0
    blocked: int = 0
    uncached_forwards: int = 0
    recent: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=20))

    def add_hit(self) -> None:
        with self._lock:
            self.hits += 1

    def add_miss(self) -> None:
        with self._lock:
            self.misses += 1

    def add_negative_hit(self) -> None:
        with self._lock:
            self.negative_hits += 1

    def add_tcp_fallback(self) -> None:
        with self._lock:
            self.tcp_fallbacks += 1

    def add_upstream_error(self) -> None:
        with self._lock:
            self.upstream_errors += 1

    def add_blocked(self) -> None:
        with self._lock:
            self.blocked += 1

    def add_uncached_forward(self) -> None:
        with self._lock:
            self.uncached_forwards += 1

    def record_recent(
        self,
        *,
        qname: str,
        qtype: str,
        outcome: str,
        latency_ms: float,
        extra: dict[str, Any] | None = None,
    ) -> None:
        row: dict[str, Any] = {
            "ts": time.time(),
            "qname": qname,
            "qtype": qtype,
            "outcome": outcome,
            "latency_ms": round(latency_ms, 3),
        }
        if extra:
            row.update(extra)
        with self._lock:
            self.recent.append(row)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            total = max(1, self.hits + self.misses + self.negative_hits + self.uncached_forwards)
            hit_rate = (self.hits + self.negative_hits) / total
            return {
                "hits": self.hits,
                "misses": self.misses,
                "negative_hits": self.negative_hits,
                "tcp_fallbacks": self.tcp_fallbacks,
                "upstream_errors": self.upstream_errors,
                "blocked": self.blocked,
                "uncached_forwards": self.uncached_forwards,
                "hit_rate_approx": round(hit_rate, 4),
                "recent": list(self.recent),
            }

    def print_summary(self, *, positive_entries: int, negative_entries: int) -> None:
        snap = self.snapshot()
        table = Table(title="Resolver stats", show_header=True, header_style="bold")
        table.add_column("Metric")
        table.add_column("Value", justify="right")
        table.add_row("cache_hits", str(snap["hits"]))
        table.add_row("cache_misses", str(snap["misses"]))
        table.add_row("negative_hits", str(snap["negative_hits"]))
        table.add_row("tcp_fallbacks", str(snap["tcp_fallbacks"]))
        table.add_row("upstream_errors", str(snap["upstream_errors"]))
        table.add_row("blocked", str(snap["blocked"]))
        table.add_row("uncached_forwards", str(snap["uncached_forwards"]))
        table.add_row("positive_cache_entries", str(positive_entries))
        table.add_row("negative_cache_entries", str(negative_entries))
        table.add_row("hit_rate_(hits+neg)/total_queries", str(snap["hit_rate_approx"]))
        _console.print(table)
