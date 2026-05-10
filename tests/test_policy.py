"""Suffix blocklist / allowlist."""

from __future__ import annotations

import dns.name

import policy as policy_mod


def test_blocklist_suffix() -> None:
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("evil.example.\n")
        path = f.name
    try:
        eng = policy_mod.PolicyEngine.from_files(path, None)
        assert eng.is_blocked(dns.name.from_text("a.evil.example."))
        assert not eng.is_blocked(dns.name.from_text("other.com."))
    finally:
        Path(path).unlink(missing_ok=True)


def test_allowlist_restricts() -> None:
    eng = policy_mod.PolicyEngine(
        blocklist=[],
        allowlist=[dns.name.from_text("allowed.com.")],
    )
    assert not eng.is_blocked(dns.name.from_text("x.allowed.com."))
    assert eng.is_blocked(dns.name.from_text("other.com."))
