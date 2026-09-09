"use client";
import React from "react";
import { AnalyzeResult, safeSourceUrl } from "../lib/analyze-contract";

export default function ResultView({ data }: { data: AnalyzeResult | null }) {
  if (!data) return null;
  const insufficient = data.status === "INSUFFICIENT_EVIDENCE";

  return (
    <div className="space-y-6">
      <div className="card p-6 rounded-2xl border border-amber-400/30">
        <h2 className="text-xl font-semibold">{insufficient ? "Evidencia insuficiente" : "Borrador pendiente de revisión"}</h2>
        <p className="mt-2">{insufficient
          ? "No se ha generado un borrador ni una alternativa contractual. Faltan fuentes para cubrir las preguntas del análisis."
          : "El abogado debe comprobar las fuentes, valorar el caso y decidir sobre el texto antes de utilizarlo."}</p>
        {data.engine === "MOCK" && <p className="mt-2 text-amber-300">Resultado simulado para pruebas técnicas. No contiene un análisis jurídico del modelo.</p>}
        <p className="text-xs text-muted mt-3">Referencia de la solicitud: {data.request_id}</p>
      </div>

      <div className="card p-6 rounded-2xl">
        <h2 className="text-lg mb-3">Fuentes recuperadas para revisión</h2>
        <p className="text-sm text-muted mb-4">La recuperación de una cita no confirma su vigencia, su interpretación ni su aplicación al caso.</p>
        {data.per_node.length === 0 && <p>No hay fuentes recuperadas.</p>}
        <div className="space-y-4">
          {data.per_node.map((item, index) => (
            <div key={index} className="bg-black/20 p-4 rounded-xl">
              <h3 className="font-semibold">{item.node.pregunta}</h3>
              <p className="text-sm text-muted mt-1">{item.retrieval.status === "OK" ? "Citas recuperadas; revisión pendiente." : "Sin evidencia para esta pregunta."}</p>
              {item.retrieval.citations.length > 0 && (
                <ul className="mt-3 space-y-3">
                  {item.retrieval.citations.map((citation, citationIndex) => {
                    const link = safeSourceUrl(citation.meta.ref_url);
                    return (
                      <li key={citationIndex} className="border border-white/10 rounded p-3">
                        <p className="text-sm font-semibold">{citation.meta.title || citation.meta.doc_id}</p>
                        <p className="text-xs text-muted">{citation.meta.source} · {citation.meta.jurisdiction} · {citation.meta.doc_id}</p>
                        {citation.meta.ref_label && <p className="text-xs text-muted mt-1">{citation.meta.ref_label}</p>}
                        <blockquote className="text-sm mt-2 whitespace-pre-wrap">{citation.text}</blockquote>
                        {link && <a href={link} target="_blank" rel="noopener noreferrer" className="inline-block underline text-sm mt-2">Consultar fuente</a>}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          ))}
        </div>
      </div>

      {!insufficient && data.opinion && (
        <>
          <div className="card p-6 rounded-2xl">
            <h2 className="text-lg mb-3">Borrador de análisis</h2>
            <div className="text-sm whitespace-pre-wrap">{data.opinion.analysis_md}</div>
            {(data.opinion.pros.length > 0 || data.opinion.cons.length > 0) && (
              <div className="grid md:grid-cols-2 gap-4 mt-4">
                <div><h3 className="font-semibold mb-2">Argumentos favorables propuestos</h3><ul className="space-y-1 list-disc list-inside">{data.opinion.pros.map((item, index) => <li key={index}>{item}</li>)}</ul></div>
                <div><h3 className="font-semibold mb-2">Objeciones propuestas</h3><ul className="space-y-1 list-disc list-inside">{data.opinion.cons.map((item, index) => <li key={index}>{item}</li>)}</ul></div>
              </div>
            )}
          </div>
          {data.alternative_clause && (
            <div className="card p-6 rounded-2xl">
              <h2 className="text-lg mb-3">Alternativa contractual pendiente de revisión</h2>
              <p className="text-sm whitespace-pre-wrap">{data.alternative_clause}</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
