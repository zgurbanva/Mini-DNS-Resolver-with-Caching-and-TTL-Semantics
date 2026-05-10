"use client";

import type { ReactNode } from "react";

const tips: Record<string, string> = {
  ttl: "Time To Live: how long a resolver may reuse this answer before asking upstream again.",
  cache:
    "Cache hit means this app answered from its short-lived in-memory store (per server instance), similar in spirit to the Python resolver’s RAM cache.",
  nxdomain: "The domain name does not exist in the DNS.",
  nodata: "The name exists, but there is no record of the type you asked for (e.g. no AAAA).",
  doh: "DNS-over-HTTPS: DNS wrapped inside a normal HTTPS request (what this web app uses on Vercel).",
  tc: "Truncated: UDP response was too large; a full resolver retries over TCP. True TCP fallback is demonstrated when you run the Python project locally.",
};

export function Glossary({ term, children }: { term: keyof typeof tips; children: ReactNode }) {
  return (
    <abbr title={tips[term]} className="cursor-help underline decoration-dotted decoration-zinc-500">
      {children}
    </abbr>
  );
}
