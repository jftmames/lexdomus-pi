"use client";
import React, { useState } from "react";
import ResultView from "../components/ResultView";

const API = process.env.NEXT_PUBLIC_API_BASE || (typeof window !== "undefined" && window.location.hostname !== "localhost" ? "https://lexdomus-pi.onrender.com" : "http://localhost:8000");

export default function Page() {
  const [clause, setClause] = useState("");
  const [juris, setJuris] = useState<"ES"|"EU"|"US"|"INT">("ES");
  const [loading, setLoading] = useState(false);
  const [res, setRes] = useState<any>(null);
  const [error, setError] = useState<string|null>(null);

  async function analyze() {
    setLoading(true); setError(null);
    try {
      const r = await fetch(`${API}/analyze`, {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({ clause, jurisdiction: juris })
      });
      if (!r.ok) throw new Error(await r.text());
      const j = await r.json();
      setRes(j);
    } catch (e:any) {
      setError(e.message || "Error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen p-6 md:p-10 space-y-8">
      <header className="max-w-5xl mx-auto">
        <h1 className="text-3xl md:text-4xl font-semibold">LexDomus–PI · Demo</h1>
        <p className="text-muted mt-2">RAGA+MCP · evidencia con pinpoint · razonamiento 1–5</p>
      </header>

      <section className="max-w-5xl mx-auto card p-6 rounded-2xl space-y-4">
        <label className="text-sm text-muted">Pega aquí la cláusula</label>
        <textarea value={clause} onChange={e=>setClause(e.target.value)}
          className="w-full h-40 rounded-xl bg-black/20 p-3 outline-none border border-white/10"
          placeholder="El Autor renuncia a todos sus derechos morales..." />
        <div className="flex items-center gap-3">
          <select value={juris} onChange={e=>setJuris(e.target.value as any)} className="bg-black/20 border border-white/10 rounded px-3 py-2">
            <option value="ES">ES</option><option value="EU">EU</option><option value="US">US</option><option value="INT">INT</option>
          </select>
          <button onClick={analyze} disabled={loading || !clause.trim()}
            className="rounded-xl px-4 py-2 bg-emerald-500/20 border border-emerald-400/30 hover:bg-emerald-500/30">
            {loading ? "Analizando..." : "Analizar"}
          </button>
          {error && <span className="text-rose-300 text-sm">{error}</span>}
        </div>
      </section>

      <section className="max-w-5xl mx-auto">
        <ResultView data={res} />
      </section>
    </main>
  );
}
