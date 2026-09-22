"use client";
import React, { useEffect, useRef, useState } from "react";
import ResultView from "../components/ResultView";
import {
  AnalyzeResult, apiErrorMessage, clauseIssue, clauseLength,
  MAX_CLAUSE_CHARACTERS, parseAnalyzeResult, resolveApiBase,
} from "../lib/analyze-contract";

export default function Page() {
  const [clause, setClause] = useState("");
  const [loading, setLoading] = useState(false);
  const [res, setRes] = useState<AnalyzeResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [api, setApi] = useState<string | null>(null);
  const sequence = useRef(0);
  const pending = useRef<AbortController | null>(null);

  useEffect(() => {
    setApi(resolveApiBase(process.env.NEXT_PUBLIC_API_BASE, window.location.hostname));
    return () => { sequence.current += 1; pending.current?.abort(); };
  }, []);

  function editClause(value: string) {
    sequence.current += 1;
    pending.current?.abort();
    pending.current = null;
    setLoading(false);
    setRes(null);
    setError(null);
    setClause(value);
  }

  async function analyze(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current || !api || clauseIssue(clause)) return;
    const current = ++sequence.current;
    const controller = new AbortController();
    pending.current = controller;
    setLoading(true);
    setError(null);
    setRes(null);
    try {
      const response = await fetch(`${api}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ clause, jurisdiction: "ES" }),
        signal: controller.signal,
      });
      const payload: unknown = await response.json().catch(() => null);
      if (current !== sequence.current) return;
      if (!response.ok) {
        setError(apiErrorMessage(response.status, payload));
        return;
      }
      const result = parseAnalyzeResult(payload);
      if (!result) {
        setError("El servicio no ha devuelto una respuesta compatible. No se ha mostrado ningún análisis.");
        return;
      }
      setRes(result);
    } catch {
      if (current === sequence.current && !controller.signal.aborted) {
        setError("No se ha podido conectar con el servicio. Inténtalo más tarde.");
      }
    } finally {
      if (current === sequence.current) {
        pending.current = null;
        setLoading(false);
      }
    }
  }

  const issue = clauseIssue(clause);
  const count = clauseLength(clause);
  const validationMessage = issue === "TOO_LONG" ? "Reduce el texto a un máximo de 5.000 caracteres."
    : issue === "INVALID_UNICODE" ? "El texto contiene caracteres dañados. Corrígelo antes de continuar."
    : issue === "EMPTY" && clause.length > 0 ? "Introduce texto; los espacios por sí solos no forman una cláusula." : null;

  return (
    <main className="min-h-screen p-6 md:p-10 space-y-8">
      <header className="max-w-5xl mx-auto">
        <h1 className="text-3xl md:text-4xl font-semibold">LexDomus–PI · Piloto técnico</h1>
        <p className="text-muted mt-2">Revisión asistida de cláusulas editoriales de cesión o licencia bajo jurisdicción española.</p>
        <p className="mt-3">Utiliza sólo textos sintéticos. El piloto aún no está habilitado para expedientes reales.</p>
      </header>

      <form onSubmit={analyze} className="max-w-5xl mx-auto card p-6 rounded-2xl space-y-4" aria-busy={loading}>
        <label htmlFor="clause" className="text-sm text-muted">Cláusula de prueba</label>
        <textarea id="clause" value={clause} onChange={event => editClause(event.target.value)}
          aria-describedby="clause-count clause-validation" aria-invalid={Boolean(validationMessage)}
          className="w-full h-40 rounded-xl bg-black/20 p-3 outline-none border border-white/10"
          placeholder="Escribe una cláusula ficticia de cesión o licencia editorial." />
        <p id="clause-count" className="text-sm text-muted">{count.toLocaleString("es-ES")} / {MAX_CLAUSE_CHARACTERS.toLocaleString("es-ES")} caracteres · Incluye espacios y saltos de línea.</p>
        <p id="clause-validation" className="text-sm text-rose-300" aria-live="polite">{validationMessage}</p>
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm">Jurisdicción: España</span>
          <button type="submit" disabled={loading || issue !== null || !api}
            className="rounded-xl px-4 py-2 bg-emerald-500/20 border border-emerald-400/30 hover:bg-emerald-500/30 disabled:opacity-50">
            {loading ? "Analizando…" : "Analizar cláusula"}
          </button>
        </div>
        {!api && <p role="status" className="text-sm text-amber-300">El servicio de análisis no está disponible en este entorno.</p>}
        {error && <p role="alert" className="text-rose-300 text-sm">{error}</p>}
      </form>

      <section className="max-w-5xl mx-auto" aria-live="polite">
        <ResultView data={res} />
      </section>
    </main>
  );
}
