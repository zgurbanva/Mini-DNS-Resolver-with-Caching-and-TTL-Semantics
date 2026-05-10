type Bucket = { count: number; resetAt: number };

const buckets = new Map<string, Bucket>();

const WINDOW_MS = 60_000;
const MAX_PER_WINDOW = 60;

export function rateLimitHit(key: string, now = Date.now()): boolean {
  const b = buckets.get(key);
  if (!b || now > b.resetAt) {
    buckets.set(key, { count: 1, resetAt: now + WINDOW_MS });
    return false;
  }
  if (b.count >= MAX_PER_WINDOW) return true;
  b.count += 1;
  return false;
}

/** Best-effort cleanup to avoid unbounded memory (dev / long-running). */
export function pruneRateBuckets(now = Date.now(), maxAgeMs = 300_000): void {
  for (const [k, b] of buckets) {
    if (now - b.resetAt > maxAgeMs) buckets.delete(k);
  }
}

export function clientKey(headers: Headers): string {
  const fwd = headers.get("x-forwarded-for");
  if (fwd) return fwd.split(",")[0]?.trim() || "unknown";
  return headers.get("x-real-ip") || "unknown";
}
