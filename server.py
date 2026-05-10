"""Asyncio UDP stub resolver: policy, cache, stats, optional DoH/DoT upstream, signals."""

from __future__ import annotations

import argparse
import asyncio
import os
import signal
import time
from typing import Any

import dns.flags
import dns.message
import dns.opcode
import dns.rcode
import dns.rdatatype

import cache as cache_mod
import policy as policy_mod
import protocol as protocol_mod
import stats as stats_mod
import utils

_CACHED_TYPES = frozenset({dns.rdatatype.A, dns.rdatatype.AAAA})

# Set while server runs: cache, stats (for SIGUSR1/2 and dashboard snapshot).
_ACTIVE: dict[str, Any] | None = None


def _dash_snapshot() -> dict[str, Any]:
    if _ACTIVE is None:
        return {}
    pos, neg = _ACTIVE["cache"].counts()
    d = _ACTIVE["stats"].snapshot()
    d["positive_cache_entries"] = pos
    d["negative_cache_entries"] = neg
    return d


def _servfail_response(query: dns.message.Message) -> dns.message.Message:
    resp = dns.message.make_response(query, recursion_available=True)
    resp.set_rcode(dns.rcode.SERVFAIL)
    return resp


def _notimp_response(query: dns.message.Message) -> dns.message.Message:
    resp = dns.message.make_response(query, recursion_available=True)
    resp.set_rcode(dns.rcode.NOTIMP)
    return resp


