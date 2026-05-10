# Mini DNS Resolver (forwarding stub)

Python **asyncio** UDP resolver that forwards to an upstream DNS server (default **1.1.1.1**), caches **A** / **AAAA** answers with **TTL** semantics (minimum TTL in the matching answer RRsets), performs **negative caching** for **NXDOMAIN** with a capped TTL (`min(300, SOA minimum)` when authority SOA is present, otherwise **60** seconds), and retries on the **TC** bit using **TCP**.

## New here? Project map (what each file is for)

| File / folder | Role in one sentence |
|---------------|----------------------|
| `server.py` | **Run this** to start the UDP resolver: listens for DNS questions, uses the cache, talks to **upstream** on misses. |
| `cache.py` | In-memory **TTL** cache for `A` / `AAAA`; short **NXDOMAIN** negative cache. |
| `protocol.py` | Sends queries **UDP first** to upstream; if the reply has **TC** (truncated), retries over **TCP**. |
| `utils.py` | Colored logs: `[CACHE_HIT]`, `[CACHE_MISS]`, `[TCP_FALLBACK]`, `[ERROR]` plus latency in **ms**. |
| `demo.py` | **Automated walkthrough**: cold vs warm cache, TTL expiry with a cap, and a **mocked** TC→TCP path (good for slides). |
| `resolver.py` | Thin alias: same as `python server.py`. |
| `requirements.txt` | Python dependencies (`dnspython`, `rich`, `pytest`). |
| `tests/` | Automated checks; run with `pytest`. |
| `prompt.md` / `ProjectRequirements.md` | Assignment wording and theory topics your report should cover. |

**One-line story:** Your laptop sends a DNS query to **this program** (stub resolver on `127.0.0.1:PORT`). If the answer is not in **cache**, the program asks **upstream** (e.g. Cloudflare `1.1.1.1`), caches the result for **TTL** seconds, and replies to you.

---

## Run

Use a virtual environment (recommended on macOS/Homebrew Python):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Resolver server

Default listen port is **5353** so unprivileged users avoid binding **53** (binding port 53 typically requires root).

```bash
python server.py --bind 127.0.0.1 --port 5353 --upstream 1.1.1.1
```

If you see **`OSError: [Errno 48] Address already in use`**, another process already owns that UDP port (on macOS, **mDNS/Bonjour** commonly uses **5353**). Stop the other process or pick a free port, e.g. `--port 55353`.

Optional demo-only TTL cap (also `DNS_RESOLVER_DEMO_MAX_TTL`):

```bash
python server.py --demo-max-ttl 5
```

Legacy shim:

```bash
python resolver.py
```

### Demo

```bash
python demo.py
```

- Runs an **offline** injected **UDP TC → TCP** harness (check stderr for `[TCP_FALLBACK]`).
- Starts an embedded server on an ephemeral port for **cold vs warm** latency on a real name (`--domain`, default `example.com`).
- Shows **TTL expiry** using `--demo-max-ttl` on the embedded server plus `--ttl-pause` sleep.

Offline-only (no upstream):

```bash
python demo.py --offline
```

### Tests

```bash
pytest -q
```

---

## Hands-on: prove it works (two terminals)

Use this flow the first time and when demoing. Pick a **free UDP port** if `5353` fails (see note above); examples use **`55353`**.

### 0) One-time setup

```bash
cd /path/to/Mini-DNS-Resolver-with-Caching-and-TTL-Semantics
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest -q                          # optional but good before a presentation
```

### 1) Terminal A — start **your** resolver (the “front door”)

```bash
source .venv/bin/activate
python server.py --bind 127.0.0.1 --port 55353 --upstream 1.1.1.1
```

Leave this running. You should see: `Listening UDP 127.0.0.1:55353 upstream=1.1.1.1 …`

- **`--upstream 1.1.1.1`** is Cloudflare’s public DNS. That is the **real internet resolver** your stub talks to after a cache miss. You can say to your professor: *“Misses go to 1.1.1.1; hits never leave this process.”*
- **`--upstream 8.8.8.8`** works the same way (Google) if you want to show it is configurable.

### 2) Terminal B — send a **real DNS question** with `dig`

`dig` is a normal DNS client; `-p` is the **port** your server listens on.

**First query (cold cache — should be slower, server logs `[CACHE_MISS]`):**

```bash
dig @127.0.0.1 -p 55353 example.com A +tries=1 +retry=0
```

**Same query again (warm cache — should be fast, server logs `[CACHE_HIT]`):**

```bash
dig @127.0.0.1 -p 55353 example.com A +tries=1 +retry=0
```

Watch **Terminal A** while you run those: you should see **`[CACHE_MISS]`** then **`[CACHE_HIT]`**, with a much smaller latency on the second line. That is the assignment’s “cold vs warm” behavior.

**Try IPv6 (`AAAA`):**

```bash
dig @127.0.0.1 -p 55353 cloudflare.com AAAA +tries=1 +retry=0
```

Repeat the same command to see another warm hit.

### 3) Optional — scripted demo (narrates the story for you)

With **network** available (uses real upstream for cold/warm/TTL parts):

```bash
source .venv/bin/activate
python demo.py
```

- Prints **client-side** cold vs warm timings and a **short TTL cap** expiry scenario.
- The **TC → TCP** part is **injected with mocks** so it always works even if live DNS never sets `TC` for that name.

No upstream needed for only the synthetic TC test:

```bash
python demo.py --offline
```

### 4) What to say in front of your professor (30-second script)

1. *“This is a **forwarding stub resolver**: it only answers what we ask it; recursion lives at **upstream**.”*  
2. *“`dig @127.0.0.1 -p PORT` sends queries **to our code**, not to the system resolver.”*  
3. *“First lookup is a **miss** → we contact **`--upstream`** (e.g. 1.1.1.1) and **cache** the answer with TTL.”*  
4. *“Second lookup is a **hit** → same answer from RAM; logs show **`[CACHE_HIT]`** and sub‑millisecond to a few ms.”*  
5. *“`demo.py` and `tests/` back up the same behavior automatically.”*

---

## Behavior notes

- **Non–A/AAAA queries** are **forwarded without caching** (still honors UDP→TCP on TC via `protocol.py`).
- Malformed or oversized (>4096 B) datagrams are dropped after logging `[ERROR]` (no response if the query cannot be parsed safely).

## Theory (course alignment)

- **DNS roles:** This service is a **forwarding stub resolver**: it does not implement full recursion or authority; it sends iterative/recursive work to the configured upstream.
- **Record types:** **A** (IPv4) and **AAAA** (IPv6) answers carry **TTL** fields telling resolvers how long the data may be reused; the cache stores entries keyed by `(name, type)` and expires them using a **monotonic** clock.
- **Caching trade-off:** TTL is a deliberate correctness/performance compromise—serving data past expiry improves latency but can violate freshness expectations if authoritative data changed.
- **Negative caching:** **NXDOMAIN** is cached briefly to reduce hammering upstream for names that do not exist; overly long negative TTL risks delaying visibility of newly created names.
- **UDP vs TCP:** DNS favors **UDP** for latency; when responses are truncated (**TC**), **TCP** retrieves the full message—this project logs `[TCP_FALLBACK]` when that path is taken.
