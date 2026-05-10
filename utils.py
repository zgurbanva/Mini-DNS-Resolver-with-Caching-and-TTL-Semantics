"""Rich-backed logging with consistent request tags and latency (milliseconds)."""

from __future__ import annotations

import time

from rich.console import Console
from rich.text import Text

console = Console(stderr=True)

TAG_HIT = "[CACHE_HIT]"
TAG_MISS = "[CACHE_MISS]"
TAG_TCP = "[TCP_FALLBACK]"
TAG_ERROR = "[ERROR]"


def elapsed_ms(t0: float) -> float:
    return (time.perf_counter() - t0) * 1000.0


def _base_line(
    tag: str,
    latency_ms: float | None,
    *,
    upstream: str | None = None,
    qname: str | None = None,
    qtype: str | None = None,
) -> Text:
    parts: list[tuple[str, str]] = []
    if tag == TAG_HIT:
        parts.append(("[bold green]", TAG_HIT))
    elif tag == TAG_MISS:
        parts.append(("[bold yellow]", TAG_MISS))
    elif tag == TAG_TCP:
        parts.append(("[bold magenta]", TAG_TCP))
    else:
        parts.append(("[bold red]", TAG_ERROR))

    if latency_ms is not None:
        parts.append(("white", f" {latency_ms:.2f}ms"))
    if upstream:
        parts.append(("cyan", f" upstream={upstream}"))
    if qname:
        parts.append(("white", f" qname={qname}"))
    if qtype:
        parts.append(("white", f" qtype={qtype}"))

    t = Text()
    for style, chunk in parts:
        t.append(chunk, style=style)
    return t


def log_cache_hit(
    *,
    latency_ms: float,
    upstream: str | None = None,
    qname: str | None = None,
    qtype: str | None = None,
    extra: str | None = None,
) -> None:
    line = _base_line(TAG_HIT, latency_ms, upstream=upstream, qname=qname, qtype=qtype)
    if extra:
        line.append(f" {extra}")
    console.print(line)


def log_cache_miss(
    *,
    latency_ms: float,
    upstream: str | None = None,
    qname: str | None = None,
    qtype: str | None = None,
    extra: str | None = None,
) -> None:
    line = _base_line(TAG_MISS, latency_ms, upstream=upstream, qname=qname, qtype=qtype)
    if extra:
        line.append(f" {extra}")
    console.print(line)


def log_tcp_fallback(
    *,
    latency_ms: float | None = None,
    upstream: str | None = None,
    qname: str | None = None,
    qtype: str | None = None,
    extra: str | None = None,
) -> None:
    line = _base_line(TAG_TCP, latency_ms, upstream=upstream, qname=qname, qtype=qtype)
    if extra:
        line.append(f" {extra}")
    console.print(line)


def log_error(
    message: str,
    *,
    latency_ms: float | None = None,
    upstream: str | None = None,
    qname: str | None = None,
    qtype: str | None = None,
    exc: BaseException | None = None,
) -> None:
    line = _base_line(TAG_ERROR, latency_ms, upstream=upstream, qname=qname, qtype=qtype)
    line.append(f" {message}")
    if exc is not None:
        line.append(f" ({type(exc).__name__}: {exc})")
    console.print(line)
