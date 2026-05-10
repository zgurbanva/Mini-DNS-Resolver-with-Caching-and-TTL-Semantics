"use client";

import { useCallback, useState } from "react";
import { Glossary } from "@/components/Glossary";

type Ok = {
  ok: true;
  name: string;
  type: string;
  rcode: string;
  truncated: boolean;
  answers: { name: string; type: string; data: string; ttl: number }[];
  authoritySummary?: string;
  latencyMs: number;
  cache: string;
  summary: string;
  negative: boolean;
  cacheTtlSec: number;
  blocked?: boolean;
};

type Err = { ok: false; error: string; hint?: string };

export function LookupLab() {
  const [name, setName] = useState("example.com");
  const [type, setType] = useState<"A" | "AAAA">("A");
  const [dohUrl, setDohUrl] = useState("");
  const [timeoutMs, setTimeoutMs] = useState(8000);
  const [blocklist, setBlocklist] = useState("");
  const [useServerCache, setUseServerCache] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Ok | null>(null);
  const [error, setError] = useState<Err | null>(null);

  const runLookup = useCallback(async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    const lines = blocklist
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);
    try {
      const res = await fetch("/api/lookup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          type,
          blocklist: lines.length ? lines : undefined,
          useServerCache,
          dohUrl: dohUrl.trim() || undefined,
          timeoutMs,
        }),
      });
      const data = (await res.json()) as Ok | Err;
      if (!res.ok) {
        setError(data as Err);
        return;
      }
      setResult(data as Ok);
    } catch {
      setError({ ok: false, error: "Network error — could not reach this app." });
    } finally {
      setLoading(false);
    }
  }, [name, type, blocklist, useServerCache, dohUrl, timeoutMs]);

  const presets = [
    { label: "example.com", v: "example.com" },
    { label: "NODATA (README)", v: "doesnotexist.example.com" },
    { label: "NXDOMAIN (README)", v: "nxdomain.test" },
    { label: "Cloudflare", v: "cloudflare.com" },
  ];

  return (
    <div className="space-y-8">
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
        <h2 className="mb-4 text-lg font-medium text-white">Look up a domain</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block sm:col-span-2">
            <span className="mb-1 block text-sm text-zinc-400">Domain name</span>
            <input
              className="w-full rounded border border-zinc-700 bg-zinc-950 px-3 py-2 text-white"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="example.com"
              autoComplete="off"
            />
          </label>
          <fieldset>
            <legend className="mb-1 text-sm text-zinc-400">Record type</legend>
            <div className="flex gap-4 text-zinc-200">
              <label className="flex items-center gap-2">
                <input type="radio" checked={type === "A"} onChange={() => setType("A")} />A (IPv4)
              </label>
              <label className="flex items-center gap-2">
                <input type="radio" checked={type === "AAAA"} onChange={() => setType("AAAA")} />
                AAAA (IPv6)
              </label>
            </div>
          </fieldset>
          <label className="flex items-center gap-2 text-sm text-zinc-300">
            <input type="checkbox" checked={useServerCache} onChange={(e) => setUseServerCache(e.target.checked)} />
            Use server <Glossary term="cache">cache</Glossary> (try twice to see a hit)
          </label>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {presets.map((p) => (
            <button
              key={p.v}
              type="button"
              className="rounded-full border border-zinc-600 px-3 py-1 text-sm text-zinc-300 hover:border-teal-600 hover:text-teal-200"
              onClick={() => setName(p.v)}
            >
              {p.label}
            </button>
          ))}
        </div>
      </section>

      <details className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-4">
        <summary className="cursor-pointer text-sm font-medium text-zinc-300">Advanced</summary>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <label className="block sm:col-span-2">
            <span className="mb-1 block text-sm text-zinc-400">
              Custom <Glossary term="doh">DoH</Glossary> URL (https only)
            </span>
            <input
              className="w-full rounded border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-white"
              value={dohUrl}
              onChange={(e) => setDohUrl(e.target.value)}
              placeholder="https://cloudflare-dns.com/dns-query"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-sm text-zinc-400">Timeout (ms)</span>
            <input
              type="number"
              min={2000}
              max={12000}
              className="w-full rounded border border-zinc-700 bg-zinc-950 px-3 py-2 text-white"
              value={timeoutMs}
              onChange={(e) => setTimeoutMs(Number(e.target.value))}
            />
          </label>
          <label className="block sm:col-span-2">
            <span className="mb-1 block text-sm text-zinc-400">Blocklist (one domain per line, optional)</span>
            <textarea
              className="h-24 w-full rounded border border-zinc-700 bg-zinc-950 px-3 py-2 font-mono text-sm text-white"
              value={blocklist}
              onChange={(e) => setBlocklist(e.target.value)}
              placeholder={"ads.example.com\ntracker.example.com"}
            />
          </label>
        </div>
      </details>

      <button
        type="button"
        disabled={loading}
        onClick={() => void runLookup()}
        className="rounded-lg bg-teal-600 px-6 py-3 font-medium text-white hover:bg-teal-500 disabled:opacity-50"
      >
        {loading ? "Looking up…" : "Run lookup"}
      </button>

      {error && (
        <div className="rounded-lg border border-red-900/60 bg-red-950/40 p-4 text-red-100">
          <p className="font-medium">{error.error}</p>
          {error.hint && <p className="mt-2 text-sm text-red-200/90">{error.hint}</p>}
        </div>
      )}

      {result && (
        <div className="space-y-4 rounded-xl border border-zinc-700 bg-zinc-900/60 p-6">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded bg-zinc-800 px-2 py-1 font-mono text-sm text-teal-300">{result.rcode}</span>
            {result.blocked && (
              <span className="rounded bg-amber-900/50 px-2 py-1 text-sm text-amber-200">Blocked (policy)</span>
            )}
            <span className="rounded bg-zinc-800 px-2 py-1 text-sm text-zinc-300">Cache: {result.cache}</span>
            {result.truncated && (
              <span className="rounded bg-amber-900/50 px-2 py-1 text-sm text-amber-200">
                <Glossary term="tc">TC</Glossary> (truncated)
              </span>
            )}
          </div>
          <p className="text-zinc-200">{result.summary}</p>
          <p className="text-sm text-zinc-400">
            Latency (this request): <strong className="text-zinc-200">{result.latencyMs} ms</strong> — suggested{" "}
            <Glossary term="ttl">TTL</Glossary> for caching: <strong className="text-zinc-200">{result.cacheTtlSec}s</strong>
          </p>
          {result.answers.length > 0 ? (
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-zinc-700 text-zinc-400">
                  <th className="py-2 pr-4">Name</th>
                  <th className="py-2 pr-4">Type</th>
                  <th className="py-2 pr-4">Data</th>
                  <th className="py-2">TTL</th>
                </tr>
              </thead>
              <tbody>
                {result.answers.map((a, i) => (
                  <tr key={i} className="border-b border-zinc-800 text-zinc-200">
                    <td className="py-2 pr-4 font-mono">{a.name}</td>
                    <td className="py-2 pr-4">{a.type}</td>
                    <td className="py-2 pr-4 font-mono">{a.data}</td>
                    <td className="py-2">{a.ttl}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-sm text-zinc-400">
              No answer records.{" "}
              {result.rcode === "NXDOMAIN" ? (
                <Glossary term="nxdomain">NXDOMAIN</Glossary>
              ) : result.rcode === "NOERROR" ? (
                <Glossary term="nodata">NODATA</Glossary>
              ) : null}
            </p>
          )}
          {result.authoritySummary && (
            <p className="text-xs text-zinc-500">Authority (sample): {result.authoritySummary}</p>
          )}
        </div>
      )}
    </div>
  );
}
