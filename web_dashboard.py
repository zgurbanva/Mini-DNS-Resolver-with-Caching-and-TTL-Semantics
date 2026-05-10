import time
import dnslib
from flask import Flask, request, jsonify

app = Flask(__name__)

HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Mini DNS Resolver - Core Control</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        
        body {
            background-color: #15002b;
            color: #d1bdf5;
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            display: flex;
            height: 95vh;
        }
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-thumb { background: #ff00ff; }
        
        .glow-cyan { color: #00f3ff; font-weight: bold; }
        .glow-magenta { color: #ff00ff; font-weight: bold; }
        
        .sidebar {
            width: 30%;
            border: 2px solid #b700ff;
            padding: 20px;
            box-shadow: 0 0 15px #b700ff inset;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            background: rgba(20, 0, 40, 0.5);
        }
        
        .sidebar h2 {
            border-bottom: 2px solid #ff00ff;
            padding-bottom: 10px;
            text-align: center;
        }
        
        .feature-item {
            margin: 15px 0;
            padding: 10px;
            border-left: 3px solid #ff00ff;
            background: rgba(255, 0, 255, 0.05);
        }
        
        .main {
            width: 70%;
            margin-left: 20px;
            display: flex;
            flex-direction: column;
        }
        
        .query-panel {
            border: 2px solid #ff00ff;
            padding: 20px;
            box-shadow: 0 0 15px #ff00ff inset;
            margin-bottom: 20px;
            display: flex;
            gap: 15px;
            background: rgba(20, 0, 40, 0.5);
        }
        
        .automated-panel {
            border: 2px solid #00ff73;
            padding: 15px;
            box-shadow: 0 0 15px #00ff73 inset;
            margin-bottom: 20px;
            background: rgba(0, 50, 20, 0.4);
            text-align: center;
        }
        
        .sys-button {
            background: #00ff73;
            color: #000;
            border: none;
            padding: 10px 20px;
            font-weight: bold;
            font-size: 1.1em;
            cursor: pointer;
            box-shadow: 0 0 10px #00ff73;
            text-transform: uppercase;
            transition: 0.2s;
        }
        .sys-button:hover { background: #fff; box-shadow: 0 0 20px #fff; }
        
        .metrics-board {
            margin-top: 10px;
            font-size: 1.1em;
            color: #fff;
            display: none;
        }
        
        input[type="text"] {
            background: #250045;
            border: 1px solid #b700ff;
            color: #00f3ff;
            padding: 15px;
            flex-grow: 1;
            font-family: inherit;
            font-size: 1.3em;
            outline: none;
            box-shadow: 0 0 5px #b700ff;
        }
        
        button {
            background: #b700ff;
            color: #fff;
            border: none;
            padding: 15px 30px;
            font-weight: bold;
            font-family: inherit;
            font-size: 1.3em;
            cursor: pointer;
            box-shadow: 0 0 10px #b700ff;
            text-transform: uppercase;
            transition: 0.2s;
        }
        
        button:hover { background: #ff00ff; box-shadow: 0 0 20px #ff00ff; color: white; }
        
        .terminal {
            background: rgba(25, 0, 50, 0.6);
            flex-grow: 1;
            border: 1px solid #b700ff;
            padding: 20px;
            overflow-y: auto;
            font-size: 1.2em;
            box-shadow: 0 0 10px #b700ff inset;
        }
        
        .log-hit { color: #00ff73; font-weight: bold; }
        .log-miss { color: #ff00ff; font-weight: bold; }
        
        .footer {
            margin-top: auto;
            text-align: center;
            padding-top: 20px;
            font-size: 0.9em;
            color: #bfa3e8;
        }
    </style>
</head>
<body>

    <div class="sidebar">
        <h2 class="glow-magenta">CORE ARCHITECTURE</h2>
        
        <div class="feature-item">
            <strong class="glow-cyan">1. Absolute TTL Expiry</strong><br>
            Calculates exact T(now) + TTL to destroy stale cache precisely.
        </div>
        <div class="feature-item">
            <strong class="glow-cyan">2. Negative Caching</strong><br>
            Caches NXDOMAIN errors locally to prevent strict upstream flooding.
        </div>
        <div class="feature-item">
            <strong class="glow-cyan">3. Active Prefetching</strong><br>
            Fires background thread fetches at 90% lifespan to keep cache HOT.
        </div>
        <div class="feature-item">
            <strong class="glow-cyan">4. Persistence System</strong><br>
            Serializes memory to disk (JSON) surviving server reboots.
        </div>
        <div class="feature-item">
            <strong class="glow-cyan">5. Multi-Upstream Balancing</strong><br>
            Round-robin failovers between multiple providers (e.g. 8.8.8.8, 1.1.1.1).
        </div>
        <div class="feature-item">
            <strong class="glow-cyan">6. UDP Metric Telemetry</strong><br>
            Tracks latency drops via high-res perf_counter mapping.
        </div>
        
        <div class="footer glow-cyan">
            DESIGNED & DEVELOPED BY:<br>
            <strong style="color:white; font-size:1.2em;">ZEYNAB AND NURIDA</strong>
        </div>
    </div>

    <div class="main">
        <div class="query-panel">
            <input type="text" id="domainInput" placeholder="AWAITING DOMAIN INPUT... (e.g. google.com)" value="google.com">
            <button onclick="fireQuery()">EXECUTE</button>
        </div>
        
        <div class="automated-panel">
            <button class="sys-button" onclick="runAutomatedTests()" id="runTestsBtn">INITIALIZE AUTOMATED TEST MATRIX</button>
            <div class="metrics-board" id="metricsBoard"></div>
        </div>
        
        <div class="terminal" id="terminalArea">
            <div style="color: #555;">[SYSTEM] Terminal online... Polling real-life Backend Telemetry...</div>
            <br>
        </div>
    </div>

    <script>
        const term = document.getElementById('terminalArea');
        let displayedLogs = new Set();
        let isPolling = true;

        async function pollLogs() {
            if(!isPolling) return;
            try {
                const response = await fetch("/logs");
                const data = await response.json();
                let added = false;
                
                for(let line of data.logs) {
                    if(!displayedLogs.has(line)) {
                        displayedLogs.add(line);
                        
                        // Parse formatting colors for detailed output
                        let cleanLine = line.replace(/\\n/g, "");
                        if(cleanLine.includes("[MISS]")) {
                            term.innerHTML += `<div class="log-miss">🚀 ${cleanLine}</div>`;
                        } else if(cleanLine.includes("[HIT]")) {
                            term.innerHTML += `<div class="log-hit">⚡ ${cleanLine}</div>`;
                        } else if(cleanLine.includes("[UPSTREAM]")) {
                            term.innerHTML += `<div class="glow-magenta">🌐 ${cleanLine}</div>`;
                        } else if(cleanLine.includes("[UDP]")) {
                            term.innerHTML += `<div style="color:#00f3ff; font-weight:bold;">📦 ${cleanLine}</div>`;
                        } else if(cleanLine.includes("[CACHE]")) {
                            term.innerHTML += `<div style="color:#aaa;">💾 ${cleanLine}</div>`;
                        } else {
                            term.innerHTML += `<div style="color:#e0e0e0;">${cleanLine}</div>`;
                        }
                        added = true;
                    }
                }
                
                if(added) {
                    term.scrollTop = term.scrollHeight;
                }
            } catch (err) {
                // Ignore silent poll errors
            }
            setTimeout(pollLogs, 300);
        }
        
        // Start background polling
        pollLogs();

        async function fireQuery() {
            const domain = document.getElementById('domainInput').value;
            
            // Add outgoing log
            term.innerHTML += `<div><br><span style="color:white;">[SEND]</span> Dispatching query for: <span class="glow-cyan">${domain}</span></div>`;
            term.scrollTop = term.scrollHeight;

            try {
                // Background trigger
                const response = await fetch("/query", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ domain: domain })
                });
                
                const data = await response.json();
                
                const cacheColor = data.cache === "HIT" ? "log-hit" : "log-miss";
                const latencyStr = `Lat: ${data.latency} ms`;
                
                // Allow a small delay so polling logs appear before the final RECV block
                setTimeout(() => {
                    term.innerHTML += `<div style="margin-bottom:10px; border-left: 2px solid #b700ff; padding-left: 10px; margin-top: 5px;">
                        <span class="glow-cyan">[RECV UI]</span> Final DNS Resolution for <span style="color:white">${data.domain}</span><br>
                        Status: [${data.status}] | 
                        Cache: <span class="${cacheColor}">[${data.cache}]</span> | 
                        Time: <span class="${cacheColor}">${latencyStr}</span> <br>
                        IP Addresses: <strong style="color:#00ff73;">${data.ips}</strong>
                    </div>`;
                    term.scrollTop = term.scrollHeight;
                }, 500);

            } catch (err) {
                term.innerHTML += `<div style="color:red; margin-bottom:10px;">[ERROR] Server connection timeout. Is resolver.py running?</div>`;
            }
        }
        
        let coldLatencies = [];
        let warmLatencies = [];

        async function doTestQuery(domain, isWarm) {
            const t_start = performance.now();
            try {
                const response = await fetch("/query", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ domain: domain })
                });
                const data = await response.json();
                if (isWarm) warmLatencies.push(data.latency);
                else coldLatencies.push(data.latency);
            } catch (e) {}
        }
        
        function sleep(ms) {
            return new Promise(resolve => setTimeout(resolve, ms));
        }

        async function runAutomatedTests() {
            const btn = document.getElementById("runTestsBtn");
            const metrics = document.getElementById("metricsBoard");
            btn.disabled = true;
            btn.innerText = "RUNNING DIAGNOSTICS...";
            metrics.style.display = "block";
            metrics.innerHTML = "<span style='color:#ff00ff'>[EXECUTING SCENARIO 1: COLD CACHE...]</span>";
            
            coldLatencies = [];
            warmLatencies = [];
            const queries = ['google.com', 'example.com', 'nonexistent.domain.xyz'];
            
            // Scenario 1: Cold Cache
            for (let q of queries) {
                await doTestQuery(q, false);
                await sleep(800);
            }
            
            // Scenario 2: Warm Cache
            metrics.innerHTML = "<span style='color:#00ff73'>[EXECUTING SCENARIO 2: WARM CACHE...]</span>";
            for (let q of queries) {
                await doTestQuery(q, true);
                await sleep(500);
            }
            for (let q of queries) {
                await doTestQuery(q, true);
                await sleep(500);
            }
            
            // Scenario 3: Expiry test
            metrics.innerHTML = "<span style='color:#00f3ff'>[EXECUTING SCENARIO 3: ABSOLUTE TTL EXPIRY QUEUE (4s)...]</span>";
            await doTestQuery("expiry.test.lcl", false); // MISS
            await sleep(500);
            await doTestQuery("expiry.test.lcl", true); // HIT
            
            await sleep(4000); // Wait for 3 sec TTL to expire
            await doTestQuery("expiry.test.lcl", false); // Refetch MISS
            await sleep(1000);

            // Calculate Math
            let coldAvg = coldLatencies.reduce((a, b) => a + b, 0) / coldLatencies.length;
            let warmAvg = warmLatencies.reduce((a, b) => a + b, 0) / warmLatencies.length;
            let gain = ((coldAvg - warmAvg) / coldAvg) * 100;
            
            metrics.innerHTML = `
                <strong style='color:#00f3ff'>Cold Latency (Network): ${coldAvg.toFixed(2)} ms</strong> | 
                <strong style='color:#00ff73'>Warm Latency (Memory): ${warmAvg.toFixed(2)} ms</strong> | 
                <strong style='color:#ff00ff'>Efficiency Gain: ${gain.toFixed(1)}% 🔥</strong>
            `;
            btn.innerText = "TESTS COMPLETED";
            setTimeout(() => { btn.disabled = false; btn.innerText = "INITIALIZE AUTOMATED TEST MATRIX"; }, 3000);
        }

        // Allow pressing Enter
        document.getElementById("domainInput").addEventListener("keypress", function(event) {
            if (event.key === "Enter") fireQuery();
        });
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return HTML_PAGE

@app.route("/logs", methods=["GET"])
def get_logs():
    try:
        with open("resolver.log", "r") as f:
            lines = f.readlines()
            return jsonify({"logs": lines[-100:]}) # return last 100 lines
    except Exception as e:
        return jsonify({"logs": []})

@app.route("/query", methods=["POST"])
def query():
    domain = request.json.get("domain", "")
    if not domain:
        return jsonify({"error": "Empty domain"}), 400
        
    q = dnslib.DNSRecord.question(domain)
    t_start = time.perf_counter()
    
    try:
        req_bytes = q.pack()
        response = q.send("127.0.0.1", 5053, timeout=2) # Sending via UDP
        response_bytes = len(response)
        
        t_finish = time.perf_counter()
        reply = dnslib.DNSRecord.parse(response)
        rcode = dnslib.RCODE[reply.header.rcode]
        latency = (t_finish - t_start) * 1000
        status = rcode
        ips = [str(rr.rdata) for rr in reply.rr if getattr(rr, 'rtype', 1) == 1]
        ip_str = ", ".join(ips) if ips else "No A-Records"
    except Exception as e:
        status = "TIMEOUT"
        latency = 0
        response_bytes = 0
        ip_str = "N/A"
        
    # We infer hit vs miss via extremely low network time threshold
    cache_type = "HIT" if latency < 10 and latency > 0 and status != "TIMEOUT" else "MISS"
    
    # Remove fake random upstream, we want real life
    upstream_str = None
    
    # Do not clamp latency artificially, real life Python RAM dict performance is good enough.
        
    return jsonify({
        "domain": domain,
        "latency": round(latency, 2),
        "status": status,
        "cache": cache_type,
        "bytes": response_bytes,
        "ips": ip_str,
        "upstream": upstream_str
    })

if __name__ == "__main__":
    print("\n" + "="*50)
    print("🚀 WEB DASHBOARD LAUNCHED: http://127.0.0.1:5000")
    print("Ensure resolver.py is running in another terminal tab!")
    print("="*50 + "\n")
    app.run(port=5000, debug=False)
