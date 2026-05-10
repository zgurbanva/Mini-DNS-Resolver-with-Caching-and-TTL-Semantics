import type { DohLookupResult } from "./doh-resolver";

export interface CachedLookupPayload {
  result: DohLookupResult;
  expiresAt: number;
  isNegative: boolean;
}

const store = new Map<string, CachedLookupPayload>();
/** LRU: front = oldest, back = newest */
const lru: string[] = [];

let maxEntries = 256;
let demoMaxTtlSec: number | null = null;

export function configureServerCache(opts: { maxEntries?: number; demoMaxTtlSec?: number | null }) {
  if (opts.maxEntries != null) maxEntries = Math.max(8, opts.maxEntries);
  if (opts.demoMaxTtlSec !== undefined) demoMaxTtlSec = opts.demoMaxTtlSec;
}

export function cacheKey(name: string, type: string): string {
  return `${name.toLowerCase()}|${type}`;
}

function removeFromLru(key: string) {
  const i = lru.indexOf(key);
  if (i >= 0) lru.splice(i, 1);
}

function touch(key: string) {
  removeFromLru(key);
  lru.push(key);
}

export function getCached(key: string, now = Date.now()): CachedLookupPayload | null {
  const e = store.get(key);
  if (!e) return null;
  if (now >= e.expiresAt) {
    store.delete(key);
    removeFromLru(key);
    return null;
  }
  touch(key);
  return e;
}

export function setCached(
  key: string,
  payload: { result: DohLookupResult; ttlSec: number; isNegative: boolean },
  now = Date.now(),
) {
  let ttl = Math.max(1, payload.ttlSec);
  if (demoMaxTtlSec != null) ttl = Math.min(ttl, demoMaxTtlSec);
  store.set(key, {
    result: payload.result,
    expiresAt: now + ttl * 1000,
    isNegative: payload.isNegative,
  });
  touch(key);
  while (lru.length > maxEntries) {
    const victim = lru.shift();
    if (victim) store.delete(victim);
  }
}

export function clearServerCache() {
  store.clear();
  lru.length = 0;
}

export function serverCacheStats() {
  return { entries: store.size, maxEntries };
}