class StubResolverDatagramProtocol(asyncio.DatagramProtocol):
    def __init__(
        self,
        *,
        dns_cache: cache_mod.DNSCache,
        upstream_cfg: protocol_mod.UpstreamConfig,
        resolver_stats: stats_mod.ResolverStats,
        policy: policy_mod.PolicyEngine,
    ) -> None:
        self._cache = dns_cache
        self._upstream_cfg = upstream_cfg
        self._stats = resolver_stats
        self._policy = policy
        self._cache_lock = asyncio.Lock()
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple[str | bytes | int, int]) -> None:
        asyncio.create_task(self._handle_query(data, addr))

    def error_received(self, exc: Exception) -> None:
        utils.log_error(f"UDP socket error: {exc}")

    def _json(
        self,
        event: str,
        *,
        latency_ms: float,
        qname: str | None = None,
        qtype: str | None = None,
        **extra: Any,
    ) -> None:
        payload: dict[str, Any] = {
            "ts": time.time(),
            "event": event,
            "latency_ms": round(latency_ms, 3),
            "upstream": self._upstream_cfg.upstream,
            "transport": self._upstream_cfg.transport,
            "doh_url": self._upstream_cfg.doh_url if self._upstream_cfg.transport == "doh" else None,
        }
        if qname:
            payload["qname"] = qname
        if qtype:
            payload["qtype"] = qtype
        payload.update({k: v for k, v in extra.items() if v is not None})
        utils.emit_json_event(payload)

    def _trace(self, msg: str, **fields: Any) -> None:
        utils.log_trace(msg, upstream=self._upstream_cfg.upstream, transport=self._upstream_cfg.transport, **fields)

    async def _handle_query(self, data: bytes, addr: tuple[str | bytes | int, int]) -> None:
        t0 = time.perf_counter()
        peer = (str(addr[0]), int(addr[1]))
        upstream_s = self._upstream_cfg.upstream

        q = protocol_mod.parse_client_query(data)
        if q is None:
            utils.log_error("Malformed or oversized DNS datagram", latency_ms=utils.elapsed_ms(t0))
            self._json("error", latency_ms=utils.elapsed_ms(t0), qname=None, qtype=None, detail="bad_wire")
            return

        if q.flags & dns.flags.QR:
            utils.log_error("Ignored non-query DNS message", latency_ms=utils.elapsed_ms(t0))
            return

        if q.opcode() != dns.opcode.QUERY:
            out = _notimp_response(q)
            self._send_wire(out, peer, t0, qname="?", qtype="?")
            return

        if len(q.question) == 0:
            utils.log_error("DNS query with empty question section", latency_ms=utils.elapsed_ms(t0))
            self._send_wire(_servfail_response(q), peer, t0)
            return

        question = q.question[0]
        qname = question.name
        qtype = question.rdtype
        qclass = question.rdclass
        qname_s = qname.to_text()
        qtype_s = dns.rdatatype.to_text(qtype)

        if self._policy.is_blocked(qname):
            self._stats.add_blocked()
            out = cache_mod.nxdomain_response_for_query(q)
            lat = utils.elapsed_ms(t0)
            utils.log_policy_block(latency_ms=lat, qname=qname_s, qtype=qtype_s)
            self._json("blocked", latency_ms=lat, qname=qname_s, qtype=qtype_s)
            self._trace("decision", path="blocked", qname=qname_s, qtype=qtype_s)
            self._stats.record_recent(
                qname=qname_s,
                qtype=qtype_s,
                outcome="blocked",
                latency_ms=lat,
                extra={"transport": self._upstream_cfg.transport},
            )
            self._send_wire(out, peer, t0, qname=qname_s, qtype=qtype_s)
            return

        if qtype not in _CACHED_TYPES:
            await self._forward_uncached(q, peer, t0, qname_s, qtype_s, qclass)
            return

        async with self._cache_lock:
            if self._cache.get_negative(qname, qtype):
                resp = cache_mod.nxdomain_response_for_query(q)
                lat = utils.elapsed_ms(t0)
                self._stats.add_negative_hit()
                utils.log_cache_hit(
                    latency_ms=lat,
                    upstream=upstream_s,
                    qname=qname_s,
                    qtype=qtype_s,
                    extra="negative",
                )
                self._json("negative_hit", latency_ms=lat, qname=qname_s, qtype=qtype_s, remaining_ttl_sec=None)
                self._trace("decision", path="negative_hit", qname=qname_s, qtype=qtype_s)
                self._stats.record_recent(
                    qname=qname_s,
                    qtype=qtype_s,
                    outcome="negative_hit",
                    latency_ms=lat,
                    extra={"transport": self._upstream_cfg.transport},
                )
                self._send_wire(resp, peer, t0, qname=qname_s, qtype=qtype_s)
                return

            hit = self._cache.get_positive_with_ttl(qname, qtype)
        if hit is not None:
            cached_msg, rem = hit
            resp = cache_mod.build_positive_cached_response(
                query=q,
                cached=cached_msg,
                remaining_ttl_sec=rem,
            )
            lat = utils.elapsed_ms(t0)
            self._stats.add_hit()
            utils.log_cache_hit(
                latency_ms=lat,
                upstream=upstream_s,
                qname=qname_s,
                qtype=qtype_s,
            )
            self._json("hit", latency_ms=lat, qname=qname_s, qtype=qtype_s, remaining_ttl_sec=rem, tcp_fallback=False)
            self._trace(
                "decision",
                path="positive_hit",
                qname=qname_s,
                qtype=qtype_s,
                remaining_ttl_sec=rem,
            )
            self._stats.record_recent(
                qname=qname_s,
                qtype=qtype_s,
                outcome="hit",
                latency_ms=lat,
                extra={"remaining_ttl_sec": rem, "transport": self._upstream_cfg.transport},
            )
            self._send_wire(resp, peer, t0, qname=qname_s, qtype=qtype_s)
            return

        upstream_q = dns.message.make_query(qname, qtype, rdclass=qclass)
        upstream_q.id = q.id

        self._trace("decision", path="upstream_miss", qname=qname_s, qtype=qtype_s)

        result = await protocol_mod.safe_query_upstream(upstream_q, config=self._upstream_cfg)
        if result is None:
            lat = utils.elapsed_ms(t0)
            self._stats.add_upstream_error()
            utils.log_error(
                "Upstream timeout or protocol failure",
                latency_ms=lat,
                upstream=upstream_s,
                qname=qname_s,
                qtype=qtype_s,
            )
            self._json("error", latency_ms=lat, qname=qname_s, qtype=qtype_s, detail="upstream_fail")
            self._stats.record_recent(
                qname=qname_s,
                qtype=qtype_s,
                outcome="upstream_error",
                latency_ms=lat,
                extra={"transport": self._upstream_cfg.transport},
            )
            self._send_wire(_servfail_response(q), peer, t0, qname=qname_s, qtype=qtype_s)
            return

        if result.used_tcp_fallback:
            self._stats.add_tcp_fallback()
            utils.log_tcp_fallback(
                latency_ms=result.latency_ms,
                upstream=upstream_s,
                qname=qname_s,
                qtype=qtype_s,
            )
            self._json(
                "tcp_fallback",
                latency_ms=result.latency_ms,
                qname=qname_s,
                qtype=qtype_s,
                tcp_fallback=True,
            )

        lat = utils.elapsed_ms(t0)
        self._stats.add_miss()
        utils.log_cache_miss(
            latency_ms=lat,
            upstream=upstream_s,
            qname=qname_s,
            qtype=qtype_s,
        )
        self._json(
            "miss",
            latency_ms=lat,
            qname=qname_s,
            qtype=qtype_s,
            tcp_fallback=result.used_tcp_fallback,
        )
        self._stats.record_recent(
            qname=qname_s,
            qtype=qtype_s,
            outcome="miss",
            latency_ms=lat,
            extra={"tcp_fallback": result.used_tcp_fallback, "transport": self._upstream_cfg.transport},
        )

        resp = result.response
        out = protocol_mod.clone_message(resp)
        out.id = q.id

        async with self._cache_lock:
            if resp.rcode() == dns.rcode.NXDOMAIN:
                self._cache.store_nxdomain(qname, qtype, resp)
            elif resp.rcode() == dns.rcode.NOERROR:
                if cache_mod.min_ttl_for_qtype(resp, qname, qtype) > 0:
                    self._cache.store_positive(qname, qtype, resp)
                elif (
                    not resp.answer
                    and any(rrset.rdtype == dns.rdatatype.SOA for rrset in resp.authority)
                ):
                    # NODATA: name exists but no records of this type; cache per RFC 2308 §5
                    self._cache.store_nodata(qname, qtype, resp)

        self._send_wire(out, peer, t0, qname=qname_s, qtype=qtype_s)

    async def _forward_uncached(
        self,
        q: dns.message.Message,
        peer: tuple[str, int],
        t0: float,
        qname_s: str,
        qtype_s: str,
        qclass: int,
    ) -> None:
        question = q.question[0]
        upstream_q = dns.message.make_query(question.name, question.rdtype, rdclass=qclass)
        upstream_q.id = q.id
        upstream_s = self._upstream_cfg.upstream

        result = await protocol_mod.safe_query_upstream(upstream_q, config=self._upstream_cfg)
        if result is None:
            lat = utils.elapsed_ms(t0)
            self._stats.add_upstream_error()
            utils.log_error(
                "Upstream timeout or protocol failure (uncached type)",
                latency_ms=lat,
                upstream=upstream_s,
                qname=qname_s,
                qtype=qtype_s,
            )
            self._json("error", latency_ms=lat, qname=qname_s, qtype=qtype_s, detail="upstream_fail_uncached")
            self._send_wire(_servfail_response(q), peer, t0, qname=qname_s, qtype=qtype_s)
            return

        if result.used_tcp_fallback:
            self._stats.add_tcp_fallback()
            utils.log_tcp_fallback(
                latency_ms=result.latency_ms,
                upstream=upstream_s,
                qname=qname_s,
                qtype=qtype_s,
            )

        lat = utils.elapsed_ms(t0)
        self._stats.add_uncached_forward()
        utils.log_cache_miss(
            latency_ms=lat,
            upstream=upstream_s,
            qname=qname_s,
            qtype=qtype_s,
            extra="forward-no-cache",
        )
        self._json("uncached_forward", latency_ms=lat, qname=qname_s, qtype=qtype_s, tcp_fallback=result.used_tcp_fallback)
        self._stats.record_recent(
            qname=qname_s,
            qtype=qtype_s,
            outcome="uncached_forward",
            latency_ms=lat,
            extra={"tcp_fallback": result.used_tcp_fallback, "transport": self._upstream_cfg.transport},
        )

        out = protocol_mod.clone_message(result.response)
        out.id = q.id
        self._send_wire(out, peer, t0, qname=qname_s, qtype=qtype_s)

    def _send_wire(
        self,
        msg: dns.message.Message,
        peer: tuple[str, int],
        t0: float,
        *,
        qname: str | None = None,
        qtype: str | None = None,
    ) -> None:
        wire = protocol_mod.wire_response(msg)
        upstream_s = self._upstream_cfg.upstream
        if wire is None:
            utils.log_error(
                "Failed to serialize DNS response",
                latency_ms=utils.elapsed_ms(t0),
                upstream=upstream_s,
                qname=qname,
                qtype=qtype,
            )
            return
        if self.transport is None:
            return
        try:
            self.transport.sendto(wire, peer)
        except OSError as exc:
            utils.log_error(
                "sendto failed",
                latency_ms=utils.elapsed_ms(t0),
                upstream=upstream_s,
                qname=qname,
                qtype=qtype,
                exc=exc,
            )


