# Mini DNS Resolver — Web companion (Vercel)

This folder is a **Next.js** web application that explains and demonstrates the same **DNS concepts** as the Python resolver in the parent repository — in a form that deploys cleanly to **Vercel**.

## What this is (and is not)

| On Vercel (this app) | On your laptop (parent `src/` + `server.py`) |
|----------------------|-----------------------------------------------|
| DNS-over-HTTPS to public resolvers | UDP stub + optional DoT / DoH upstream |
| Short-lived in-memory cache per server instance | Long-lived process + full cache / LRU flags |
| Great for teaching & quick lookups | Full README parity including `dig`, SIGUSR, Docker |

You **cannot** run the identical UDP listener on Vercel. Use **Lookup** here for DoH-based demos; use **Run locally** in the app (or the main repo README) for the real resolver.

## Deploy to Vercel

1. Push the repository to GitHub.
2. In Vercel: **New Project** → import the repo.
3. Set **Root Directory** to `web`.
4. Framework: **Next.js** (auto-detected). Deploy.

### Optional environment variables

| Variable | Purpose |
|----------|---------|
| `UPSTREAM_DOH_URL` | Default DoH URL (default: `https://cloudflare-dns.com/dns-query`) |
| `UPSTREAM_TIMEOUT_MS` | Upper bound for upstream fetch (default `8000`) |
| `DEMO_MAX_TTL_SEC` | Cap TTL stored in the server cache (mirrors `--demo-max-ttl`) |
| `PLAYGROUND_RESET_SECRET` | If set, `POST /api/playground/reset` requires header `x-playground-token: <secret>` |

## Local development

```bash
cd web
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Tests

```bash
npm test
```

## Rate limiting

The API uses a simple per-IP in-memory limiter (suitable for demos). For production under heavy traffic, add **Vercel KV** or similar.
