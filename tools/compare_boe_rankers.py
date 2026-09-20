"""Offline BM25 comparison. No source admission, API calls or model use."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lex_domus.chunking import split_text
from tools.evaluate_boe_review import CASES, build_report as baseline_report

EVIDENCE = ROOT / 'docs/T04-evidence'
# Fixed before the first comparison, with no parameter search. These are new
# author-written probes, not an independent or legally approved test set.
EXTRA_CASES = [
    ('N01', 'No se especifica la lengua en que saldrá el libro.', [('62', '2. La falta de expresión')]),
    ('N02', '¿En qué idioma pueden publicar si no lo pactamos?', [('62', '2. La falta de expresión')]),
    ('N03', 'El editor debe rendir cuentas y liquidar la remuneración cada año.', [('64', '5.º Satisfacer')]),
    ('N04', '¿Cuándo me tienen que informar de ventas y pagar mi parte?', [('64', '5.º Satisfacer')]),
    ('N05', 'Comprar el soporte no transmite derechos de explotación.', [('56', '1. El adquirente')]),
    ('N06', 'He comprado el manuscrito; ¿puedo explotar la obra?', [('56', '1. El adquirente')]),
    ('N07', 'El autor debe corregir las pruebas de la tirada.', [('65', '3.º Corregir')]),
    ('N08', '¿Quién revisa las pruebas antes de imprimir?', [('64', '2.º Someter'), ('65', '3.º Corregir')]),
    ('N09', '¿Qué IVA corresponde a la venta del libro?', None),
    ('N10', '¿Cómo registro una marca para la editorial?', None),
    ('N11', '¿Es válido este contrato bajo el derecho de California?', None),
    ('N12', '¿Qué permiso municipal exige la obra del garaje?', None),
]
K1, B, TOP_K = 1.2, 0.75, 6


def tokens(text):
    return re.findall(r'\w+', text.lower(), re.U)


def rank(texts, query, mode):
    query_terms = sorted(set(tokens(query)))
    counts = [Counter(tokens(t)) for t in texts]
    n = len(counts)
    avg_len = sum(map(lambda c: sum(c.values()), counts)) / n if n else 0
    df = Counter(term for c in counts for term in c)
    scores = []
    for index, counts_doc in enumerate(counts):
        if mode == 'lexical':
            score = len(set(query_terms) & counts_doc.keys())
        elif mode == 'bm25':
            score = 0.0
            length = sum(counts_doc.values())
            for term in query_terms:
                frequency = counts_doc.get(term, 0)
                if frequency:
                    idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
                    score += idf * frequency * (K1 + 1) / (frequency + K1 * (1 - B + B * length / avg_len))
        else:
            raise ValueError('Unknown ranker')
        if score > 0:
            scores.append((score, index))
    return sorted(scores, key=lambda item: (-item[0], item[1]))[:TOP_K]


def covered(chunks, article, start, end):
    cursor = start
    for lo, hi in sorted((c['char_start'], c['char_end']) for c in chunks if c['article'] == article):
        if lo <= cursor:
            cursor = max(cursor, hi)
    return cursor >= end


def build_report():
    raw = (EVIDENCE / 'boe-articles-review.json').read_bytes()
    articles = json.loads(raw)['articles']
    by_id = {a['article']: a for a in articles}
    chunks = [dict(article=a['article'], **p) for a in articles if not a['repealed_marker'] for p in split_text(a['text'])]
    cases = CASES + EXTRA_CASES
    rows = []
    for case_id, query, expected in cases:
        passages = []
        for article, prefix in expected or []:
            text = by_id[article]['text']
            matches = [p for p in text.split('\n\n')[1:] if p.startswith(prefix)]
            if len(matches) != 1:
                raise ValueError('Ambiguous expected passage')
            start = text.index(matches[0])
            passages.append({'article': article, 'start': start, 'end': start + len(matches[0]), 'prefix': prefix})
        result = {}
        for mode in ('lexical', 'bm25'):
            top = rank([c['text'] for c in chunks], query, mode)
            retrieved = [chunks[i] for _, i in top]
            hits = [covered(retrieved, p['article'], p['start'], p['end']) for p in passages]
            result[mode] = {'all_passages_covered': all(hits) if expected else None,
                            'passages_covered': hits,
                            'top': [{'article': chunks[i]['article'], 'char_start': chunks[i]['char_start'],
                                     'char_end': chunks[i]['char_end'], 'score': round(score, 10)} for score, i in top]}
        rows.append({'id': case_id, 'set': 'existing' if case_id.startswith('C') else 'new_probes',
                     'query': query, 'expected_passages': passages, 'results': result})
    # The comparison baseline must match the previous diagnostic, including order.
    prior = baseline_report()
    for before, after in zip(prior['cases'], rows):
        actual = after['results']['lexical']
        assert before['all_passages_covered'] == actual['all_passages_covered']
        assert [(x['article'], x['char_start'], x['char_end']) for x in before['top']] == [(x['article'], x['char_start'], x['char_end']) for x in actual['top']]
    summaries = {}
    for group in ('existing', 'new_probes'):
        selected = [r for r in rows if r['set'] == group]
        positive = [r for r in selected if r['expected_passages']]
        summaries[group] = {'reference_cases': len(positive),
            **{mode: {'fully_covered': sum(r['results'][mode]['all_passages_covered'] for r in positive),
                      'misses': [r['id'] for r in positive if not r['results'][mode]['all_passages_covered']],
                      'scope_probes_with_candidates': [r['id'] for r in selected if not r['expected_passages'] and r['results'][mode]['top']]}
               for mode in ('lexical', 'bm25')},
            'gains': [r['id'] for r in positive if r['results']['bm25']['all_passages_covered'] and not r['results']['lexical']['all_passages_covered']],
            'regressions': [r['id'] for r in positive if r['results']['lexical']['all_passages_covered'] and not r['results']['bm25']['all_passages_covered']]}
    return {'purpose': 'offline_ranker_comparison', 'activated': False, 'legally_approved': False,
            'input_sha256': hashlib.sha256(raw).hexdigest(),
            'case_set_sha256': hashlib.sha256(json.dumps(cases, ensure_ascii=False).encode()).hexdigest(),
            'configuration': {'top_k': TOP_K, 'k1': K1, 'b': B, 'chunks': len(chunks),
                              'tokens': 'Unicode word regex, lowercase, no stopwords, stemming, synonyms or query term repetition',
                              'idf': 'log(1+(N-df+0.5)/(df+0.5))',
                              'tf_factor': 'f*(k1+1)/(f+k1*(1-b+b*dl/avgdl))',
                              'tie_break': 'input index', 'score_threshold': '>0, not a relevance threshold',
                              'parameter_tuning': False, 'reference_url': 'https://lucene.apache.org/core/9_12_1/core/org/apache/lucene/search/similarities/BM25Similarity.html'},
            'limitations': ['DOM-derived sources not admitted; no production pipeline.',
                           'New probes were authored by the same implementer; no independent held-out validation.',
                           'Expected passages are provisional, not complete legal evidence.',
                           'No relevance labels for every candidate: precision and false-positive rates cannot be estimated.',
                           'Candidate return on scope probes does not prove an incorrect API answer.',
                           'Explicit floating-point BM25 experiment, not Lucene engine parity.'],
            'summary': summaries, 'cases': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    report = build_report()
    output = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    target = EVIDENCE / 'boe-ranker-comparison.json'
    if args.check:
        if target.read_text() != output:
            raise SystemExit('Comparison differs from recorded evidence')
    else:
        target.write_text(output, encoding='utf-8')
    print(json.dumps(report['summary'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
