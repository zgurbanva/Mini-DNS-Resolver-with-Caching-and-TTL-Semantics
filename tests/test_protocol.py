"""UDP + TCP-on-TC upstream path (mocked)."""

from __future__ import annotations

import asyncio
import unittest.mock as mock

import dns.flags
import dns.message
import dns.name
import dns.rdataclass
import dns.rdatatype
import dns.rrset

from src import protocol as protocol_mod


def test_query_upstream_tcp_fallback_on_tc() -> None:
    q = dns.message.make_query(dns.name.from_text("example.com"), dns.rdatatype.A)
    cfg = protocol_mod.UpstreamConfig(upstream="1.1.1.1", timeout=2.0, transport="udp")

    def udp_trunc(*_a, **_k) -> dns.message.Message:
        r = dns.message.make_response(q)
        r.flags |= dns.flags.TC
        return r

    def tcp_full(*_a, **_k) -> dns.message.Message:
        r = dns.message.make_response(q)
        r.answer.append(
            dns.rrset.from_text("example.com", 30, dns.rdataclass.IN, "A", "93.184.216.34")
        )
        return r

    async def run() -> None:
        with mock.patch("dns.query.udp", side_effect=udp_trunc), mock.patch("dns.query.tcp", side_effect=tcp_full):
            res = await protocol_mod.query_upstream(q, config=cfg)
        assert res.used_tcp_fallback is True
        assert res.response.rcode() == dns.rcode.NOERROR
        assert len(res.response.answer) == 1

    asyncio.run(run())


def test_safe_query_upstream_returns_none_on_dns_error() -> None:
    q = dns.message.make_query(dns.name.from_text("example.com"), dns.rdatatype.A)
    cfg = protocol_mod.UpstreamConfig(upstream="1.1.1.1", timeout=1.0, transport="udp")

    async def run() -> None:
        with mock.patch("dns.query.udp", side_effect=OSError("boom")):
            res = await protocol_mod.safe_query_upstream(q, config=cfg)
        assert res is None

    asyncio.run(run())


def test_dot_tls_uses_server_hostname_for_cloudflare_ip() -> None:
    q = dns.message.make_query(dns.name.from_text("example.com"), dns.rdatatype.A)
    cfg = protocol_mod.UpstreamConfig(upstream="1.1.1.1", timeout=2.0, transport="dot")
    seen: dict[str, object] = {}

    def fake_tls(*_a, **kwargs) -> dns.message.Message:
        seen.update(kwargs)
        r = dns.message.make_response(q)
        r.answer.append(
            dns.rrset.from_text("example.com", 30, dns.rdataclass.IN, "A", "93.184.216.34")
        )
        return r

    async def run() -> None:
        with mock.patch("dns.query.tls", side_effect=fake_tls):
            res = await protocol_mod.query_upstream(q, config=cfg)
        assert res.used_tcp_fallback is False
        assert seen.get("server_hostname") == "cloudflare-dns.com"

    asyncio.run(run())


def test_dot_tls_respects_explicit_dot_server_hostname() -> None:
    q = dns.message.make_query(dns.name.from_text("example.com"), dns.rdatatype.A)
    cfg = protocol_mod.UpstreamConfig(
        upstream="9.9.9.9",
        timeout=2.0,
        transport="dot",
        dot_server_hostname="dns.quad9.net",
    )
    seen: dict[str, object] = {}

    def fake_tls(*_a, **kwargs) -> dns.message.Message:
        seen.update(kwargs)
        return dns.message.make_response(q)

    async def run() -> None:
        with mock.patch("dns.query.tls", side_effect=fake_tls):
            await protocol_mod.query_upstream(q, config=cfg)
        assert seen.get("server_hostname") == "dns.quad9.net"

    asyncio.run(run())
