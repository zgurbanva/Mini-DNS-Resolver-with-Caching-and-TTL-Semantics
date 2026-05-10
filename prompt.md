# PROMPT: Project 6 - Advanced DNS Resolver with Caching & Protocol Fallback

## 1. Project Overview

Act as a Senior Backend & Protocol Engineer. Your goal is to develop a **Mini DNS Resolver** that focuses on caching efficiency, TTL semantics, and robust transport behavior (UDP with TCP fallback). This is a "Protocol Project" designed to demonstrate deep understanding of how DNS works under the hood.

## 2. Core Functional Requirements

* **Dual-Transport Handling:**
* The resolver must primarily use **UDP** for speed.
* **CRITICAL:** Implement **TCP Fallback**. If a UDP response is received with the `TC` (Truncated) bit set, the resolver must automatically re-issue the query over TCP to retrieve the full record.


* **Caching Engine:**
* Implement an in-memory cache that respects **TTL (Time-to-Live)**.
* Entries must be automatically evicted or marked as "stale" once the TTL expires.
* Implement **Negative Caching**: Cache `NXDOMAIN` responses for a short duration to prevent redundant upstream lookups for non-existent domains.


* **Upstream Integration:** Default to forwarding misses to a reliable upstream (e.g., `1.1.1.1` or `8.8.8.8`).
* **Record Support:** At a minimum, handle `A` and `AAAA` records.

## 3. Technical Constraints & Architecture

* **Libraries:** You are permitted to use established libraries (e.g., `dnslib` or `dnspython` for Python, or `miekg/dns` for Go) to ensure robustness. For the UI/Terminal output, use something like `rich` or `colorama` to make the logs professional.
* **Modularity:** The project MUST be structured into logical modules:
* `server.py`: Handling socket listeners (UDP/TCP).
* `cache.py`: Logic for TTL, storage, and eviction.
* `protocol.py`: Logic for parsing, crafting packets, and handling the TC bit fallback.
* `utils.py`: Logging and terminal formatting.


* **Dynamic Output:** The terminal output must be user-friendly and dynamic. Use colors to distinguish between `[CACHE_HIT]`, `[CACHE_MISS]`, `[TCP_FALLBACK]`, and `[ERROR]`. Show latency in milliseconds for every request.

## 4. Execution Workflow (Step-by-Step)

> **STOP: Before writing code, provide a detailed Technical Design Document in Plan Mode.**

1. **Phase 1: Plan.** Outline the data structures for the cache and the logic flow for the UDP -> TCP fallback.
2. **Phase 2: Implementation.** Build the core resolver.
3. **Phase 3: Testing & Benchmarking.** Create a `demo.py` script that:
* Queries a domain (Cold Cache) -> Displays Latency.
* Queries again (Warm Cache) -> Displays Latency.
* Forces a large response (to trigger TC bit) and shows the switch to TCP.
* Waits for TTL expiration and shows the refetch.



## 5. P.S. Coding Standards

1. **Readability:** Code must be "production-grade"—clean, commented, and type-hinted.
2. **Concurrency:** Use `asyncio` (Python) or Goroutines (Go) to handle multiple queries without blocking.
3. **Resilience:** Handle upstream timeouts and malformed packets gracefully without crashing the server.