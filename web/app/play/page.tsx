import Link from "next/link";
import { Glossary } from "@/components/Glossary";
import { ClearCacheButton } from "@/components/ClearCacheButton";

export const metadata = { title: "Playgrounds — Mini DNS companion" };

export default function PlayPage() {
  return (
    <div className="space-y-12">
      <div>
        <h1 className="text-2xl font-bold text-white">Playgrounds</h1>
        <p className="mt-2 max-w-2xl text-zinc-400">
          Short experiments that mirror README ideas. Heavy lifting for UDP / DoT / injected TC remains on the{" "}
          <Link href="/local" className="text-teal-400 underline">
            Python project
          </Link>
          .
        </p>
      </div>

      <section id="ttl" className="scroll-mt-24 space-y-3 rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
        <h2 className="text-lg font-semibold text-white">TTL (Feature 2)</h2>
        <p className="text-sm text-zinc-400">
          After a successful lookup in the{" "}
          <Link href="/lookup" className="text-teal-400 underline">
            Lookup lab
          </Link>
          , note the <Glossary term="ttl">TTL</Glossary> column — it is how long answers may be cached. On Vercel, you
          can set <code className="rounded bg-zinc-800 px-1">DEMO_MAX_TTL_SEC</code> in the environment to cap cached TTL
          (same idea as <code className="rounded bg-zinc-800 px-1">--demo-max-ttl</code> on the Python server).
        </p>
      </section>

      <section id="tcp" className="scroll-mt-24 space-y-3 rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
        <h2 className="text-lg font-semibold text-white">TCP fallback when UDP is truncated (Feature 3)</h2>
        <p className="text-sm text-zinc-400">
          When the <Glossary term="tc">TC</Glossary> bit is set, a full resolver retries over TCP. Public resolvers rarely
          show TC in a simple A query, so the README uses an <strong className="text-zinc-200">injected mock</strong> in{" "}
          <code className="rounded bg-zinc-800 px-1">demo.py</code>. Run locally:
        </p>
        <pre className="overflow-x-auto rounded-lg bg-black/50 p-4 font-mono text-xs text-zinc-300">
          python demo.py --offline
        </pre>
      </section>

      <section id="lru" className="scroll-mt-24 space-y-3 rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
        <h2 className="text-lg font-semibold text-white">LRU cache (Feature 8)</h2>
        <p className="text-sm text-zinc-400">
          The web API keeps a small in-memory <Glossary term="cache">cache</Glossary> per server instance with LRU
          eviction. Many distinct names will push older entries out — same idea as <code className="rounded bg-zinc-800 px-1">--max-positive-cache</code>{" "}
          on the Python resolver.
        </p>
      </section>

      <section className="space-y-3 rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
        <h2 className="text-lg font-semibold text-white">Clear server demo cache</h2>
        <p className="text-sm text-zinc-400">
          If you set <code className="rounded bg-zinc-800 px-1">PLAYGROUND_RESET_SECRET</code> in Vercel, POST with header{" "}
          <code className="rounded bg-zinc-800 px-1">x-playground-token</code>. Without a secret, reset is open (fine for
          local dev only).
        </p>
        <ClearCacheButton />
      </section>
    </div>
  );
}
