"""LRU eviction on positive cache."""

from __future__ import annotations

import dns.message
import dns.name
import dns.rdataclass
import dns.rdatatype
import dns.rrset

from src import cache as cache_mod


def _resp_a(qn: dns.name.Name, ip: str, ttl: int = 60) -> dns.message.Message:
    q = dns.message.make_query(qn, dns.rdatatype.A)
    r = dns.message.make_response(q)
    r.answer.append(
        dns.rrset.from_rdata_list(
            qn,
            ttl,
            [dns.rdata.from_text(dns.rdataclass.IN, dns.rdatatype.A, ip)],
        )
    )
    return r


def test_lru_evicts_oldest_when_cap() -> None:
    c = cache_mod.DNSCache(max_positive_entries=2)
    a = dns.name.from_text("a.example.")
    b = dns.name.from_text("b.example.")
    d = dns.name.from_text("d.example.")
    c.store_positive(a, dns.rdatatype.A, _resp_a(a, "192.0.2.1"))
    c.store_positive(b, dns.rdatatype.A, _resp_a(b, "192.0.2.2"))
    assert c.get_positive_with_ttl(a, dns.rdatatype.A) is not None
    assert c.get_positive_with_ttl(b, dns.rdatatype.A) is not None
    c.store_positive(d, dns.rdatatype.A, _resp_a(d, "192.0.2.4"))
    assert c.get_positive_with_ttl(d, dns.rdatatype.A) is not None
    assert c.get_positive_with_ttl(b, dns.rdatatype.A) is not None
    assert c.get_positive_with_ttl(a, dns.rdatatype.A) is None
    assert c.counts()[0] == 2
