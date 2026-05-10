import { isUnderOrEqual, normalizeFqdn } from "./dns-names";

function parseNameLines(lines: string[]): string[] {
  const out: string[] = [];
  for (const raw of lines) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    out.push(normalizeFqdn(line));
  }
  return out;
}

export class PolicyEngine {
  private readonly _block: string[];
  private readonly _allow: string[];

  constructor(blocklist: string[], allowlist: string[]) {
    this._block = [...blocklist].sort((a, b) => labelsLen(b) - labelsLen(a));
    this._allow = [...allowlist].sort((a, b) => labelsLen(b) - labelsLen(a));
  }

  static empty(): PolicyEngine {
    return new PolicyEngine([], []);
  }

  static fromLines(blockLines: string[], allowLines: string[]): PolicyEngine {
    return new PolicyEngine(parseNameLines(blockLines), parseNameLines(allowLines));
  }

  isBlocked(qname: string): boolean {
    const n = normalizeFqdn(qname);

    if (this._allow.length > 0) {
      if (!this._allow.some((a) => isUnderOrEqual(n, a))) return true;
    }

    return this._block.some((b) => isUnderOrEqual(n, b));
  }
}

function labelsLen(fqdn: string): number {
  return fqdn.replace(/\.$/, "").split(".").filter(Boolean).length;
}
