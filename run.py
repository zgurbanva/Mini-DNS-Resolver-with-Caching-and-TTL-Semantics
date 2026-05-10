#!/usr/bin/env python3
"""Interactive launcher — the single entry point for beginners.

    python run.py

Pick a number from the menu; the script builds the correct CLI invocation,
picks a free port, and prints the dig commands you should paste into a
second terminal.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

console = Console()

DEFAULT_PORT = 55353
MAX_PORT_ATTEMPTS = 5

# ISC dig defaults to +time=5 (seconds per try).  Our server uses --timeout 5s
# for upstream DoT/DoH/UDP; a failed upstream often returns SERVFAIL at ~5001–5010 ms.
# If dig stops waiting at 5000 ms, you get "connection timed out" even though the
# stub would have answered SERVFAIL milliseconds later — looks like "no server".
DIG_CLIENT_FLAGS = "+tries=1 +retry=0 +time=8"


# ── helpers ──────────────────────────────────────────────────────────

def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _find_free_port(start: int = DEFAULT_PORT) -> int:
    for offset in range(MAX_PORT_ATTEMPTS):
        candidate = start + offset
        if _port_is_free(candidate):
            return candidate
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _print_dig_hint(port: int, extra: str = "") -> None:
    f = DIG_CLIENT_FLAGS
    lines = [
        f"dig @127.0.0.1 -p {port} example.com A {f}",
        f"dig @127.0.0.1 -p {port} cloudflare.com AAAA {f}",
    ]
    if extra:
        lines.append(extra)
    body = "\n".join(lines)
    note = (
        "\n\n[dim]These commands include +time=8 so `dig` waits longer than the server's "
        "default 5s upstream timeout. Without that, slow upstream failures can look like "
        "`connection timed out` even though the resolver is running.[/dim]"
    )
    console.print()
    console.print(Panel(
        body + note,
        title="[bold]Paste these in a second terminal[/bold]",
        border_style="cyan",
        expand=False,
    ))
    console.print()


def _ensure_venv_deps(requirements_file: str) -> bool:
    """Prompt to install extra deps; return True if ready."""
    try:
        __import__("fastapi")
        __import__("uvicorn")
        return True
    except ImportError:
        pass
    ans = Prompt.ask(
        f"[yellow]Dashboard needs FastAPI + uvicorn.  Install from {requirements_file}?[/yellow]",
        choices=["y", "n"],
        default="y",
    )
    if ans != "y":
        console.print("[dim]Skipped.[/dim]")
        return False
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", requirements_file])
    return True


def _run_server(extra_args: list[str], *, port: int | None = None) -> None:
    """Start server.py (root wrapper → src.server) with the given extra args. Never returns (exec)."""
    if port is None:
        port = _find_free_port()
    cmd = [sys.executable, "server.py", "--port", str(port)] + extra_args
    console.print(f"[bold green]Starting:[/bold green] {' '.join(cmd)}")
    _print_dig_hint(port)
    os.execvp(sys.executable, cmd)


# ── menu actions ─────────────────────────────────────────────────────

def action_basic() -> None:
    port = _find_free_port()
    _run_server(["--upstream", "1.1.1.1"], port=port)


def action_dot() -> None:
    port = _find_free_port()
    console.print(
        "[dim]DoT uses outbound TCP port 853. If every query takes ~5s then fails with "
        "[ERROR] / SERVFAIL, your network may block 853 — try menu [1] (UDP).[/dim]\n"
    )
    _run_server([
        "--upstream", "1.1.1.1",
        "--upstream-protocol", "dot",
    ], port=port)


def action_doh() -> None:
    port = _find_free_port()
    console.print(
        "[dim]DoH sends HTTPS POST requests to the DoH endpoint. "
        "If queries fail instantly with [ERROR], run: "
        "[bold]pip install h2[/bold] — the h2 HTTP/2 library is required. "
        "If queries take ~5s then return SERVFAIL, your network may block "
        "HTTPS to known DNS-resolver IPs — try a hostname URL like "
        "https://cloudflare-dns.com/dns-query or switch to menu [1] (UDP).[/dim]\n"
    )
    _run_server([
        "--upstream-protocol", "doh",
        "--doh-url", "https://1.1.1.1/dns-query",
    ], port=port)


def action_blocklist() -> None:
    port = _find_free_port()
    blocklist = os.path.join(os.path.dirname(__file__) or ".", "blocklist.txt")
    if not os.path.exists(blocklist):
        console.print("[red]blocklist.txt not found beside run.py[/red]")
        return
    console.print(f"[dim]Using blocklist: {blocklist}[/dim]")
    _run_server([
        "--upstream", "1.1.1.1",
        "--blocklist", blocklist,
    ], port=port)


def action_demo() -> None:
    console.print("[bold]Running demo (cold / warm / TTL / TC tests) …[/bold]\n")
    subprocess.call([sys.executable, "demo.py"])


def action_demo_offline() -> None:
    console.print("[bold]Running offline demo (TC fallback only, no internet) …[/bold]\n")
    subprocess.call([sys.executable, "demo.py", "--offline"])


def action_benchmark() -> None:
    """Self-contained benchmark: start server, run benchmark, print results, kill server."""
    port = _find_free_port()
    console.print(f"[bold]Benchmark:[/bold] starting server on port {port} …")

    server_proc = subprocess.Popen(
        [sys.executable, "server.py", "--port", str(port), "--upstream", "1.1.1.1"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    time.sleep(0.8)

    if server_proc.poll() is not None:
        console.print("[red]Server failed to start.[/red]")
        return

    try:
        console.print("[dim]Running warm + cold passes …[/dim]\n")
        subprocess.call([
            sys.executable, "benchmark.py",
            "--host", "127.0.0.1",
            "--port", str(port),
            "--pid", str(server_proc.pid),
        ])
    finally:
        try:
            server_proc.send_signal(signal.SIGTERM)
            server_proc.wait(timeout=3)
        except Exception:
            server_proc.kill()
    console.print("\n[bold green]Done.[/bold green]")


def action_tests() -> None:
    console.print("[bold]Running pytest …[/bold]\n")
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", "-q"]))


def action_dashboard() -> None:
    if not _ensure_venv_deps("requirements.txt"):
        return
    port = _find_free_port()
    dash_port = 8080
    console.print(f"[bold cyan]Dashboard:[/bold cyan] http://127.0.0.1:{dash_port}/")
    _run_server([
        "--upstream", "1.1.1.1",
        "--dashboard", f"127.0.0.1:{dash_port}",
    ], port=port)


# ── main menu ────────────────────────────────────────────────────────

MENU = """\
[bold]=== Mini DNS Resolver ===[/bold]