def _demo_ttl_from_env(cli_value: int | None) -> int | None:
    if cli_value is not None:
        return cli_value
    raw = os.environ.get("DNS_RESOLVER_DEMO_MAX_TTL")
    if raw is None or raw == "":
        return None
    try:
        return max(1, int(raw))
    except ValueError:
        return None


async def run_udp_server(
    *,
    bind: str,
    port: int,
    upstream_cfg: protocol_mod.UpstreamConfig,
    demo_max_ttl_sec: int | None,
    max_positive_entries: int | None,
    max_negative_entries: int | None,
    policy: policy_mod.PolicyEngine,
    resolver_stats: stats_mod.ResolverStats,
) -> tuple[asyncio.DatagramTransport, cache_mod.DNSCache]:
    loop = asyncio.get_running_loop()
    dns_cache = cache_mod.DNSCache(
        demo_max_ttl_sec=demo_max_ttl_sec,
        max_positive_entries=max_positive_entries,
        max_negative_entries=max_negative_entries,
    )
    transport, _ = await loop.create_datagram_endpoint(
        lambda: StubResolverDatagramProtocol(
            dns_cache=dns_cache,
            upstream_cfg=upstream_cfg,
            resolver_stats=resolver_stats,
            policy=policy,
        ),
        local_addr=(bind, port),
    )
    return transport, dns_cache


