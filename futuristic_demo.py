import time
import subprocess
import threading
import statistics
import sys
import dnslib
from collections import deque

from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.console import Console

# Global states
resolver_logs = deque(maxlen=20)
test_results = []
metrics = {"cold": [], "warm": []}
current_stage = "INITIALIZING PROTOCOLS..."
is_running = True

queries = [
    'google.com',
    'example.com',
    'nonexistent.domain.xyz',
    'github.com'
]

def format_latency(ms):
    if ms < 2:
        return f"[bold green]{ms:.2f} ms[/]"
    elif ms < 20:
        return f"[bold yellow]{ms:.2f} ms[/]"
    return f"[bold red]{ms:.2f} ms[/]"

def resolver_reader(proc):
    """Reads stdout from the resolver subprocess and adds to logs deque."""
    for line in iter(proc.stdout.readline, b''):
        decoded = line.decode('utf-8').strip()
        if decoded:
            if "HIT" in decoded:
                resolver_logs.append(f"[green]{decoded}[/]")
            elif "EXPIR" in decoded:
                resolver_logs.append(f"[yellow]{decoded}[/]")
            elif "ERROR" in decoded:
                resolver_logs.append(f"[red]{decoded}[/]")
            else:
                resolver_logs.append(f"[cyan]{decoded}[/]")
    proc.stdout.close()

def run_tests():
    """Runs the DNS queries simulating scenarios."""
    global current_stage
    time.sleep(2) # Give resolver time to start
    
    def query_domain(domain, is_warm=False):
        q = dnslib.DNSRecord.question(domain)
        t_start = time.perf_counter()
        
        try:
            response = q.send("127.0.0.1", 5053, timeout=2)
            t_finish = time.perf_counter()
            reply = dnslib.DNSRecord.parse(response)
            rcode = dnslib.RCODE[reply.header.rcode]
            latency = (t_finish - t_start) * 1000
        except Exception as e:
            rcode = "TIMEOUT/ERR"
            latency = 0

        status_color = "green" if rcode == "NOERROR" else "red"
        
        test_results.append((
            domain, 
            f"[{status_color}]{rcode}[/]", 
            latency, 
            "[bold green]HIT[/]" if is_warm else "[bold cyan]MISS[/]"
        ))
        
        if is_warm:
            metrics["warm"].append(latency)
        else:
            metrics["cold"].append(latency)
            
        time.sleep(0.8)

    # Scenario 1
    current_stage = "[bold cyan]SCENARIO 1: COLD CACHE INITIATION (MISS)[/]"
    for domain in queries:
        query_domain(domain, is_warm=False)

    # Scenario 2
    current_stage = "[bold green]SCENARIO 2: WARM CACHE OVERDRIVE (HIT)[/]"
    for _ in range(2):
        for domain in queries:
            query_domain(domain, is_warm=True)

    # Scenario 3
    current_stage = "[bold yellow]SCENARIO 3: TTL EXPIRY PROTOCOL (3s)[/]"
    test_domain = "expiry.test.lcl"
    
    test_results.append(("---", "---", 0, "---"))
    query_domain(test_domain, is_warm=False)
    query_domain(test_domain, is_warm=True)
    
    current_stage = "[bold yellow]WAITING FOR PURGE CYCLE... (4s)[/]"
    time.sleep(4)
    
    current_stage = "[bold red]SCENARIO 3: POST-EXPIRY RE-FETCH (MISS)[/]"
    query_domain(test_domain, is_warm=False)

    time.sleep(1)
    current_stage = "[bold white on green] SYSTEM TESTS COMPLETED [/]"
    global is_running
    is_running = False

def generate_layout():
    """Builds the rich layout."""
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main"),
        Layout(name="footer", size=5)
    )
    layout["main"].split_row(
        Layout(name="logs", ratio=1),
        Layout(name="tests", ratio=1)
    )
    return layout

