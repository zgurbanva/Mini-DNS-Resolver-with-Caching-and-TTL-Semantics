import { describe, expect, it } from "vitest";
import { PolicyEngine } from "./policy";

describe("PolicyEngine", () => {
  it("blocks subdomains of block suffix", () => {
    const p = PolicyEngine.fromLines(["evil.example."], []);
    expect(p.isBlocked("a.evil.example.")).toBe(true);
    expect(p.isBlocked("evil.example.")).toBe(true);
    expect(p.isBlocked("other.com.")).toBe(false);
  });

  it("allowlist restricts when non-empty", () => {
    const p = new PolicyEngine([], ["allowed.com."]);
    expect(p.isBlocked("x.allowed.com.")).toBe(false);
    expect(p.isBlocked("other.com.")).toBe(true);
  });
});
