"""Upstream DNS transport: UDP-first with TCP retry when TC is set."""

from __future__ import annotations

import asyncio
import copy
import dataclasses

import dns.exception
import dns.flags
import dns.message
import dns.query


MAX_UDP_PAYLOAD = 4096
MAX_TCP_PAYLOAD = 65535


def clone_message(msg: dns.message.Message) -> dns.message.Message:
    """Deep copy (dnspython 2.8 `QueryMessage` lacks `.copy()`)."""
    return copy.deepcopy(msg)


@dataclasses.dataclass
class UpstreamResult:
    response: dns.message.Message
    used_tcp_fallback: bool
    latency_ms: float


async def query_upstream(
    query: dns.message.Message,
    *,
    upstream: str,
    timeout: float,
) -> UpstreamResult:
    """
    Send `query` over UDP; if the UDP reply has TC set, discard it and repeat
    over TCP with the same payload semantics as dns.query.tcp.
    """
    t0 = asyncio.get_running_loop().time()

    def udp_once() -> dns.message.Message:
        query.to_wire(max_size=MAX_UDP_PAYLOAD)
        return dns.query.udp(
            query,
            upstream,
            timeout=timeout,
            ignore_unexpected=True,
            sock=None,
        )

    udp_resp = await asyncio.to_thread(udp_once)

    if not (udp_resp.flags & dns.flags.TC):
        elapsed = (asyncio.get_running_loop().time() - t0) * 1000.0
        return UpstreamResult(response=udp_resp, used_tcp_fallback=False, latency_ms=elapsed)

    def tcp_once() -> dns.message.Message:
        return dns.query.tcp(query, upstream, timeout=timeout)

    tcp_resp = await asyncio.to_thread(tcp_once)
    elapsed = (asyncio.get_running_loop().time() - t0) * 1000.0
    return UpstreamResult(response=tcp_resp, used_tcp_fallback=True, latency_ms=elapsed)


async def safe_query_upstream(
    query: dns.message.Message,
    *,
    upstream: str,
    timeout: float,
) -> UpstreamResult | None:
    """Like query_upstream but maps timeouts and transport failures to None."""
    try:
        return await query_upstream(query, upstream=upstream, timeout=timeout)
    except dns.exception.DNSException:
        return None
    except OSError:
        return None


def parse_client_query(wire: bytes) -> dns.message.Message | None:
    """Parse a client datagram with strict size limits."""
    if len(wire) > MAX_UDP_PAYLOAD:
        return None
    try:
        return dns.message.from_wire(wire, question_only=False, one_rr_per_rrset=False)
    except dns.exception.DNSException:
        return None


def wire_response(msg: dns.message.Message) -> bytes | None:
    try:
        return msg.to_wire(max_size=MAX_TCP_PAYLOAD)
    except dns.exception.DNSException:
        return None
