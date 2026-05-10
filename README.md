# Mini DNS Resolver with Caching and TTL Semantics
**By Zeynab and Nurida**

---

## ⚡ Environment Setup
Make sure you have standard Python 3.
1. `python3 -m venv venv`
2. `source venv/bin/activate` 
3. `pip install -r requirements.txt`

---

## 🌐 1. The Web Dashboard (Website Version - Recommended)
We created a beautiful frontend graphical interface that connects to our local DNS server and dynamically shows UDP datagram packets being transported and latency calculations!

**How to run it:**
1. Open terminal and run the background server:
   ```bash
   python resolver.py
   ```
2. Open a *new* terminal, activate the environment, and run the website:
   ```bash
   python web_dashboard.py
   ```
3. Open your browser and go to: **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

You can manually type domains (like `google.com`), and watch the terminal inside the website log the UDP packet bites and show the difference in latency for `[MISS]` and `[HIT]`.

---

## 💻 2. Automated Terminal Demo (Terminal Version)
If you prefer a fast, automated test suite in the console, we built a futuristic Terminal UI that explicitly proves all our caching metrics.

Simply run:
```bash
python futuristic_demo.py
```
This single script will boot up the DNS server automatically and run our visual test suite.

**What it Demonstrates:**
1. **Cold Cache Behavior (MISS)**: First queries organically hit the simulated internet and log standard upstream fetch latencies.
2. **Warm Cache Behavior (HIT)**: Identical subsequent queries return from our Python RAM dictionary instantly, heavily reducing query time.
3. **Negative Caching (NXDOMAIN)**: Unresolved domains (`nonexistent.domain.xyz`) correctly return.
4. **TTL Expiry Cycle**: Tests `expiry.test.lcl` (mocked with a strong 3-second TTL). The system demonstrates a cache HIT, forces a 4-second wait, and requests it again to prove it correctly purged from memory (MISS).
5. **Efficiency Metrics**: Prints out a metric tracker proving the exact latency reduction achieved using real-time timers.

---

## 🛠 3. Running the Resolver Manually
If you want to run the server as a raw daemon to debug it on your own without any UIs:
```bash
python resolver.py
```
This will start the DNS server listening on `127.0.0.1:5053`.

You can query it manually using `dig`:
```bash
dig @127.0.0.1 -p 5053 google.com
```