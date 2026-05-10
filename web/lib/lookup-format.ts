import type { DohLookupResult, DnsAnswerRow } from "./doh-resolver";

export type CacheMode = "miss" | "hit" | "bypass";

export interface LookupResponse {
  ok: true;
  name: string;
  type: "A" | "AAAA";
  rcode: string;
  truncated: boolean;
  answers: DnsAnswerRow[];
  authoritySummary?: string;
  latencyMs: number;
  cache: CacheMode;
  /** Human hint */
  summary: string;
  /** Negative cache (NXDOMAIN / NODATA) */
  negative: boolean;
  /** TTL used for server-side cache storage */
  cacheTtlSec: number;
  blocked?: boolean;
}

export interface LookupErrorResponse {
  ok: false;
  error: string;
  hint?: string;
}

export function summarize(r: DohLookupResult, blocked: boolean): string {
  if (blocked) return "This name matched your blocklist — no upstream query was sent.";
  if (r.rcode === "NXDOMAIN") return "The name does not exist (NXDOMAIN).";
  if (r.rcode === "NOERROR" && r.answers.length === 0)
    return "The name exists but has no records of this type (NODATA).";
  if (r.rcode === "NOERROR") return "Success — addresses were returned.";
  if (r.rcode === "SERVFAIL") return "Upstream could not complete the query (SERVFAIL).";
  return `Response code: ${r.rcode}`;
}

export function blockedResult(name: string, type: "A" | "AAAA"): LookupResponse {
  const synthetic: DohLookupResult = {
    rcode: "NXDOMAIN",
    flags: 0,
    truncated: false,
    answers: [],
    latencyMs: 0.05,
    cacheTtlSec: 300,
    negative: true,
  };
  return {
    ok: true,
    name,
    type,
    rcode: "NXDOMAIN",
    truncated: false,
    answers: [],
    latencyMs: synthetic.latencyMs,
    cache: "bypass",
    summary: summarize(synthetic, true),
    negative: true,
    cacheTtlSec: 300,
    blocked: true,
  };
}
