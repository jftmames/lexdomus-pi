/** Public API boundary. A well-formed response is not a legal validation. */
export const CONTRACT_VERSION = "0.2";
export const MAX_CLAUSE_CHARACTERS = 5000;

export type ClauseIssue = "EMPTY" | "TOO_LONG" | "INVALID_UNICODE";
export type Citation = {
  text: string;
  meta: {
    doc_id: string;
    source: string;
    jurisdiction: string;
    ref_url: string;
    title?: string;
    ref_label?: string;
    pinpoint?: boolean;
    line_start?: number | null;
    line_end?: number | null;
    chunk_id?: string | null;
    document_version?: string | null;
    source_sha256?: string | null;
    normalized_sha256?: string | null;
    char_start?: number | null;
    char_end?: number | null;
  };
};
export type NodeItem = {
  node: { pregunta: string };
  retrieval: { status: "OK" | "NO_EVIDENCE"; citations: Citation[] };
};
export type RetrievalContext = {
  mode: "lexical-overlap-v1";
  snapshot_id: string;
  corpus_id: string;
  active_indices: [];
};
export type AnalyzeResult = {
  contract_version: "0.2";
  request_id: string;
  status: "DRAFT_REVIEW_REQUIRED" | "INSUFFICIENT_EVIDENCE";
  message: string;
  review_required: true;
  engine: "LLM" | "MOCK" | "NOT_RUN";
  per_node: NodeItem[];
  retrieval_context?: RetrievalContext | null;
  gate: { status: "OK" | "NO_EVIDENCE" };
  opinion: { analysis_md: string; pros: string[]; cons: string[] } | null;
  alternative_clause: string | null;
  EEE: Record<string, unknown> | null;
  latency_ms: number;
};

const record = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);
const nonempty = (value: unknown): value is string =>
  typeof value === "string" && !/^[\s\u0085\u001c-\u001f]*$/u.test(value);
const stringList = (value: unknown): value is string[] =>
  Array.isArray(value) && value.every(item => typeof item === "string");
const requestId = (value: unknown): value is string =>
  typeof value === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
const sha256 = (value: unknown): value is string =>
  typeof value === "string" && /^[0-9a-f]{64}$/.test(value);

export function clauseLength(clause: string): number {
  return Array.from(clause).length;
}

export function clauseIssue(clause: string): ClauseIssue | null {
  if (/^[\s\u0085\u001c-\u001f]*$/u.test(clause)) return "EMPTY";
  for (const character of Array.from(clause)) {
    const point = character.codePointAt(0)!;
    if (point >= 0xd800 && point <= 0xdfff) return "INVALID_UNICODE";
  }
  return clauseLength(clause) > MAX_CLAUSE_CHARACTERS ? "TOO_LONG" : null;
}

export function safeSourceUrl(value: unknown): string | null {
  if (typeof value !== "string" || /[\s\u0000-\u001f\u007f]/u.test(value)) return null;
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) && url.hostname && !url.username && !url.password
      ? url.href : null;
  } catch {
    return null;
  }
}

export function resolveApiBase(configured: string | undefined, hostname: string): string | null {
  if (configured) {
    const valid = safeSourceUrl(configured);
    if (!valid) return null;
    const url = new URL(valid);
    if (url.search || url.hash) return null;
    return valid.replace(/\/+$/, "");
  }
  return ["localhost", "127.0.0.1"].includes(hostname) ? "http://localhost:8000" : null;
}

function isCitation(value: unknown): value is Citation {
  if (!record(value) || !nonempty(value.text) || !record(value.meta)) return false;
  const meta = value.meta;
  if (!["doc_id", "source", "jurisdiction", "ref_url"].every(key => nonempty(meta[key])) || !safeSourceUrl(meta.ref_url)) return false;
  if (["title", "ref_label"].some(key => key in meta && typeof meta[key] !== "string")) return false;
  if ("pinpoint" in meta && typeof meta.pinpoint !== "boolean") return false;
  for (const key of ["line_start", "line_end"]) {
    if (key in meta && meta[key] !== null && (typeof meta[key] !== "number" || !Number.isInteger(meta[key]) || (meta[key] as number) < 1)) return false;
  }
  const provenance = ["chunk_id", "document_version", "source_sha256", "normalized_sha256", "char_start", "char_end"];
  if (provenance.some(key => meta[key] != null)) {
    if (!provenance.every(key => meta[key] != null) || !nonempty(meta.document_version)) return false;
    if (!["chunk_id", "source_sha256", "normalized_sha256"].every(key => sha256(meta[key]))) return false;
    if (typeof meta.char_start !== "number" || typeof meta.char_end !== "number"
        || !Number.isSafeInteger(meta.char_start) || !Number.isSafeInteger(meta.char_end)
        || meta.char_start < 0 || meta.char_end - meta.char_start !== Array.from(value.text).length) return false;
  }
  return !(typeof meta.line_start === "number" && typeof meta.line_end === "number" && meta.line_end < meta.line_start);
}

