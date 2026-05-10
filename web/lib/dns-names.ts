/** Canonical FQDN: lowercase labels, trailing dot (matches Python policy style). */

export function normalizeFqdn(input: string): string {
  const trimmed = input.trim().toLowerCase().replace(/\.$/, "");
  if (!trimmed) return ".";
  const labels = trimmed.split(".").filter(Boolean);
  if (labels.length === 0) return ".";
  return `${labels.join(".")}.`;
}

function labelsOf(fqdn: string): string[] {
  const n = fqdn.replace(/\.$/, "");
  if (!n) return [];
  return n.split(".").filter(Boolean);
}

/** True if q is exactly suffix or a subdomain of suffix (both canonical FQDNs). */
export function isUnderOrEqual(q: string, suffix: string): boolean {
  const ql = labelsOf(q);
  const sl = labelsOf(suffix);
  if (sl.length === 0) return true;
  if (ql.length < sl.length) return false;
  for (let i = 0; i < sl.length; i++) {
    if (ql[ql.length - sl.length + i] !== sl[i]) return false;
  }
  return true;
}
