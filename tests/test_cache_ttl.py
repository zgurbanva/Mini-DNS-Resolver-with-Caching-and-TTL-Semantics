"""Tests for TTL-aware caching and NXDOMAIN negative TTL caps."""

from __future__ import annotations

import dns.message
import dns.name
import dns.rdataclass
import dns.rdatatype
import dns.rcode
import dns.rrset

from src import cache as cache_mod


def _sample_positive_response(qname: dns.name.Name, ttl: int = 120) -> dns.message.Message:
    q = dns.message.make_query(qname, dns.rdatatype.A)
    resp = dns.message.make_response(q)
    resp.answer.append(
        dns.rrset.from_rdata_list(
            qname,
            ttl,
            [dns.rdata.from_text(dns.rdataclass.IN, dns.rdatatype.A, "192.0.2.1")],
        )
    )
    return resp


def test_positive_cache_expires_with_monotonic_clock() -> None:
    now = {"t": 0.0}

    def mono() -> float:
        return now["t"]

    c = cache_mod.DNSCache(monotonic_fn=mono)
    qn = dns.name.from_text("example.com.")
    resp = _sample_positive_response(qn, ttl=10)
    c.store_positive(qn, dns.rdatatype.A, resp)

    hit = c.get_positive_with_ttl(qn, dns.rdatatype.A)
    assert hit is not None
    msg, rem = hit
    assert rem <= 10
    assert msg.rcode() == dns.rcode.NOERROR

    now["t"] = 9.0
    assert c.get_positive_with_ttl(qn, dns.rdatatype.A) is not None

    now["t"] = 11.0
    assert c.get_positive_with_ttl(qn, dns.rdatatype.A) is None


def test_negative_cache_ttl_respects_soa_minimum_cap() -> None:
    qn = dns.name.from_text("does-not-exist.example.")
    q = dns.message.make_query(qn, dns.rdatatype.A)
    resp = dns.message.make_response(q)
    resp.set_rcode(dns.rcode.NXDOMAIN)
    soa = dns.rrset.from_rdata_list(
        dns.name.from_text("example."),
        3600,
        [
            dns.rdata.from_text(
                dns.rdataclass.IN,
                dns.rdatatype.SOA,
                "ns.example. hostmaster.example. 1 3600 1800 604800 900",
            )
        ],
    )
    resp.authority.append(soa)

    assert cache_mod.negative_cache_ttl_sec(resp) == min(300, 900)

    now = {"t": 0.0}

    def mono() -> float:
        return now["t"]

    c = cache_mod.DNSCache(monotonic_fn=mono)
    c.store_nxdomain(qn, dns.rdatatype.A, resp)
    assert c.get_negative(qn, dns.rdatatype.A) is True

    now["t"] = float(cache_mod.negative_cache_ttl_sec(resp)) + 0.5
    assert c.get_negative(qn, dns.rdatatype.A) is False


def test_demo_ttl_cap_applies_to_positive_entries() -> None:
    now = {"t": 0.0}

    def mono() -> float:
        return now["t"]

    c = cache_mod.DNSCache(monotonic_fn=mono, demo_max_ttl_sec=3)
    qn = dns.name.from_text("example.com.")
    resp = _sample_positive_response(qn, ttl=600)
    c.store_positive(qn, dns.rdatatype.A, resp)

    now["t"] = 4.0
    assert c.get_positive_with_ttl(qn, dns.rdatatype.A) is None