function isNode(value: unknown): value is NodeItem {
  if (!record(value) || !record(value.node) || !nonempty(value.node.pregunta) || !record(value.retrieval)) return false;
  const retrieval = value.retrieval;
  if (!Array.isArray(retrieval.citations) || !retrieval.citations.every(isCitation)) return false;
  return retrieval.status === "OK" ? retrieval.citations.length > 0
    : retrieval.status === "NO_EVIDENCE" && retrieval.citations.length === 0;
}

function isRetrievalContext(value: unknown): value is RetrievalContext {
  return record(value) && Object.keys(value).length === 4
    && value.mode === "lexical-overlap-v1" && sha256(value.snapshot_id) && sha256(value.corpus_id)
    && Array.isArray(value.active_indices) && value.active_indices.length === 0;
}

export function parseAnalyzeResult(value: unknown): AnalyzeResult | null {
  if (!record(value) || value.contract_version !== CONTRACT_VERSION || !requestId(value.request_id)
      || typeof value.message !== "string" || value.review_required !== true
      || typeof value.latency_ms !== "number" || !Number.isFinite(value.latency_ms) || value.latency_ms < 0
      || !Array.isArray(value.per_node) || value.per_node.length === 0 || !value.per_node.every(isNode) || !record(value.gate)) return null;

  if (value.retrieval_context != null) {
    if (!isRetrievalContext(value.retrieval_context)
        || value.per_node.some(item => item.retrieval.citations.some(citation => !sha256(citation.meta.chunk_id)))) return null;
  }

  if (value.status === "INSUFFICIENT_EVIDENCE") {
    if (value.gate.status !== "NO_EVIDENCE" || value.engine !== "NOT_RUN" || value.per_node.every(item => item.retrieval.status === "OK")
        || value.opinion !== null || value.alternative_clause !== null || value.EEE !== null) return null;
  } else if (value.status === "DRAFT_REVIEW_REQUIRED") {
    if (value.gate.status !== "OK" || !["LLM", "MOCK"].includes(String(value.engine))
        || !value.per_node.every(item => item.retrieval.status === "OK")
        || !record(value.opinion) || !nonempty(value.opinion.analysis_md)
        || !stringList(value.opinion.pros) || !stringList(value.opinion.cons)
        || (value.alternative_clause !== null && typeof value.alternative_clause !== "string")
        || (value.EEE !== null && !record(value.EEE))) return null;
  } else return null;

  return value as AnalyzeResult;
}

/** Never display arbitrary server text, exception detail or echoed input. */
export function apiErrorMessage(httpStatus: number, value: unknown): string {
  if (record(value) && value.contract_version === CONTRACT_VERSION && requestId(value.request_id)) {
    if (httpStatus === 503 && value.status === "TECHNICAL_ERROR") return `Análisis no disponible. El responsable debe revisar la configuración del servicio. Referencia: ${value.request_id}.`;
    if (httpStatus === 422 && value.status === "OUT_OF_SCOPE") return "El piloto sólo admite cláusulas bajo jurisdicción española.";
    if ([400, 422].includes(httpStatus) && value.status === "INVALID_INPUT") return "Revisa el texto: debe contener una cláusula válida de hasta 5.000 caracteres.";
    if (httpStatus === 500 && value.status === "TECHNICAL_ERROR") return `No se ha podido completar el análisis. Inténtalo más tarde. Referencia: ${value.request_id}.`;
  }
  return "El servicio no ha devuelto una respuesta compatible. No se ha mostrado ningún análisis.";
}
