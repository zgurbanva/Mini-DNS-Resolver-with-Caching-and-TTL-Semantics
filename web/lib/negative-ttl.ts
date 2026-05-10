/** RFC 2308 style: min(300, SOA minimum) or 60 when no SOA in authority. */

interface SoaLike {
  minimum?: number;
}

export function negativeCacheTtlSec(authorities: Array<{ type: string; data?: unknown }>): number {
  for (const rr of authorities) {
    if (rr.type !== "SOA" || !rr.data || typeof rr.data !== "object") continue;
    const d = rr.data as SoaLike;
    if (typeof d.minimum === "number") {
      return Math.min(300, Math.floor(d.minimum));
    }
  }
  return Math.min(300, 60);
}
