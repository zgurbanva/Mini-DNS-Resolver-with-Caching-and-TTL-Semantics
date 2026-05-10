const MAX_DOMAIN_LEN = 253;
const MAX_LABEL = 63;

export function validateDomain(name: string): { ok: true; name: string } | { ok: false; error: string } {
  const trimmed = name.trim();
  if (!trimmed) return { ok: false, error: "Domain is required." };
  if (trimmed.length > MAX_DOMAIN_LEN) {
    return { ok: false, error: `Domain too long (max ${MAX_DOMAIN_LEN} characters).` };
  }
  if (trimmed.includes("..")) return { ok: false, error: "Invalid domain (consecutive dots)." };
  const withoutTrailing = trimmed.replace(/\.$/, "");
  const labels = withoutTrailing.split(".");
  for (const label of labels) {
    if (!label) return { ok: false, error: "Invalid domain (empty label)." };
    if (label.length > MAX_LABEL) return { ok: false, error: `Label too long (max ${MAX_LABEL}).` };
    if (label.startsWith("-") || label.endsWith("-")) {
      return { ok: false, error: "Invalid domain (label cannot start/end with hyphen)." };
    }
    if (!/^[a-z0-9-]+$/i.test(label)) {
      return { ok: false, error: "Invalid domain (allowed: letters, digits, hyphen per label)." };
    }
  }
  return { ok: true, name: trimmed };
}

export function validateDohUrl(url: string): { ok: true; url: string } | { ok: false; error: string } {
  try {
    const u = new URL(url);
    if (u.protocol !== "https:") return { ok: false, error: "DoH URL must use https." };
    if (!u.hostname) return { ok: false, error: "DoH URL must have a hostname." };
    return { ok: true, url: u.toString() };
  } catch {
    return { ok: false, error: "Invalid DoH URL." };
  }
}
