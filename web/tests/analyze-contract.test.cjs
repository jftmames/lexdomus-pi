const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const ts = require("typescript");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");

// Compile the checked-in TypeScript in memory; no generated files or network.
function loadTs(relativePath, overrides = {}) {
  const filename = path.resolve(__dirname, relativePath);
  const compiled = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
    fileName: filename,
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2018, jsx: ts.JsxEmit.React, esModuleInterop: true },
  }).outputText;
  const exports = {};
  vm.runInNewContext(compiled, {
    exports, URL,
    require: (name) => overrides[name] || require(name),
  }, { filename });
  return exports;
}

const contract = loadTs("../lib/analyze-contract.ts");
const ResultView = loadTs("../components/ResultView.tsx", { "../lib/analyze-contract": contract }).default;
const requestId = "51fdb1c9-9382-4b19-97d4-020ba2fbfca1";
const citation = () => ({ text: "Texto sintético de una fuente de prueba.", meta: {
  doc_id: "synthetic-1", source: "TEST", jurisdiction: "ES", ref_url: "https://example.org/source",
  line_start: null, line_end: null,
} });
const node = (withEvidence) => ({ node: { pregunta: "Pregunta de prueba", alternativa: "HIDDEN_UNGROUNDED_TEMPLATE" },
  retrieval: { status: withEvidence ? "OK" : "NO_EVIDENCE", citations: withEvidence ? [citation()] : [] } });
const draft = () => ({ contract_version: "0.2", request_id: requestId, status: "DRAFT_REVIEW_REQUIRED",
  message: "REMOTE_MESSAGE_MUST_NOT_RENDER", review_required: true, engine: "MOCK", per_node: [node(true)],
  gate: { status: "OK" }, opinion: { analysis_md: "Borrador sintético", pros: [], cons: [] },
  alternative_clause: "Alternativa sintética", EEE: { T: 100, J: 100, P: 100 }, latency_ms: 1.5 });
const insufficient = () => ({ ...draft(), status: "INSUFFICIENT_EVIDENCE", engine: "NOT_RUN", per_node: [node(false)],
  gate: { status: "NO_EVIDENCE" }, opinion: null, alternative_clause: null, EEE: null });

test("5000 Unicode points are accepted; spaces, line breaks and emoji count without truncation", () => {
  assert.equal(contract.clauseLength("A😀\n "), 4);
  assert.equal(contract.clauseIssue("😀".repeat(5000)), null);
  assert.equal(contract.clauseIssue("😀".repeat(5001)), "TOO_LONG");
  assert.equal(contract.clauseIssue(" " + "x".repeat(5000)), "TOO_LONG");
});

test("shared blank predicate and malformed Unicode are rejected", () => {
  for (const value of ["", " \n\t", "\ufeff", "\u0085", "\u001c\u001d\u001e\u001f"]) assert.equal(contract.clauseIssue(value), "EMPTY");
  for (const value of ["\ud800", "x\udfff", "\ud800x\udc00"]) assert.equal(contract.clauseIssue(value), "INVALID_UNICODE");
  assert.equal(contract.clauseIssue(" \ncláusula\n "), null);
});

test("remote environments never select an implicit external API", () => {
  assert.equal(contract.resolveApiBase(undefined, "pilot.example.org"), null);
  assert.equal(contract.resolveApiBase("", "pilot.example.org"), null);
  assert.equal(contract.resolveApiBase(undefined, "localhost"), "http://localhost:8000");
  assert.equal(contract.resolveApiBase(undefined, "127.0.0.1"), "http://localhost:8000");
  assert.equal(contract.resolveApiBase("https://api.example.org/v1/", "pilot.example.org"), "https://api.example.org/v1");
  for (const value of ["javascript:alert(1)", "https://user:pass@example.org", "https://api.example.org/?key=secret", "https://api.example.org/#secret"])
    assert.equal(contract.resolveApiBase(value, "localhost"), null);
});

test("response boundary accepts versioned states, optional null lines and partial evidence", () => {
  assert.ok(contract.parseAnalyzeResult(draft()));
  assert.ok(contract.parseAnalyzeResult(insufficient()));
  const partial = draft(); partial.per_node.push(node(false));
  assert.ok(contract.parseAnalyzeResult(partial));
});

test("legacy, contradictory and malformed responses cannot reach presentation", () => {
  for (const patch of [{ contract_version: "0.1" }, { request_id: "secret stack trace" }, { status: "OK" },
    { review_required: false }, { latency_ms: NaN }, { latency_ms: -1 }, { per_node: [] }, { opinion: "untyped" },
    { engine: "NOT_RUN" }, { gate: { status: "NO_EVIDENCE" } }, { per_node: [node(false)] }])
    assert.equal(contract.parseAnalyzeResult({ ...draft(), ...patch }), null);
  for (const patch of [{ opinion: draft().opinion }, { alternative_clause: "unguarded advice" }, { EEE: {} },
    { engine: "MOCK" }, { per_node: [node(true)] }])
    assert.equal(contract.parseAnalyzeResult({ ...insufficient(), ...patch }), null);
  assert.equal(contract.parseAnalyzeResult({ engine: "MOCK", gate: { status: "OK" } }), null);
  for (const analysis_md of ["", " \n\ufeff", "\u0085\u001c"]) {
    const value = draft(); value.opinion.analysis_md = analysis_md;
    assert.equal(contract.parseAnalyzeResult(value), null);
  }
});

