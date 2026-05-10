# Project 6: Mini DNS Resolver with Caching and TTL Semantics (Protocol Project)

## THEORETICAL PART

### DNS roles and message flow
- Stub vs recursive vs authoritative (conceptual responsibilities)
- Record types (at minimum A/AAAA) and TTL semantics

### Caching as correctness/performance trade
- TTL meaning; why stale caching breaks correctness
- Negative caching concept (NXDOMAIN) and risks

### Transport behavior
- Why DNS uses UDP commonly; TCP fallback conceptually

### Validation
- Cold vs warm cache latency; TTL expiration behavior

## PRACTICAL PART

### Implement a resolver that:
- Sends queries to an upstream DNS server
- Caches answers with TTL and expires them correctly
- Logs cache hits/misses and response times

### Report + demo:
- Compare latency distributions (cold vs warm cache)
- Show TTL expiration: entry removed and refetched