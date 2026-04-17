# Mini DNS Resolver with Caching and TTL Semantics
**By Zeynab and Nurida**

---

## ⚡ Environment Setup
Make sure you have standard Python 3.
1. `python3 -m venv venv`
2. `source venv/bin/activate` 
3. `pip install -r requirements.txt`

## 🚀 Live Demo & Analytical Report (Recommended)
We have built an automated, futuristic Terminal UI that explicitly proves all our caching metrics.

Simply run:
```bash
python futuristic_demo.py
```
This single script will boot up the DNS server automatically and run our visual test suite.

**What it Demonstrates:**
1. **Cold Cache Behavior (MISS)**: First queries organically hit the simulated internet and log standard upstream fetch latencies.
2. **Warm Cache Behavior (HIT)**: Identical subsequent queries return from our Python RAM dictionary instantly, heavily reducing query time.
3. **Negative Caching (NXDOMAIN)**: Unresolved domains (`nonexistent.domain.xyz`) correctly return their status and fetch time is cached too.
4. **TTL Expiry Cycle**: Requests our test domain `expiry.test.lcl` (mocked with a strong 3-second TTL). The system demonstrates a cache HIT, forces a 4-second waiting queue, and then requests it again to explicitly prove the Absolute Expiry (`abs_expiry`) correctly purged it from memory and resulted in a refetch (MISS).
5. **Efficiency Metrics (Analytical Report)**: Prints out a metric tracker proving the exact latency reduction achieved using real-time Python timers (`time.perf_counter()`).

## 🛠 Running the Resolver Manually
If you want to run the server as a raw daemon to debug it on your own without the UI:
```bash
python resolver.py
```
This will start the DNS server listening on `127.0.0.1:5053`.

You can query it manually using `dig`:
```bash
dig @127.0.0.1 -p 5053 google.com
```