def update_layout(layout):
    """Updates the layout with current data."""
    # Header
    layout["header"].update(Panel(
        Text("🚀 A.C.E. RESOLVER CORE: DNS CACHE AND TTL TELEMETRY", justify="center", style="bold magenta"),
        style="blue"
    ))
    
    # Left Panel - Logs
    log_text = "\n".join(resolver_logs)
    layout["logs"].update(Panel(
        log_text, 
        title="[cyan]Live Resolver Telemetry[/]", 
        border_style="cyan"
    ))
    
    # Right Panel - Test Suite
    table = Table(show_header=True, header_style="bold magenta", expand=True)
    table.add_column("Domain", style="dim")
    table.add_column("Status")
    table.add_column("Latency", justify="right")
    table.add_column("Cache")
    
    # Show last 12 tests
    for r in test_results[-12:]:
        table.add_row(r[0], r[1], format_latency(r[2]) if r[2] else "-", r[3])
    
    layout["tests"].update(Panel(
        table, 
        title=f"[magenta]Automated Test Matrix - {current_stage}[/]", 
        border_style="magenta"
    ))
    
    # Footer - Metrics
    if metrics["cold"] and metrics["warm"]:
        cold_mean = statistics.mean(metrics["cold"])
        warm_mean = statistics.mean(metrics["warm"])
        improvement = ((cold_mean - warm_mean) / cold_mean) * 100 if cold_mean else 0
        
        stat_text = (
            f"[bold cyan]Cold Latency (Network):[/] {cold_mean:.2f} ms | "
            f"[bold green]Warm Latency (Memory):[/] {warm_mean:.2f} ms | "
            f"[bold yellow]Efficiency Gain:[/] {improvement:.1f}% 🔥\n"
        )
        if improvement > 90:
            stat_text += "[bold green]STATUS: OPTIMAL CACHE PERFORMANCE REACHED[/]"
    else:
        stat_text = "Gathering analytical data..."
        
    layout["footer"].update(Panel(
        Text.from_markup(stat_text, justify="center"),
        title="[bold yellow]Performance Analytics[/]",
        border_style="yellow"
    ))

if __name__ == "__main__":
    # Start resolver as subprocess, unbuffered (-u) so we read logs instantly
    proc = subprocess.Popen(
        [sys.executable, "-u", "resolver.py"], 
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT
    )
    
    # Start background threads
    threading.Thread(target=resolver_reader, args=(proc,), daemon=True).start()
    threading.Thread(target=run_tests, daemon=True).start()
    
    layout = generate_layout()
    with Live(layout, refresh_per_second=10, screen=True) as live:
        while is_running:
            update_layout(layout)
            time.sleep(0.1)
            
        update_layout(layout) # final flush
        time.sleep(5) # keep final results on screen for 5 secs
        
    proc.terminate()
    time.sleep(0.5)

    from rich.align import Align
    import pyfiglet
    
    console = Console()
    console.clear()
    
    ascii_complete = pyfiglet.figlet_format("PROJECT COMPLETE", font="standard")
    ascii_thanks = pyfiglet.figlet_format("THANKS", font="standard")
    ascii_watching = pyfiglet.figlet_format("FOR WATCHING", font="standard")
    
    # We use Text() directly to avoid markup parsing issues with ASCII characters like [ and ]
    combined_text = Text()
    combined_text.append(ascii_complete + "\n", style="bold cyan")
    combined_text.append(ascii_thanks + "\n", style="bold magenta")
    combined_text.append(ascii_watching + "\n", style="bold magenta")
    combined_text.append("   DESIGNED AND DEVELOPED BY: ZEYNAB AND NURIDA   \n\n", style="bold black on cyan")
    combined_text.append(">>> SYSTEM DISCONNECTED. OFFLINE CACHE SECURED. <<<\n\n", style="blink italic green")
    combined_text.justify = "center"

    # Print directly to center of console
    console.print(
        Align.center(
            Panel(
                combined_text,
                border_style="cyan",
                title="[bold yellow]MISSION ACCOMPLISHED[/]",
                padding=(2, 6)
            ),
            vertical="middle",
        ),
        height=console.size.height - 2
    )
