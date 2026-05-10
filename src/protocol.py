"""Upstream DNS transport: UDP+TCP-on-TC, or DoT, or DoH."""

from __future__ import annotations

import asyncio
import copy
import dataclasses
import ipaddress
import urllib.parse
from typing import Literal

import dns.exception
import dns.flags
import dns.message
import dns.query

MAX_UDP_PAYLOAD = 4096
MAX_TCP_PAYLOAD = 65535

UpstreamTransport = Literal["udp", "dot", "doh"]


def clone_message(msg: dns.message.Message) -> dns.message.Message:
    """Deep copy (dnspython 2.8 `QueryMessage` lacks `.copy()`)."""
    return copy.deepcopy(msg)


@dataclasses.dataclass
class UpstreamConfig:
    upstream: str
    timeout: float
    transport: UpstreamTransport = "udp"
    doh_url: str = "https://1.1.1.1/dns-query"
    doh_bootstrap: str | None = None
    dot_port: int = 853
    # TLS SNI + cert hostname for DoT when *upstream* is an IP (dnspython requires IP in *where*).
    dot_server_hostname: str | None = None


def _upstream_ip_for_dot_sni(upstream: str) -> str | None:
    try:
        return str(ipaddress.ip_address(upstream.strip()))
    except ValueError:
        return None


def _default_dot_server_hostname(upstream: str) -> str | None:
    """Pick a TLS server name for well-known anycast resolver IPs (SNI + hostname verify)."""
    ip = _upstream_ip_for_dot_sni(upstream)
    if ip is None:
        return None
    if ip in ("1.1.1.1", "1.0.0.1", "2606:4700:4700::1111", "2606:4700:4700::1001"):
        return "cloudflare-dns.com"
    if ip in ("8.8.8.8", "8.8.4.4", "2001:4860:4860::8888", "2001:4860:4860::8844"):
        return "dns.google"
    return None


def _effective_dot_server_hostname(config: UpstreamConfig) -> str | None:
    if config.dot_server_hostname:
        return config.dot_server_hostname
    return _default_dot_server_hostname(config.upstream)


@dataclasses.dataclass
class UpstreamResult:
    response: dns.message.Message
    used_tcp_fallback: bool
    latency_ms: float


def _parse_doh_url(url: str) -> tuple[str, int, str]:
    p = urllib.parse.urlparse(url)
    host = p.hostname or "1.1.1.1"
    port = p.port or (443 if p.scheme == "https" else 443)
    path = p.path or "/dns-query"
    if not path.startswith("/"):
        path = "/" + path
    return host, int(port), path


async def query_upstream(query: dns.message.Message, *, config: UpstreamConfig) -> UpstreamResult:
    t0 = asyncio.get_running_loop().time()
    transport = config.transport

    if transport == "udp":

        def udp_once() -> dns.message.Message:
            query.to_wire(max_size=MAX_UDP_PAYLOAD)
            return dns.query.udp(
                query,
                config.upstream,
                timeout=config.timeout,
                ignore_unexpected=True,
                sock=None,
            )

        udp_resp = await asyncio.to_thread(udp_once)

        if not (udp_resp.flags & dns.flags.TC):
            elapsed = (asyncio.get_running_loop().time() - t0) * 1000.0
            return UpstreamResult(response=udp_resp, used_tcp_fallback=False, latency_ms=elapsed)

        def tcp_once() -> dns.message.Message:
            return dns.query.tcp(query, config.upstream, timeout=config.timeout)

        tcp_resp = await asyncio.to_thread(tcp_once)
        elapsed = (asyncio.get_running_loop().time() - t0) * 1000.0
        return UpstreamResult(response=tcp_resp, used_tcp_fallback=True, latency_ms=elapsed)

    if transport == "dot":

        def tls_once() -> dns.message.Message:
            sni = _effective_dot_server_hostname(config)
            return dns.query.tls(
                query,
                config.upstream,
                timeout=config.timeout,
                port=config.dot_port,
                server_hostname=sni,
            )

        resp = await asyncio.to_thread(tls_once)
        used = bool(resp.flags & dns.flags.TC)
        elapsed = (asyncio.get_running_loop().time() - t0) * 1000.0
        return UpstreamResult(response=resp, used_tcp_fallback=used, latency_ms=elapsed)

    if transport == "doh":
        # Pass the full URL as `where`; dnspython handles both IP and hostname URLs.
        # Passing just the host breaks hostname-based URLs (urlparse sees no scheme → no hostname).
        doh_where = config.doh_url

        def https_once() -> dns.message.Message:
            return dns.query.https(
                query,
                doh_where,
                timeout=config.timeout,
                bootstrap_address=config.doh_bootstrap,
            )

        resp = await asyncio.to_thread(https_once)
        used = bool(resp.flags & dns.flags.TC)
        elapsed = (asyncio.get_running_loop().time() - t0) * 1000.0
        return UpstreamResult(response=resp, used_tcp_fallback=used, latency_ms=elapsed)

    raise ValueError(f"unknown transport {transport!r}")


async def safe_query_upstream(query: dns.message.Message, *, config: UpstreamConfig) -> UpstreamResult | None:
    """Like query_upstream but maps timeouts and transport failures to None."""
    try:
        return await query_upstream(query, config=config)
    except dns.exception.DNSException:
        return None
    except OSError:
        return None
    except Exception:
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
