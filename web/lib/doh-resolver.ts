import * as dns from "dns-packet";
import { negativeCacheTtlSec } from "./negative-ttl";
import { normalizeFqdn } from "./dns-names";

const TRUNCATED_RESPONSE = 1 << 9;

function rcodeToString(rcode: number | string | undefined): string {
  if (typeof rcode === "string") return rcode;
  const n = typeof rcode === "number" ? rcode : 0;
  switch (n) {
    case 0:
      return "NOERROR";
    case 1:
      return "FORMERR";
    case 2:
      return "SERVFAIL";
    case 3:
      return "NXDOMAIN";
    case 4:
      return "NOTIMP";
    case 5:
      return "REFUSED";
    default:
      return `RCODE_${n}`;
  }
}

export type RecordType = "A" | "AAAA";

export interface DnsAnswerRow {
  name: string;
  type: string;
  data: string;
  ttl: number;
}

export interface DohLookupResult {
  rcode: string;
  flags: number;
  truncated: boolean;
  answers: DnsAnswerRow[];
  authoritySummary?: string;
  latencyMs: number;
  /** Minimum TTL among matching answers (positive cache), or negative TTL hint */
  cacheTtlSec: number;
  /** NXDOMAIN or NODATA-style negative */
  negative: boolean;
}

function stringifyData(type: string, data: unknown): string {
  if (data == null) return "";
  if (typeof data === "string") return data;
  if (typeof data === "object" && "toString" in (data as object)) {
    try {
      return String((data as { toString(): string }).toString());
    } catch {
      /* fall through */
    }
  }
  return JSON.stringify(data);
}

export async function dohLookup(
  name: string,
  type: RecordType,
  dohUrl: string,
  timeoutMs: number,
): Promise<DohLookupResult> {
  const fqdn = normalizeFqdn(name).replace(/\.$/, "");
  const id = Math.floor(Math.random() * 65535);
  const buf = dns.encode({
    type: "query",
    id,
    flags: dns.RECURSION_DESIRED,
    questions: [{ type, name: fqdn }],
  });

  const t0 = performance.now();
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), timeoutMs);

  let res: Response;
  try {
    res = await fetch(dohUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/dns-message",
        Accept: "application/dns-message",
      },
      body: new Uint8Array(buf),
      signal: ac.signal,
    });
  } finally {
    clearTimeout(timer);
  }

  const latencyMs = performance.now() - t0;

  if (!res.ok) {
    throw new Error(`DoH HTTP ${res.status}`);
  }

  const ab = await res.arrayBuffer();
  const decoded = dns.decode(Buffer.from(ab)) as dns.DnsPacket;
  const rcodeStr = rcodeToString(decoded.rcode as number | string | undefined);

  const flags = decoded.flags ?? 0;
  const truncated = (flags & TRUNCATED_RESPONSE) !== 0;

  const answers: DnsAnswerRow[] = [];
  const want = type;
  for (const a of decoded.answers ?? []) {
    if (a.type !== want) continue;
    answers.push({
      name: typeof a.name === "string" ? a.name : String(a.name),
      type: a.type,
      data: stringifyData(a.type, a.data),
      ttl: Math.max(0, Math.floor(a.ttl ?? 0)),
    });
  }

  const authorities = decoded.authorities ?? [];
  let authoritySummary: string | undefined;
  if (authorities.length > 0) {
    authoritySummary = authorities
      .slice(0, 3)
      .map((r) => `${r.type} ${r.name}`)
      .join("; ");
  }

  const negTtl = negativeCacheTtlSec(authorities);
  const isNx = rcodeStr === "NXDOMAIN";
  const isNodata = rcodeStr === "NOERROR" && answers.length === 0;
  const negative = isNx || isNodata;

  let cacheTtlSec = 0;
  if (answers.length > 0) {
    cacheTtlSec = Math.max(1, Math.min(...answers.map((x) => x.ttl || 1)));
  } else if (negative) {
    cacheTtlSec = Math.max(1, negTtl);
  }

  return {
    rcode: rcodeStr,
    flags,
    truncated,
    answers,
    authoritySummary,
    latencyMs,
    cacheTtlSec,
    negative,
  };
}
