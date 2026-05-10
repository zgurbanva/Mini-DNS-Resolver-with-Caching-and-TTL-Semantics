#!/usr/bin/env python3
"""
Measure cold vs warm DNS latency against a running server.

Cold runs: send SIGUSR2 to the server PID between iterations (cache flush), then query.
Warm runs: repeat the same query without flushing.

Example:
  Terminal A: python server.py --port 55353 --upstream 1.1.1.1
  Terminal B: python scripts/benchmark.py --pid $(pgrep -f 'python server.py') --port 55353
"""

from __future__ import annotations

import argparse
import os
import signal
import statistics
import time

import dns.message
import dns.query
import dns.rdatatype


def _udp_ms(host: str, port: int, qname: str, rdtype: str) -> float:
    q = dns.message.make_query(qname, getattr(dns.rdatatype, rdtype))
    t0 = time.perf_counter()
    dns.query.udp(q, host, port=port, timeout=5.0)
    return (time.perf_counter() - t0) * 1000.0


def _summarize(samples: list[float]) -> tuple[float, float, float]:
    if not samples:
        return 0.0, 0.0, 0.0
    return min(samples), statistics.median(samples), max(samples)


def main() -> int:
    p = argparse.ArgumentParser(description="DNS resolver latency benchmark (cold vs warm).")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=55353)
    p.add_argument("--domain", default="example.com")
    p.add_argument("--type", dest="rtype", default="A", help="Query type name, e.g. A or AAAA")
    p.add_argument("--warm-iters", type=int, default=50)
    p.add_argument("--cold-iters", type=int, default=20)
    p.add_argument(
        "--pid",
        type=int,
        default=None,
        help="Server PID: send SIGUSR2 before each cold query to flush cache (Unix)",
    )
    args = p.parse_args()

    warm_samples: list[float] = []
    for _ in range(args.warm_iters):
        warm_samples.append(_udp_ms(args.host, args.port, args.domain, args.rtype))

    cold_samples: list[float] = []
    for i in range(args.cold_iters):
        if args.pid:
            try:
                os.kill(args.pid, signal.SIGUSR2)
            except ProcessLookupError:
                print("error: --pid process not found")
                return 1
            time.sleep(0.05)
        cold_samples.append(_udp_ms(args.host, args.port, f"{args.domain}", args.rtype))
        # vary qname slightly if no pid so cold still hits network sometimes
        if not args.pid and i > 0:
            pass  # same domain: second+ cold without flush is just warm — user should pass --pid

    wmin, wmed, wmax = _summarize(warm_samples)
    cmin, cmed, cmax = _summarize(cold_samples)
    print(f"Warm (n={args.warm_iters}) ms — min: {wmin:.2f}  median: {wmed:.2f}  max: {wmax:.2f}")
    print(f"Cold (n={args.cold_iters}) ms — min: {cmin:.2f}  median: {cmed:.2f}  max: {cmax:.2f}")
    if not args.pid:
        print("note: pass --pid <server_pid> so SIGUSR2 flushes cache between cold samples.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
