"use client";
import React from "react";

type Citation = {
  text: string;
  meta: { title?: string; source?: string; jurisdiction?: string; ref_label?: string; ref_url?: string; pinpoint?: boolean; line_start?: number; line_end?: number; };
};

type NodeItem = {
  node: any;
  retrieval: { status: "OK" | "NO_EVIDENCE"; citations: Citation[] };
  used_query?: string;
};

type Result = {
  engine: string;
  gate: { status: string };
  per_node: NodeItem[];
  opinion?: { analysis_md?: string; pros?: string[]; cons?: string[]; devils_advocate?: any };
  alternative_clause?: string;
  EEE?: { T?: number; J?: number; P?: number };
  latency_ms?: number;
  reasoning?: any;
};

export default function ResultView({ data }: { data: Result | null }) {
  if (!data) return null;
  const chip = (s: string) => (
    <span className={`px-2 py-0.5 rounded text-xs ${s==="OK" ? "bg-emerald-500/20 text-emerald-300" : "bg-amber-500/20 text-amber-300"}`}>{s}</span>
  );

  return (
    <div className="space-y-6">
      <div className="grid md:grid-cols-3 gap-4">
        <div className="card p-4 rounded-2xl">
          <div className="text-sm text-muted">Engine</div>
          <div className="text-xl">{data.engine}</div>
        </div>
        <div className="card p-4 rounded-2xl">
          <div className="text-sm text-muted">Gate</div>
          <div className="text-xl">{chip(data.gate?.status || "NO_EVIDENCE")}</div>
        </div>
        <div className="card p-4 rounded-2xl">
          <div className="text-sm text-muted">Latencia</div>
          <div className="text-xl">{(data.latency_ms ?? 0).toFixed(0)} ms</div>
        </div>
      </div>

      <div className="card p-6 rounded-2xl">
        <h3 className="text-lg mb-3">Evidencia</h3>
        <div className="space-y-4">
          {data.per_node?.map((it, i) => (
            <div key={i} className="bg-black/20 p-4 rounded-xl">
              <div className="flex items-center justify-between mb-2">
                <div className="font-semibold">Nodo {i+1}</div>
                {chip(it.retrieval?.status)}
              </div>
              <pre className="text-xs text-muted overflow-x-auto">{JSON.stringify(it.node, null, 2)}</pre>
              {it.used_query && (
                <details className="mt-2">
                  <summary className="text-sm text-muted cursor-pointer">Consulta usada</summary>
                  <pre className="text-xs">{it.used_query}</pre>
                </details>
              )}
              {it.retrieval?.citations?.length ? (
                <ul className="mt-2 space-y-2">
                  {it.retrieval.citations.map((c, j) => (
                    <li key={j} className="border border-white/10 rounded p-2">
                      <div className="text-sm">{c.meta?.title} <span className="text-muted">· {c.meta?.source} · {c.meta?.jurisdiction}</span></div>
                      {c.meta?.ref_label && <div className="text-xs text-muted">{c.meta.ref_label} ({c.meta.line_start}–{c.meta.line_end})</div>}
                      <div className="text-xs mt-1">{(c.text || "").slice(0, 300)}{(c.text||"").length>300 ? "…" : ""}</div>
                    </li>
                  ))}
                </ul>
              ) : <div className="text-sm text-muted">Sin citas</div>}
            </div>
          ))}
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="card p-6 rounded-2xl">
          <h3 className="text-lg mb-3">Dictamen</h3>
          <div className="prose prose-invert max-w-none text-sm whitespace-pre-wrap">{data.opinion?.analysis_md || "—"}</div>
        </div>
        <div className="card p-6 rounded-2xl">
          <h3 className="text-lg mb-3">Pros / Contras</h3>
          <div className="grid grid-cols-2 gap-4">
            <ul className="space-y-1 list-disc list-inside text-emerald-300">{(data.opinion?.pros || []).map((p,i)=><li key={i}>{p}</li>)}</ul>
            <ul className="space-y-1 list-disc list-inside text-rose-300">{(data.opinion?.cons || []).map((p,i)=><li key={i}>{p}</li>)}</ul>
          </div>
        </div>
      </div>

      <div className="card p-6 rounded-2xl">
        <h3 className="text-lg mb-3">Modelo doctrinal (1–5)</h3>
        <pre className="text-xs overflow-x-auto">{JSON.stringify(data.reasoning || {}, null, 2)}</pre>
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        <div className="card p-4 rounded-2xl"><div className="text-sm text-muted">EEE.T</div><div className="text-2xl">{data.EEE?.T ?? 0}</div></div>
        <div className="card p-4 rounded-2xl"><div className="text-sm text-muted">EEE.J</div><div className="text-2xl">{data.EEE?.J ?? 0}</div></div>
        <div className="card p-4 rounded-2xl"><div className="text-sm text-muted">EEE.P</div><div className="text-2xl">{data.EEE?.P ?? 0}</div></div>
      </div>
    </div>
  );
}
