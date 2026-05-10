import Link from "next/link";

const features = [
  { n: 1, title: "Cache hit vs miss", href: "/lookup", note: "Run the same lookup twice with server cache on." },
  { n: 2, title: "TTL expiry", href: "/play#ttl", note: "See TTL on answers; optional DEMO_MAX_TTL_SEC on the server." },
  { n: 3, title: "TCP fallback (TC)", href: "/play#tcp", note: "Explained + link to local Python demo with injected TC." },
  { n: 4, title: "Negative caching (NXDOMAIN / NODATA)", href: "/lookup", note: "Try presets: nxdomain.test and doesnotexist.example.com." },
  { n: 5, title: "DNS-over-TLS", href: "/local", note: "Run python run.py option 2 locally — not on Vercel." },
  { n: 6, title: "DNS-over-HTTPS", href: "/lookup", note: "This web app uses DoH from the server, like README Feature 6." },
  { n: 7, title: "Blocklist", href: "/lookup", note: "Optional blocklist textarea in Lookup lab (Advanced)." },
  { n: 8, title: "LRU eviction", href: "/play#lru", note: "Server cache is LRU-bounded per instance." },
  { n: 9, title: "SIGUSR1 stats", href: "/local", note: "Python resolver only." },
  { n: 10, title: "JSON logs", href: "/local", note: "Python --json-logs." },
  { n: 11, title: "Trace mode", href: "/local", note: "Python --trace." },
  { n: 12, title: "Benchmark", href: "/local", note: "python run.py option 7 in the repo." },
  { n: 13, title: "Web dashboard", href: "/local", note: "FastAPI dashboard with the Python server." },
  { n: 14, title: "Docker", href: "/local", note: "docker compose from repository root." },
];

export const metadata = { title: "Learn — Mini DNS companion" };

export default function LearnPage() {
  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-white">Learn (README map)</h1>
      <p className="max-w-2xl text-zinc-400">
        Each item matches a section in the project README. Items marked “local” need the Python resolver on your machine
        or Docker.
      </p>
      <ul className="space-y-3">
        {features.map((f) => (
          <li key={f.n} className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="font-medium text-white">
                Feature {f.n}: {f.title}
              </span>
              <Link href={f.href} className="text-sm text-teal-400 hover:underline">
                Try / read →
              </Link>
            </div>
            <p className="mt-1 text-sm text-zinc-500">{f.note}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
