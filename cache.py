"""In-memory DNS cache with TTL-aware positive and negative (NXDOMAIN) entries + optional LRU caps."""

from __future__ import annotations

import copy
import dataclasses
import time
from collections import OrderedDict
from typing import Callable

import dns.message
import dns.name
import dns.rcode
import dns.rdatatype

MonotonicFn = Callable[[], float]


def _normalize_name(name: dns.name.Name) -> dns.name.Name:
    n = name
    if not n.is_absolute():
        n = n.concatenate(dns.name.root)
    return n.canonicalize()


@dataclasses.dataclass
class PositiveCacheEntry:
    message: dns.message.Message
    expires_at: float


@dataclasses.dataclass
class NegativeCacheEntry:
    expires_at: float


class DNSCache:
    """Keyed by (canonical qname, rdtype). Lazy eviction on access; optional LRU eviction."""

    def __init__(
        self,
        *,
        monotonic_fn: MonotonicFn | None = None,
        demo_max_ttl_sec: int | None = None,
        max_positive_entries: int | None = None,
        max_negative_entries: int | None = None,
    ) -> None:
        self._mono = monotonic_fn or time.monotonic
        self._demo_max_ttl_sec = demo_max_ttl_sec
        self._max_positive = max_positive_entries
        self._max_negative = max_negative_entries
        self._positive: OrderedDict[tuple[dns.name.Name, int], PositiveCacheEntry] = OrderedDict()
        self._negative: OrderedDict[tuple[dns.name.Name, int], NegativeCacheEntry] = OrderedDict()

    def _maybe_cap_ttl(self, ttl_sec: int) -> int:
        if self._demo_max_ttl_sec is None:
            return ttl_sec
        return min(ttl_sec, self._demo_max_ttl_sec)

    def counts(self) -> tuple[int, int]:
        return len(self._positive), len(self._negative)

    def flush_all(self) -> None:
        self._positive.clear()
        self._negative.clear()

    def _evict_positive_lru(self) -> None:
        while self._max_positive is not None and len(self._positive) > self._max_positive:
            self._positive.popitem(last=False)

    def _evict_negative_lru(self) -> None:
        while self._max_negative is not None and len(self._negative) > self._max_negative:
            self._negative.popitem(last=False)

    def get_positive_with_ttl(
        self, qname: dns.name.Name, rdtype: int
    ) -> tuple[dns.message.Message, int] | None:
        key = (_normalize_name(qname), rdtype)
        entry = self._positive.get(key)
        if entry is None:
            return None
        now = self._mono()
        if now >= entry.expires_at:
            del self._positive[key]
            return None
        self._positive.move_to_end(key)
        rem = max(0, int(entry.expires_at - now))
        return entry.message, rem

    def get_negative(self, qname: dns.name.Name, rdtype: int) -> bool:
        key = (_normalize_name(qname), rdtype)
        entry = self._negative.get(key)
        if entry is None:
            return False
        now = self._mono()
        if now >= entry.expires_at:
            del self._negative[key]
            return False
        self._negative.move_to_end(key)
        return True

    def store_positive(self, qname: dns.name.Name, rdtype: int, response: dns.message.Message) -> None:
        ttl = min_ttl_for_qtype(response, qname, rdtype)
        if ttl <= 0:
            return
        ttl = max(1, self._maybe_cap_ttl(ttl))
        expires_at = self._mono() + float(ttl)
        key = (_normalize_name(qname), rdtype)
        self._positive[key] = PositiveCacheEntry(message=copy.deepcopy(response), expires_at=expires_at)
        self._positive.move_to_end(key)
        self._evict_positive_lru()

    def store_nxdomain(self, qname: dns.name.Name, rdtype: int, response: dns.message.Message) -> None:
        ttl = negative_cache_ttl_sec(response)
        ttl = max(1, self._maybe_cap_ttl(ttl))
        key = (_normalize_name(qname), rdtype)
        self._negative[key] = NegativeCacheEntry(expires_at=self._mono() + float(ttl))
        self._negative.move_to_end(key)
        self._evict_negative_lru()


def min_ttl_for_qtype(msg: dns.message.Message, qname: dns.name.Name, rdtype: int) -> int:
    """Minimum TTL among answer RRsets matching the query name and type."""
    want = _normalize_name(qname)
    found: list[int] = []
    for rrset in msg.answer:
        if rrset.rdtype != rdtype:
            continue
        if _normalize_name(rrset.name) != want:
            continue
        found.append(rrset.ttl)
    if not found:
        return 0
    return min(found)


def negative_cache_ttl_sec(msg: dns.message.Message) -> int:
    """
    NXDOMAIN negative cache TTL: min(300, SOA minimum) when SOA is present in
    authority; otherwise 60 seconds (hard cap 300).
    """
    soa_min: int | None = None
    for rrset in msg.authority:
        if rrset.rdtype != dns.rdatatype.SOA:
            continue
        if len(rrset) == 0:
            continue
        soa_min = int(rrset[0].minimum)
        break
    if soa_min is None:
        return min(300, 60)
    return min(300, soa_min)


def remaining_ttl_seconds(entry: PositiveCacheEntry, mono_now: float) -> int:
    return max(0, int(entry.expires_at - mono_now))


def build_positive_cached_response(
    *,
    query: dns.message.Message,
    cached: dns.message.Message,
    remaining_ttl_sec: int,
) -> dns.message.Message:
    """Attach cached upstream answers to the client's query with refreshed TTLs."""
    resp = dns.message.make_response(query, recursion_available=True)
    resp.set_rcode(cached.rcode())
    for rrset in cached.answer:
        new_rrset = rrset.copy()
        new_rrset.ttl = max(0, remaining_ttl_sec)
        resp.answer.append(new_rrset)
    for rrset in cached.authority:
        new_rrset = rrset.copy()
        new_rrset.ttl = max(0, min(new_rrset.ttl, remaining_ttl_sec))
        resp.authority.append(new_rrset)
    for rrset in cached.additional:
        new_rrset = rrset.copy()
        new_rrset.ttl = max(0, min(new_rrset.ttl, remaining_ttl_sec))
        resp.additional.append(new_rrset)
    return resp


def nxdomain_response_for_query(query: dns.message.Message) -> dns.message.Message:
    resp = dns.message.make_response(query, recursion_available=True)
    resp.set_rcode(dns.rcode.NXDOMAIN)
    return resp