What would you like to do?

 [cyan][1][/cyan] Start the resolver (basic, UDP upstream)
 [cyan][2][/cyan] Start the resolver (DNS-over-TLS upstream)
 [cyan][3][/cyan] Start the resolver (DNS-over-HTTPS upstream)
 [cyan][4][/cyan] Start the resolver with blocklist enabled
 [cyan][5][/cyan] Run the automated demo (cold/warm/TTL/TC tests)
 [cyan][6][/cyan] Run the automated demo (offline, no internet needed)
 [cyan][7][/cyan] Run the benchmark (latency stats)
 [cyan][8][/cyan] Run tests (pytest)
 [cyan][9][/cyan] Start the resolver with web dashboard
 [cyan][0][/cyan] Exit
"""

ACTIONS = {
    "1": action_basic,
    "2": action_dot,
    "3": action_doh,
    "4": action_blocklist,
    "5": action_demo,
    "6": action_demo_offline,
    "7": action_benchmark,
    "8": action_tests,
    "9": action_dashboard,
}


def main() -> None:
    console.print(MENU)
    choice = Prompt.ask("Enter your choice", choices=[*ACTIONS, "0"], default="1")
    if choice == "0":
        console.print("[dim]Bye![/dim]")
        return
    ACTIONS[choice]()


if __name__ == "__main__":
    main()
