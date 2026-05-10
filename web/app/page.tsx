import Link from "next/link";

export default function HomePage() {
  return (
    <div className="space-y-10">
      <div className="space-y-4">
        <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">Explore DNS like a mini resolver</h1>
        <p className="max-w-2xl text-lg text-zinc-400">
          This web companion helps you <strong className="text-zinc-200">look up domains</strong>, understand{" "}
          <strong className="text-zinc-200">cache hits</strong>, <strong className="text-zinc-200">TTL</strong>, and{" "}
          <strong className="text-zinc-200">blocklists</strong> — the same ideas as the Mini DNS Resolver README — in a
          browser-friendly way.
        </p>
        <p className="max-w-2xl text-sm text-amber-200/90">
          Important: the Python resolver listens on <strong>UDP</strong> on your machine. Vercel cannot host that.
          Here we use <strong>DNS-over-HTTPS</strong> to real resolvers. For UDP, DoT, and full demos, use{" "}
          <Link href="/local" className="text-teal-400 underline">
            Run locally
          </Link>
          .
        </p>
      </div>
      <div className="flex flex-wrap gap-4">
        <Link
          href="/lookup"
          className="rounded-lg bg-teal-600 px-6 py-3 font-medium text-white hover:bg-teal-500"
        >
          Open Lookup lab
        </Link>
        <Link
          href="/learn"
          className="rounded-lg border border-zinc-600 px-6 py-3 font-medium text-zinc-200 hover:border-teal-600"
        >
          Learn features
        </Link>
      </div>
    </div>
  );
}
