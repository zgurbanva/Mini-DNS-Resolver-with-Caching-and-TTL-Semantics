"""DNSCache TTL and NXDOMAIN negative caching."""

from __future__ import annotations

import dns.message
import dns.name
import dns.rdataclass
import dns.rcode
import dns.rdatatype
import dns.rrset

import cache as cache_mod


def _mono_factory(start: float = 1000.0):
    t = {"v": start}

    def mono() -> float:
        return t["v"]

    def advance(sec: float) -> None:
        t["v"] += sec

    return mono, advance


def test_positive_cache_expires() -> None:
    mono, advance = _mono_factory()
    c = cache_mod.DNSCache(monotonic_fn=mono)
    qname = dns.name.from_text("example.com.")
    q = dns.message.make_query(qname, dns.rdatatype.A)
    resp = dns.message.make_response(q)
    resp.set_rcode(dns.rcode.NOERROR)
    rrset = dns.rrset.from_rdata_list(
        qname,
        30,
        [dns.rdata.from_text(dns.rdataclass.IN, dns.rdatatype.A, "93.184.216.34")],
    )
    resp.answer.append(rrset)

    c.store_positive(qname, dns.rdatatype.A, resp)
    hit = c.get_positive_with_ttl(qname, dns.rdatatype.A)
    assert hit is not None
    _, rem = hit
    assert rem > 0

    advance(31)
    assert c.get_positive_with_ttl(qname, dns.rdatatype.A) is None


def test_nxdomain_negative_cache() -> None:
    mono, advance = _mono_factory()
    c = cache_mod.DNSCache(monotonic_fn=mono)
    qname = dns.name.from_text("this-should-not-exist-12345.invalid")
    upstream = dns.message.make_query(qname, dns.rdatatype.A)
    resp = dns.message.make_response(upstream)
    resp.set_rcode(dns.rcode.NXDOMAIN)
    soa = dns.rrset.from_text(
        "invalid",
        300,
        dns.rdataclass.IN,
        "SOA",
        "ns.invalid. hostmaster.invalid. 1 3600 1800 604800 120",
    )
    resp.authority.append(soa)

    c.store_nxdomain(qname, dns.rdatatype.A, resp)
    assert c.get_negative(qname, dns.rdatatype.A) is True

    advance(121)
    assert c.get_negative(qname, dns.rdatatype.A) is False


def test_build_positive_cached_response_ttl_clamp() -> None:
    mono, advance = _mono_factory()
    c = cache_mod.DNSCache(monotonic_fn=mono)
    qname = dns.name.from_text("example.com.")
    q = dns.message.make_query(qname, dns.rdatatype.A)
    resp = dns.message.make_response(q)
    resp.answer.append(
        dns.rrset.from_rdata_list(
            qname,
            60,
            [dns.rdata.from_text(dns.rdataclass.IN, dns.rdatatype.A, "93.184.216.34")],
        )
    )
    c.store_positive(qname, dns.rdatatype.A, resp)
    advance(45)
    cached, rem = c.get_positive_with_ttl(qname, dns.rdatatype.A)  # type: ignore[misc]
    out = cache_mod.build_positive_cached_response(query=q, cached=cached, remaining_ttl_sec=rem)
    for rrset in out.answer:
        assert rrset.ttl <= rem
