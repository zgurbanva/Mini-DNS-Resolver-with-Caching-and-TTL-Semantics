#!/usr/bin/env python3
"""Demonstrations: cold vs warm cache, injected TCP fallback, short-TTL expiry."""

from __future__ import annotations

import argparse
import asyncio
import time
from unittest.mock import patch

import dns.flags
import dns.message
import dns.name
import dns.query
import dns.rdataclass
import dns.rdatatype
import dns.rrset

import policy as policy_mod
import protocol
import stats as stats_mod
import utils
from server import run_udp_server


def _embedded_upstream(upstream: str, timeout: float) -> protocol.UpstreamConfig:
    return protocol.UpstreamConfig(upstream=upstream, timeout=timeout, transport="udp")


async def _udp_query_local(port: int, qname: str, rdtype: str) -> dns.message.Message:
    q = dns.message.make_query(qname, rdtype)

    def _send() -> dns.message.Message:
        return dns.query.udp(q, "127.0.0.1", port=port, timeout=5.0)

    return await asyncio.to_thread(_send)


async def scenario_cold_warm(*, upstream: str, timeout: float, domain: str) -> None:
    utils.console.print("\n[bold]Scenario 1–2:[/bold] cold cache → warm repeat")
    transport, _cache = await run_udp_server(
        bind="127.0.0.1",
        port=0,
        upstream_cfg=_embedded_upstream(upstream, timeout),
        demo_max_ttl_sec=None,
        max_positive_entries=None,
        max_negative_entries=None,
        policy=policy_mod.PolicyEngine.empty(),
        resolver_stats=stats_mod.ResolverStats(),
    )
    port = transport.get_extra_info("sockname")[1]
    try:
        t0 = time.perf_counter()
        await _udp_query_local(port, domain, "A")
        cold_ms = (time.perf_counter() - t0) * 1000.0
        utils.console.print(f"Cold query latency (client-measured): {cold_ms:.2f} ms")

        t1 = time.perf_counter()
        await _udp_query_local(port, domain, "A")
        warm_ms = (time.perf_counter() - t1) * 1000.0
        utils.console.print(f"Warm query latency (client-measured): {warm_ms:.2f} ms")
    finally:
        transport.close()
        await asyncio.sleep(0.05)


async def scenario_tcp_fallback_injected() -> None:
    utils.console.print(
        "\n[bold]Scenario 3:[/bold] UDP returns TC → TCP retry "
        "(offline injected mocks; watch for [TCP_FALLBACK] on stderr)"
    )

    q = dns.message.make_query("example.com", "A")
    truncated = dns.message.make_response(q)
    truncated.flags |= dns.flags.TC

    full = dns.message.make_response(q)
    full.answer.append(
        dns.rrset.from_rdata_list(
            dns.name.from_text("example.com."),
            300,
            [dns.rdata.from_text(dns.rdataclass.IN, dns.rdatatype.A, "192.0.2.10")],
        )
    )

    def fake_udp(*_args, **_kwargs):  # noqa: ANN001
        return truncated

    def fake_tcp(*_args, **_kwargs):  # noqa: ANN001
        return full

    cfg = protocol.UpstreamConfig(upstream="192.0.2.1", timeout=2.0, transport="udp")
    with patch.object(protocol.dns.query, "udp", side_effect=fake_udp), patch.object(
        protocol.dns.query, "tcp", side_effect=fake_tcp
    ):
        res = await protocol.query_upstream(q, config=cfg)

    assert res is not None
    assert res.used_tcp_fallback is True
    utils.console.print(
        f"Injected TC path OK (tcp_fallback={res.used_tcp_fallback}, "
        f"upstream_latency≈{res.latency_ms:.2f} ms)"
    )


async def scenario_ttl_expiry(*, upstream: str, timeout: float, domain: str, cap: int, pause: float) -> None:
    utils.console.print(
        f"\n[bold]Scenario 4:[/bold] TTL expiry via demo TTL cap={cap}s "
        f"(sleep {pause:.1f}s between queries)"
    )
    transport, _cache = await run_udp_server(
        bind="127.0.0.1",
        port=0,
        upstream_cfg=_embedded_upstream(upstream, timeout),
        demo_max_ttl_sec=cap,
        max_positive_entries=None,
        max_negative_entries=None,
        policy=policy_mod.PolicyEngine.empty(),
        resolver_stats=stats_mod.ResolverStats(),
    )
    port = transport.get_extra_info("sockname")[1]
    try:
        await _udp_query_local(port, domain, "A")
        utils.console.print(f"First fetch cached with TTL≤{cap}s …")
        await asyncio.sleep(pause)
        t0 = time.perf_counter()
        await _udp_query_local(port, domain, "A")
        refetch_ms = (time.perf_counter() - t0) * 1000.0
        utils.console.print(
            f"Post-expiry query latency (expect upstream again): {refetch_ms:.2f} ms "
            "(server logs should show [CACHE_MISS])"
        )
    finally:
        transport.close()
        await asyncio.sleep(0.05)


async def _async_main() -> None:
    parser = argparse.ArgumentParser(description="Mini DNS resolver demos against a local embedded server.")
    parser.add_argument("--upstream", default="1.1.1.1")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--domain", default="example.com", help="Real domain for cold/warm/TTL demos")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Only run the injected TCP-fallback harness (no upstream needed).",
    )
    parser.add_argument("--ttl-cap", type=int, default=3, help="Demo positive-cache TTL cap for scenario 4")
    parser.add_argument(
        "--ttl-pause",
        type=float,
        default=3.5,
        help="Seconds to sleep before post-expiry query in scenario 4",
    )
    args = parser.parse_args()

    await scenario_tcp_fallback_injected()
    if args.offline:
        utils.console.print("\n[dim]Skipping network demos (--offline).[/dim]")
        return

    await scenario_cold_warm(upstream=args.upstream, timeout=args.timeout, domain=args.domain)
    await scenario_ttl_expiry(
        upstream=args.upstream,
        timeout=args.timeout,
        domain=args.domain,
        cap=args.ttl_cap,
        pause=args.ttl_pause,
    )


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
