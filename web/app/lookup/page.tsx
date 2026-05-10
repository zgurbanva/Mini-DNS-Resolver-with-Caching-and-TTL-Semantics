import { LookupLab } from "@/components/LookupLab";

export const metadata = {
  title: "Lookup lab — Mini DNS companion",
};

export default function LookupPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Lookup lab</h1>
        <p className="mt-2 max-w-2xl text-zinc-400">
          Enter any public domain. Choose <strong className="text-zinc-200">A</strong> or{" "}
          <strong className="text-zinc-200">AAAA</strong>. Run the same lookup twice with{" "}
          <em>server cache</em> enabled to see a fast second response (similar to a warm cache on the Python resolver).
        </p>
      </div>
      <LookupLab />
    </div>
  );
}
