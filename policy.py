"""Optional blocklist / allowlist: suffix-based matching on canonical DNS names."""

from __future__ import annotations

from pathlib import Path

import dns.name


def _parse_name_lines(path: Path) -> list[dns.name.Name]:
    names: list[dns.name.Name] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        n = dns.name.from_text(line)
        if not n.is_absolute():
            n = n.concatenate(dns.name.root)
        names.append(n.canonicalize())
    return names


def _is_under_or_equal(q: dns.name.Name, suffix: dns.name.Name) -> bool:
    if q == suffix:
        return True
    return q.is_subdomain(suffix)


class PolicyEngine:
    """
    - If allowlist is non-empty: only names matching at least one allow suffix may proceed.
    - Blocklist: names matching a block suffix return blocked (policy decision by caller).
    """

    def __init__(self, *, blocklist: list[dns.name.Name], allowlist: list[dns.name.Name]) -> None:
        self._block = sorted(blocklist, key=len, reverse=True)
        self._allow = sorted(allowlist, key=len, reverse=True)

    @classmethod
    def from_files(
        cls,
        blocklist_path: str | None,
        allowlist_path: str | None,
    ) -> PolicyEngine:
        blocks: list[dns.name.Name] = []
        allows: list[dns.name.Name] = []
        if blocklist_path:
            blocks = _parse_name_lines(Path(blocklist_path))
        if allowlist_path:
            allows = _parse_name_lines(Path(allowlist_path))
        return cls(blocklist=blocks, allowlist=allows)

    @classmethod
    def empty(cls) -> PolicyEngine:
        return cls(blocklist=[], allowlist=[])

    def is_blocked(self, qname: dns.name.Name) -> bool:
        n = qname
        if not n.is_absolute():
            n = n.concatenate(dns.name.root)
        n = n.canonicalize()

        if self._allow:
            if not any(_is_under_or_equal(n, a) for a in self._allow):
                return True

        return any(_is_under_or_equal(n, b) for b in self._block)
