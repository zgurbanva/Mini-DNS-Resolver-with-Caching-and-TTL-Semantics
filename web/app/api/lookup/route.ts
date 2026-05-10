import { NextRequest, NextResponse } from "next/server";
import { dohLookup, type RecordType } from "@/lib/doh-resolver";
import { PolicyEngine } from "@/lib/policy";
import { validateDomain, validateDohUrl } from "@/lib/validate";
import { cacheKey, getCached, setCached, configureServerCache } from "@/lib/server-cache";
import { clientKey, pruneRateBuckets, rateLimitHit } from "@/lib/rate-limit";
import { blockedResult, summarize, type LookupResponse } from "@/lib/lookup-format";

export const runtime = "nodejs";

const DEFAULT_DOH = process.env.UPSTREAM_DOH_URL ?? "https://cloudflare-dns.com/dns-query";
const DEFAULT_TIMEOUT_MS = Math.min(
  8000,
  Math.max(3000, Number.parseInt(process.env.UPSTREAM_TIMEOUT_MS ?? "8000", 10) || 8000),
);
const MAX_BLOCKLIST_LINES = 200;

const _demo = process.env.DEMO_MAX_TTL_SEC;
if (_demo) {
  const n = Number.parseInt(_demo, 10);
  if (!Number.isNaN(n) && n > 0) configureServerCache({ demoMaxTtlSec: n });
}

interface LookupBody {
  name?: string;
  type?: string;
  blocklist?: string[];
  useServerCache?: boolean;
  dohUrl?: string;
  timeoutMs?: number;
}

function toResponse(
  r: Awaited<ReturnType<typeof dohLookup>>,
  name: string,
  type: RecordType,
  cache: LookupResponse["cache"],
): LookupResponse {
  return {
    ok: true,
    name,
    type,
    rcode: r.rcode,
    truncated: r.truncated,
    answers: r.answers,
    authoritySummary: r.authoritySummary,
    latencyMs: Math.round(r.latencyMs * 100) / 100,
    cache,
    summary: summarize(r, false),
    negative: r.negative,
    cacheTtlSec: r.cacheTtlSec,
  };
}

export async function POST(req: NextRequest) {
  pruneRateBuckets();
  const keyIp = clientKey(req.headers);
  if (rateLimitHit(keyIp)) {
    return NextResponse.json(
      {
        ok: false,
        error: "Too many lookups from this address. Please wait a minute and try again.",
        hint: "We rate-limit to keep the public demo fair.",
      },
      { status: 429 },
    );
  }

  let body: LookupBody;
  try {
    body = (await req.json()) as LookupBody;
  } catch {
    return NextResponse.json({ ok: false, error: "Invalid JSON body." }, { status: 400 });
  }

  const v = validateDomain(body.name ?? "");
  if (!v.ok) return NextResponse.json({ ok: false, error: v.error }, { status: 400 });

  const t = (body.type ?? "A").toUpperCase();
  if (t !== "A" && t !== "AAAA") {
    return NextResponse.json({ ok: false, error: "Only A and AAAA record types are supported." }, { status: 400 });
  }
  const type = t as RecordType;

  const lines = Array.isArray(body.blocklist) ? body.blocklist : [];
  if (lines.length > MAX_BLOCKLIST_LINES) {
    return NextResponse.json(
      { ok: false, error: `Blocklist too long (max ${MAX_BLOCKLIST_LINES} lines).` },
      { status: 400 },
    );
  }

  const policy = PolicyEngine.fromLines(lines, []);
  if (policy.isBlocked(v.name)) {
    return NextResponse.json(blockedResult(v.name, type));
  }

  let dohUrl = DEFAULT_DOH;
  if (body.dohUrl) {
    const u = validateDohUrl(body.dohUrl);
    if (!u.ok) return NextResponse.json({ ok: false, error: u.error }, { status: 400 });
    dohUrl = u.url;
  }

  const timeoutMs = Math.min(12000, Math.max(2000, Number(body.timeoutMs) || DEFAULT_TIMEOUT_MS));

  const ck = cacheKey(v.name, type);
  const useCache = body.useServerCache !== false;

  if (useCache) {
    const hit = getCached(ck);
    if (hit) {
      const r = hit.result;
      return NextResponse.json({
        ...toResponse(r, v.name, type, "hit"),
        latencyMs: Math.min(r.latencyMs, 0.5),
        summary: `${summarize(r, false)} (served from this app’s short-lived server cache — like a warm hit on the Python resolver.)`,
      });
    }
  }

  try {
    const r = await dohLookup(v.name, type, dohUrl, timeoutMs);
    if (useCache) {
      setCached(ck, {
        result: r,
        ttlSec: r.cacheTtlSec,
        isNegative: r.negative,
      });
    }
    return NextResponse.json(toResponse(r, v.name, type, "miss"));
  } catch (e) {
    const msg = e instanceof Error ? e.message : "Lookup failed";
    const aborted = e instanceof Error && e.name === "AbortError";
    return NextResponse.json(
      {
        ok: false,
        error: aborted ? "Upstream lookup timed out." : msg,
        hint: aborted
          ? "This mirrors a slow or blocked upstream (see README: use a longer client timeout; here the server aborted the DoH request)."
          : "Check your network or try again. DoH-only on Vercel — UDP/DoT require running the Python resolver locally.",
      },
      { status: 502 },
    );
  }
}
