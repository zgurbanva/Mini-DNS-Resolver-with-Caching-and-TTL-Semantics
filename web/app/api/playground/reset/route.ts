import { NextRequest, NextResponse } from "next/server";
import { clearServerCache } from "@/lib/server-cache";

export const runtime = "nodejs";

/** Clears the in-memory demo cache (same Node isolate only). */
export async function POST(req: NextRequest) {
  const secret = process.env.PLAYGROUND_RESET_SECRET;
  if (secret) {
    const token = req.headers.get("x-playground-token");
    if (token !== secret) {
      return NextResponse.json({ ok: false, error: "Unauthorized" }, { status: 401 });
    }
  }
  clearServerCache();
  return NextResponse.json({ ok: true });
}
