import socket
import threading
import time
import json
import base64
import os
import signal
import sys
from collections import defaultdict
from queue import Queue

from dnslib import DNSRecord, RCODE, QTYPE

CACHE_FILE = 'cache.json'
UPSTREAM_SERVERS = [('8.8.8.8', 53), ('1.1.1.1', 53)]
NEGATIVE_CACHE_TTL = 60  # seconds

class DnsCache:
    def __init__(self):
        self.lock = threading.Lock()
        self.entries = {}
        self.load_cache()

    def get(self, qname, qtype):
        with self.lock:
            now = time.time()
            if (qname, qtype) in self.entries:
                entry = self.entries[(qname, qtype)]
                if now < entry['absolute_expiry']:
                    return entry
                else:
                    del self.entries[(qname, qtype)]
                    return 'EXPIRED'
            return 'MISS'

    def set(self, qname, qtype, record, absolute_expiry, soft_ttl, is_negative):
        with self.lock:
            self.entries[(qname, qtype)] = {
                'packet': base64.b64encode(record.pack()).decode('utf-8'),
                'absolute_expiry': absolute_expiry,
                'soft_ttl': soft_ttl,
                'is_negative': is_negative
            }

    def save_cache(self):
        with self.lock:
            now = time.time()
            # Clean expired before saving
            valid_entries = {
                f"{k[0]}|{k[1]}": v
                for k, v in self.entries.items()
                if now < v['absolute_expiry']
            }
            try:
                with open(CACHE_FILE, 'w') as f:
                    json.dump(valid_entries, f)
                print(f"[CACHE] Saved {len(valid_entries)} entries to {CACHE_FILE}")
            except Exception as e:
                print(f"[CACHE] Failed to save cache: {e}")

    def load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r') as f:
                    data = json.load(f)
                
                now = time.time()
                loaded = 0
                for k_str, v in data.items():
                    if now < v['absolute_expiry']:
                        qname, str_qtype = k_str.split('|')
                        self.entries[(qname, int(str_qtype))] = v
                        loaded += 1
                print(f"[CACHE] Loaded {loaded} valid entries from {CACHE_FILE}")
            except Exception as e:
                print(f"[CACHE] Failed to load cache: {e}")

class MiniDNSResolver:
    def __init__(self, host='127.0.0.1', port=5053):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((self.host, self.port))
        self.cache = DnsCache()
        self.upstream_index = 0
        self.prefetch_queue = Queue()
        self.running = True
        
        # Start prefetch worker
        threading.Thread(target=self.prefetch_worker, daemon=True).start()

    def get_upstream(self):
        server = UPSTREAM_SERVERS[self.upstream_index]
        self.upstream_index = (self.upstream_index + 1) % len(UPSTREAM_SERVERS)
        return server

    def fetch_upstream(self, query_data):
        upstream = self.get_upstream()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(2.0)
            try:
                s.sendto(query_data, upstream)
                response_data, _ = s.recvfrom(4096)
                return response_data
            except Exception as e:
                print(f"[ERROR] Upstream fetch failed: {e}")
                return None

    def process_upstream_response(self, response_data, qname, qtype):
        if not response_data:
            return None
        try:
            record = DNSRecord.parse(response_data)
            now = time.time()
            
            # Extract smallest TTL from answers
            ttl = 300  # Default fallback
            is_negative = False
            
            if record.header.rcode != RCODE.NOERROR:
                is_negative = True
                ttl = NEGATIVE_CACHE_TTL
            elif len(record.rr) > 0:
                ttl = min(rr.ttl for rr in record.rr)
                
            # Demo override: artificially force a 3-second TTL for our expiry test
            if "expiry.test.lcl" in qname:
                ttl = 3
                
            absolute_expiry = now + ttl
            soft_ttl = now + (ttl * 0.9)  # 90% threshold for prefetch
            
            self.cache.set(qname, qtype, record, absolute_expiry, soft_ttl, is_negative)
            return record
            
        except Exception as e:
            print(f"[ERROR] Parsing response failed: {e}")
            return None

    def prefetch_worker(self):
        while self.running:
            try:
                qname, qtype, query_data = self.prefetch_queue.get(timeout=1.0)
                print(f"[*] Prefetching {qname} ({QTYPE[qtype]})...")
                response_data = self.fetch_upstream(query_data)
                self.process_upstream_response(response_data, str(qname), qtype)
                self.prefetch_queue.task_done()
            except:
                pass

    def handle_request(self, data, addr):
        t_start = time.perf_counter()
        
        try:
            query = DNSRecord.parse(data)
            qname = str(query.q.qname)
            qtype = query.q.qtype
            qtype_str = QTYPE[qtype]
            tx_id = query.header.id
            
            cache_result = self.cache.get(qname, qtype)
            
            if isinstance(cache_result, dict):
                # Valid cache hit
                status = 'HIT'
                now = time.time()
                time_remaining = cache_result['absolute_expiry'] - now
                
                # Check for soft TTL prefetch
                if now >= cache_result['soft_ttl']:
                    # Trigger background prefetch
                    self.prefetch_queue.put((qname, qtype, data))
                
                cached_packet = base64.b64decode(cache_result['packet'])
                response_record = DNSRecord.parse(cached_packet)
                # Patch Transaction ID to match current query!
                response_record.header.id = tx_id
                
                response_packet = response_record.pack()
                self.socket.sendto(response_packet, addr)
                
                t_finish = time.perf_counter()
                latency_ms = (t_finish - t_start) * 1000
                print(f"{qname: <25} | [{status: <7}] | TTL: {time_remaining:05.1f}s | Latency: {latency_ms:.2f} ms")
                
            else:
                status = cache_result # 'MISS' or 'EXPIRED'
                
                # Fetch entirely new
                response_data = self.fetch_upstream(data)
                
                if response_data:
                    response_record = self.process_upstream_response(response_data, qname, qtype)
                    # Use original packet but match TX_ID
                    response_record.header.id = tx_id
                    response_packet = response_record.pack()
                else:
                    # Serve SERVFAIL
                    response_record = query.reply()
                    response_record.header.rcode = getattr(RCODE, 'SERVFAIL', 2)
                    response_packet = response_record.pack()
            
                self.socket.sendto(response_packet, addr)
                t_finish = time.perf_counter()
                latency_ms = (t_finish - t_start) * 1000
                
                print(f"{qname: <25} | [{status: <7}] | Fetched/Refetched | Latency: {latency_ms:.2f} ms")

        except Exception as e:
            print(f"[ERROR] Request handling failed: {e}")


    def run(self):
        print(f"[*] Mini DNS Resolver running on {self.host}:{self.port}")
        while self.running:
            try:
                data, addr = self.socket.recvfrom(4096)
                threading.Thread(target=self.handle_request, args=(data, addr)).start()
            except Exception as e:
                if self.running:
                    print(f"[ERROR] recvfrom: {e}")

    def shutdown(self, signum, frame):
        print("\n[*] Shutting down Gracefully...")
        self.running = False
        self.cache.save_cache()
        sys.exit(0)


if __name__ == '__main__':
    resolver = MiniDNSResolver()
    signal.signal(signal.SIGINT, resolver.shutdown)
    signal.signal(signal.SIGTERM, resolver.shutdown)
    resolver.run()