async def _async_main() -> None:
    global _ACTIVE

    parser = argparse.ArgumentParser(description="Mini asyncio forwarding DNS stub resolver (UDP).")
    parser.add_argument("--bind", default="127.0.0.1", help="Listen address (default 127.0.0.1)")
    parser.add_argument(
        "--port",
        type=int,
        default=55353,
        help="UDP listen port (default 55353; root often required for 53)",
    )
    parser.add_argument("--upstream", default="1.1.1.1", help="Upstream resolver IP or hostname (DoT/UDP)")
    parser.add_argument("--timeout", type=float, default=5.0, help="Upstream timeout seconds")
    parser.add_argument(
        "--upstream-protocol",
        choices=("udp", "dot", "doh"),
        default="udp",
        help="Upstream transport (default udp)",
    )
    parser.add_argument(
        "--doh-url",
        default="https://1.1.1.1/dns-query",
        help="Full HTTPS URL for DoH (default Cloudflare)",
    )
    parser.add_argument(
        "--doh-bootstrap-ip",
        default=None,
        help="Optional bootstrap IP/hostname for DoH TLS connect",
    )
    parser.add_argument("--dot-port", type=int, default=853, help="DoT port (default 853)")
    parser.add_argument(
        "--dot-server-name",
        default=None,
        metavar="HOSTNAME",
        help="TLS SNI / cert hostname for DoT when --upstream is an IP (e.g. cloudflare-dns.com). "
        "Omitted: auto for 1.1.1.1 / 8.8.8.8 and related anycast addresses.",
    )
    parser.add_argument(
        "--demo-max-ttl",
        type=int,
        default=None,
        help="Demo-only: cap cached TTL seconds (also DNS_RESOLVER_DEMO_MAX_TTL)",
    )
    parser.add_argument("--max-positive-cache", type=int, default=None, help="LRU cap for positive A/AAAA entries")
    parser.add_argument("--max-negative-cache", type=int, default=None, help="LRU cap for negative cache entries")
    parser.add_argument("--blocklist", default=None, help="Path to blocklist file (suffixes, one per line)")
    parser.add_argument("--allowlist", default=None, help="Optional allowlist; if set, only matching names proceed")
    parser.add_argument("--json-logs", action="store_true", help="Emit one JSON line per query event to stdout")
    parser.add_argument("--trace", action="store_true", help="Verbose trace lines to stderr")
    parser.add_argument(
        "--stats-interval",
        type=float,
        default=0.0,
        help="If >0, print stats table every N seconds",
    )
    parser.add_argument(
        "--dashboard",
        default=None,
        metavar="HOST:PORT",
        help="Serve FastAPI dashboard (pip install -r requirements-dashboard.txt), e.g. 127.0.0.1:8080",
    )
    args = parser.parse_args()
    demo_cap = _demo_ttl_from_env(args.demo_max_ttl)

    utils.configure(json_logs=args.json_logs, trace=args.trace)

    policy = policy_mod.PolicyEngine.from_files(args.blocklist, args.allowlist)
    resolver_stats = stats_mod.ResolverStats()
    upstream_cfg = protocol_mod.UpstreamConfig(
        upstream=args.upstream,
        timeout=args.timeout,
        transport=args.upstream_protocol,
        doh_url=args.doh_url,
        doh_bootstrap=args.doh_bootstrap_ip,
        dot_port=args.dot_port,
        dot_server_hostname=args.dot_server_name,
    )

    transport, dns_cache = await run_udp_server(
        bind=args.bind,
        port=args.port,
        upstream_cfg=upstream_cfg,
        demo_max_ttl_sec=demo_cap,
        max_positive_entries=args.max_positive_cache,
        max_negative_entries=args.max_negative_cache,
        policy=policy,
        resolver_stats=resolver_stats,
    )

    _ACTIVE = {"cache": dns_cache, "stats": resolver_stats}

    sockname = transport.get_extra_info("sockname")
    utils.console.print(
        f"[bold green]Listening[/bold green] UDP {sockname[0]}:{sockname[1]} "
        f"upstream={args.upstream} protocol={args.upstream_protocol} demo_ttl_cap={demo_cap}",
    )

    loop = asyncio.get_running_loop()

    def on_usr1() -> None:
        if _ACTIVE is None:
            return
        pos, neg = _ACTIVE["cache"].counts()
        _ACTIVE["stats"].print_summary(positive_entries=pos, negative_entries=neg)

    def on_usr2() -> None:
        if _ACTIVE is None:
            return
        _ACTIVE["cache"].flush_all()
        utils.console.print("[yellow]Cache flushed (SIGUSR2)[/yellow]")

    try:
        loop.add_signal_handler(signal.SIGUSR1, on_usr1)
        loop.add_signal_handler(signal.SIGUSR2, on_usr2)
    except (NotImplementedError, AttributeError):
        pass

    if args.dashboard:
        dash = args.dashboard.strip()
        if ":" in dash:
            host, _, port_s = dash.partition(":")
            bind_host = host or "127.0.0.1"
            port_i = int(port_s)
        else:
            bind_host, port_i = "127.0.0.1", int(dash)
        import dashboard as dashboard_mod

        dashboard_mod.start_dashboard(bind_host, port_i, _dash_snapshot)
        utils.console.print(f"[bold cyan]Dashboard[/bold cyan] http://{bind_host}:{port_i}/")

    async def stats_loop() -> None:
        while True:
            await asyncio.sleep(args.stats_interval)
            if _ACTIVE is None:
                continue
            pos, neg = _ACTIVE["cache"].counts()
            _ACTIVE["stats"].print_summary(positive_entries=pos, negative_entries=neg)

    stats_task: asyncio.Task[None] | None = None
    if args.stats_interval and args.stats_interval > 0:
        stats_task = asyncio.create_task(stats_loop())

    stop = asyncio.Event()

    def _shutdown() -> None:
        stop.set()

    try:
        loop.add_signal_handler(signal.SIGINT, _shutdown)
        loop.add_signal_handler(signal.SIGTERM, _shutdown)
    except (NotImplementedError, AttributeError):
        pass

    await stop.wait()
    if stats_task is not None:
        stats_task.cancel()
        try:
            await stats_task
        except asyncio.CancelledError:
            pass
    transport.close()
    _ACTIVE = None


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