test("unsafe citation URLs and missing provenance are rejected", () => {
  for (const url of ["javascript:alert(1)", "data:text/html,secret", "https://user:pass@example.org", "https://example.org/\nsecret", "not-a-url"]) {
    const value = draft(); value.per_node[0].retrieval.citations[0].meta.ref_url = url;
    assert.equal(contract.parseAnalyzeResult(value), null);
  }
  const value = draft(); delete value.per_node[0].retrieval.citations[0].meta.doc_id;
  assert.equal(contract.parseAnalyzeResult(value), null);
});

test("ingested provenance preserves Unicode offsets and rejects partial or inconsistent coordinates", () => {
  const value = draft();
  const item = value.per_node[0].retrieval.citations[0];
  item.text = "A😀\n ";
  Object.assign(item.meta, { chunk_id: "a".repeat(64), document_version: "synthetic-v1",
    source_sha256: "b".repeat(64), normalized_sha256: "c".repeat(64), char_start: 8, char_end: 12 });
  assert.ok(contract.parseAnalyzeResult(value));
  for (const change of [{ char_end: 13 }, { char_start: -1 }, { char_start: 8.5 },
      { source_sha256: "not-a-hash" }, { normalized_sha256: null }, { document_version: " " }]) {
    const bad = JSON.parse(JSON.stringify(value));
    Object.assign(bad.per_node[0].retrieval.citations[0].meta, change);
    assert.equal(contract.parseAnalyzeResult(bad), null);
  }
});

test("verified retrieval context requires coherent versioned citations and declares no persistent index", () => {
  const value = draft();
  value.retrieval_context = { mode: "lexical-overlap-v1", snapshot_id: "d".repeat(64),
    corpus_id: "e".repeat(64), active_indices: [] };
  const item = value.per_node[0].retrieval.citations[0];
  Object.assign(item.meta, { chunk_id: "a".repeat(64), document_version: "synthetic-v1",
    source_sha256: "b".repeat(64), normalized_sha256: "c".repeat(64),
    char_start: 0, char_end: Array.from(item.text).length });
  assert.ok(contract.parseAnalyzeResult(value));
  assert.ok(contract.parseAnalyzeResult({ ...insufficient(), retrieval_context: value.retrieval_context }));
  for (const patch of [{ mode: "bm25" }, { snapshot_id: "not-a-hash" }, { corpus_id: "E".repeat(64) },
      { active_indices: ["bm25"] }, { active_indices: null }, { extra: "undeclared" }]) {
    assert.equal(contract.parseAnalyzeResult({ ...value, retrieval_context: { ...value.retrieval_context, ...patch } }), null);
  }
  for (const key of Object.keys(value.retrieval_context)) {
    const context = { ...value.retrieval_context }; delete context[key];
    assert.equal(contract.parseAnalyzeResult({ ...value, retrieval_context: context }), null);
  }
  assert.equal(contract.parseAnalyzeResult({ ...draft(), retrieval_context: value.retrieval_context }), null);
  const mixed = { ...value, per_node: [...value.per_node, node(true)] };
  assert.equal(contract.parseAnalyzeResult(mixed), null);
  assert.ok(contract.parseAnalyzeResult(draft()));
  assert.ok(contract.parseAnalyzeResult({ ...draft(), retrieval_context: null }));
  const html = renderToStaticMarkup(React.createElement(ResultView, { data: value }));
  assert.doesNotMatch(html, /lexical-overlap-v1|dddddddd|eeeeeeee|snapshot_id|active_indices/);
});

test("HTTP errors use local copy and a validated request reference, never raw server details", () => {
  for (const [http, status] of [[400, "INVALID_INPUT"], [422, "INVALID_INPUT"], [422, "OUT_OF_SCOPE"], [500, "TECHNICAL_ERROR"], [503, "TECHNICAL_ERROR"]]) {
    const message = contract.apiErrorMessage(http, { contract_version: "0.2", request_id: requestId, status,
      message: "SECRET_CLIENT_CLAUSE", errors: [{ field: "clause", code: "PRIVATE_TRACE" }] });
    assert.doesNotMatch(message, /SECRET_CLIENT_CLAUSE|PRIVATE_TRACE/);
    if (http === 500) assert.match(message, new RegExp(requestId));
    if (http === 503) {
      assert.match(message, /responsable debe revisar/);
      assert.match(message, new RegExp(requestId));
      assert.doesNotMatch(message, /Inténtalo más tarde/);
    }
  }
  assert.doesNotMatch(contract.apiErrorMessage(500, "RAW_PRIVATE_TRACE"), /RAW_PRIVATE_TRACE/);
  assert.doesNotMatch(contract.apiErrorMessage(500, { request_id: "UNTRUSTED" }), /UNTRUSTED/);
});

test("draft rendering labels simulated output and sources without EEE certification or node template", () => {
  const html = renderToStaticMarkup(React.createElement(ResultView, { data: draft() }));
  assert.match(html, /Borrador pendiente de revisión/);
  assert.match(html, /Resultado simulado/);
  assert.match(html, /href="https:\/\/example.org\/source"/);
  assert.match(html, /Alternativa sintética/);
  assert.doesNotMatch(html, /HIDDEN_UNGROUNDED_TEMPLATE|REMOTE_MESSAGE_MUST_NOT_RENDER|EEE|100%|Dictamen/);
});

test("insufficient rendering never shows opinion, alternative or node recommendation, even if passed inconsistent props", () => {
  const value = { ...insufficient(), opinion: draft().opinion, alternative_clause: "DO_NOT_RENDER", EEE: { T: 100 } };
  const html = renderToStaticMarkup(React.createElement(ResultView, { data: value }));
  assert.match(html, /Evidencia insuficiente/);
  assert.doesNotMatch(html, /DO_NOT_RENDER|HIDDEN_UNGROUNDED_TEMPLATE|Borrador sintético|EEE/);
});
