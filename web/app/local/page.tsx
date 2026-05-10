export const metadata = { title: "Run locally — Mini DNS companion" };

export default function LocalPage() {
  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-white">Run the full resolver locally</h1>
      <p className="max-w-2xl text-zinc-400">
        Clone the repository, then from the <strong className="text-zinc-200">repository root</strong> (folder that contains{" "}
        <code className="rounded bg-zinc-800 px-1">run.py</code> and <code className="rounded bg-zinc-800 px-1">src/</code>
        ):
      </p>
      <pre className="overflow-x-auto rounded-xl border border-zinc-800 bg-black/60 p-4 font-mono text-sm text-zinc-300">
        {`python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python run.py                # interactive menu
# or:
python server.py --port 55353 --upstream 1.1.1.1
# equivalent:
python -m src.server --port 55353 --upstream 1.1.1.1`}
      </pre>
      <p className="text-sm text-zinc-500">
        Do <strong className="text-zinc-300">not</strong> run <code className="rounded bg-zinc-800 px-1">python src/server.py</code> — use{" "}
        <code className="rounded bg-zinc-800 px-1">python server.py</code> or <code className="rounded bg-zinc-800 px-1">python -m src.server</code>.
      </p>
      <h2 className="text-lg font-semibold text-white">Docker</h2>
      <pre className="overflow-x-auto rounded-xl border border-zinc-800 bg-black/60 p-4 font-mono text-sm text-zinc-300">
        docker compose up --build
      </pre>
      <p className="text-sm text-zinc-500">
        Map host port <code className="rounded bg-zinc-800 px-1">55353</code> to the container (see <code className="rounded bg-zinc-800 px-1">compose.yml</code>
        ).
      </p>
    </div>
  );
}
