"use client";
import { useEffect, useState } from "react";
import axios from "axios";

export default function Home() {
  const [health, setHealth] = useState<any>(null);
  const [ledger, setLedger] = useState<any[]>([]);

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_BASE!;
    axios.get(`${base}/health`).then(r => setHealth(r.data));
    axios.get(`${base}/api/v1/ledger?limit=10`).then(r => setLedger(r.data.items));
  }, []);

  return (
    <main className="p-8 max-w-6xl mx-auto">
      <h1 className="text-3xl font-bold mb-2">GentleΩ Nexus</h1>
      <p className="text-sm text-gray-500 mb-6">Web3 AI & Agent Economy</p>

      <section className="mb-8">
        <h2 className="text-xl font-semibold">System Health</h2>
        <pre className="bg-gray-900 text-green-300 p-3 rounded-md overflow-x-auto">
          {health ? JSON.stringify(health, null, 2) : "Loading..."}
        </pre>
      </section>

      <section>
        <h2 className="text-xl font-semibold">Recent PoE Ledger</h2>
        <div className="mt-2 grid grid-cols-1 gap-2">
          {ledger.map((r:any) => (
            <div key={r.id} className="rounded border border-gray-700 p-3">
              <div className="text-xs">#{r.id} • {r.status} • block {r.block_number ?? "—"}</div>
              <div className="text-xs break-all">tx: {r.tx_hash ?? "—"}</div>
              <div className="text-xs break-all">poe: {r.poe_hash}</div>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}