import Link from "next/link";

const links = [
  { href: "/", label: "Home" },
  { href: "/lookup", label: "Lookup" },
  { href: "/learn", label: "Learn" },
  { href: "/play", label: "Playgrounds" },
  { href: "/local", label: "Run locally" },
];

export function SiteNav() {
  return (
    <header className="border-b border-zinc-800 bg-zinc-950/80 backdrop-blur">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-3">
        <Link href="/" className="font-semibold tracking-tight text-teal-400">
          Mini DNS Companion
        </Link>
        <nav className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-zinc-300">
          {links.map((l) => (
            <Link key={l.href} href={l.href} className="hover:text-white">
              {l.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
