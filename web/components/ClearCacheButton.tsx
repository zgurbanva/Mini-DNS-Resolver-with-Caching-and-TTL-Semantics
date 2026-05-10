"use client";

export function ClearCacheButton() {
  async function clear() {
    await fetch("/api/playground/reset", { method: "POST" });
    alert("Cache cleared (this server instance only).");
  }
  return (
    <button
      type="button"
      onClick={() => void clear()}
      className="rounded border border-zinc-600 px-4 py-2 text-sm text-zinc-200 hover:border-teal-600"
    >
      POST /api/playground/reset
    </button>
  );
}
