"""Asyncio UDP stub resolver: cache, optional demo TTL cap, upstream forwarding."""

from __future__ import annotations

import argparse
import asyncio
import os
import signal
import time

import dns.flags
import dns.message
import dns.opcode
import dns.rcode
import dns.rdatatype

import cache as cache_mod
import protocol as protocol_mod
import utils


_CACHED_TYPES = frozenset({dns.rdatatype.A, dns.rdatatype.AAAA})


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
        upstream: str,
        timeout: float,
    ) -> None:
        self._cache = dns_cache
        self._upstream = upstream
        self._timeout = timeout
        self._cache_lock = asyncio.Lock()
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple[str | bytes | int, int]) -> None:
        asyncio.create_task(self._handle_query(data, addr))

    def error_received(self, exc: Exception) -> None:
        utils.log_error(f"UDP socket error: {exc}")

    async def _handle_query(self, data: bytes, addr: tuple[str | bytes | int, int]) -> None:
        t0 = time.perf_counter()
        peer = (str(addr[0]), int(addr[1]))

        q = protocol_mod.parse_client_query(data)
        if q is None:
            utils.log_error("Malformed or oversized DNS datagram", latency_ms=utils.elapsed_ms(t0))
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

        if qtype not in _CACHED_TYPES:
            await self._forward_uncached(q, peer, t0, qname_s, qtype_s, qclass)
            return

        async with self._cache_lock:
            if self._cache.get_negative(qname, qtype):
                resp = cache_mod.nxdomain_response_for_query(q)
                utils.log_cache_hit(
                    latency_ms=utils.elapsed_ms(t0),
                    upstream=self._upstream,
                    qname=qname_s,
                    qtype=qtype_s,
                    extra="negative",
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
            utils.log_cache_hit(
                latency_ms=utils.elapsed_ms(t0),
                upstream=self._upstream,
                qname=qname_s,
                qtype=qtype_s,
            )
            self._send_wire(resp, peer, t0, qname=qname_s, qtype=qtype_s)
            return

        upstream_q = dns.message.make_query(qname, qtype, rdclass=qclass)
        upstream_q.id = q.id

        result = await protocol_mod.safe_query_upstream(
            upstream_q,
            upstream=self._upstream,
            timeout=self._timeout,
        )
        if result is None:
            utils.log_error(
                "Upstream timeout or protocol failure",
                latency_ms=utils.elapsed_ms(t0),
                upstream=self._upstream,
                qname=qname_s,
                qtype=qtype_s,
            )
            self._send_wire(_servfail_response(q), peer, t0, qname=qname_s, qtype=qtype_s)
            return

        if result.used_tcp_fallback:
            utils.log_tcp_fallback(
                latency_ms=result.latency_ms,
                upstream=self._upstream,
                qname=qname_s,
                qtype=qtype_s,
            )

        utils.log_cache_miss(
            latency_ms=utils.elapsed_ms(t0),
            upstream=self._upstream,
            qname=qname_s,
            qtype=qtype_s,
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

        result = await protocol_mod.safe_query_upstream(
            upstream_q,
            upstream=self._upstream,
            timeout=self._timeout,
        )
        if result is None:
            utils.log_error(
                "Upstream timeout or protocol failure (uncached type)",
                latency_ms=utils.elapsed_ms(t0),
                upstream=self._upstream,
                qname=qname_s,
                qtype=qtype_s,
            )
            self._send_wire(_servfail_response(q), peer, t0, qname=qname_s, qtype=qtype_s)
            return

        if result.used_tcp_fallback:
            utils.log_tcp_fallback(
                latency_ms=result.latency_ms,
                upstream=self._upstream,
                qname=qname_s,
                qtype=qtype_s,
            )

        utils.log_cache_miss(
            latency_ms=utils.elapsed_ms(t0),
            upstream=self._upstream,
            qname=qname_s,
            qtype=qtype_s,
            extra="forward-no-cache",
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
        if wire is None:
            utils.log_error(
                "Failed to serialize DNS response",
                latency_ms=utils.elapsed_ms(t0),
                upstream=self._upstream,
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
                upstream=self._upstream,
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
    upstream: str,
    timeout: float,
    demo_max_ttl_sec: int | None,
) -> asyncio.DatagramTransport:
    loop = asyncio.get_running_loop()
    dns_cache = cache_mod.DNSCache(demo_max_ttl_sec=demo_max_ttl_sec)
    transport, _ = await loop.create_datagram_endpoint(
        lambda: StubResolverDatagramProtocol(
            dns_cache=dns_cache,
            upstream=upstream,
            timeout=timeout,
        ),
        local_addr=(bind, port),
    )
    return transport


async def _async_main() -> None:
    parser = argparse.ArgumentParser(description="Mini asyncio forwarding DNS stub resolver (UDP).")
    parser.add_argument("--bind", default="127.0.0.1", help="Listen address (default 127.0.0.1)")
    parser.add_argument(
        "--port",
        type=int,
        default=5353,
        help="UDP listen port (default 5353; root often required for 53)",
    )
    parser.add_argument("--upstream", default="1.1.1.1", help="Upstream resolver IP or hostname")
    parser.add_argument("--timeout", type=float, default=5.0, help="Upstream timeout seconds")
    parser.add_argument(
        "--demo-max-ttl",
        type=int,
        default=None,
        help="Demo-only: cap cached TTL seconds (also DNS_RESOLVER_DEMO_MAX_TTL)",
    )
    args = parser.parse_args()
    demo_cap = _demo_ttl_from_env(args.demo_max_ttl)

    transport = await run_udp_server(
        bind=args.bind,
        port=args.port,
        upstream=args.upstream,
        timeout=args.timeout,
        demo_max_ttl_sec=demo_cap,
    )
    sockname = transport.get_extra_info("sockname")
    utils.console.print(
        f"[bold green]Listening[/bold green] UDP {sockname[0]}:{sockname[1]} "
        f"upstream={args.upstream} demo_ttl_cap={demo_cap}",
    )

    stop = asyncio.Event()

    def _shutdown() -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    try:
        loop.add_signal_handler(signal.SIGINT, _shutdown)
        loop.add_signal_handler(signal.SIGTERM, _shutdown)
    except (NotImplementedError, AttributeError):
        pass

    await stop.wait()
    transport.close()


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
