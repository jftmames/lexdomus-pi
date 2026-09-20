"""Offline lexical diagnostic on unapproved DOM-derived articles, not API validation."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lex_domus.chunking import split_text
from lex_domus.snapshots import tokenize

EVIDENCE = ROOT / 'docs/T04-evidence'
# Provisional passage references fixed before ranking. No professional approval.
CASES = [
    ('C01', 'La cesión no indica tiempo ni ámbito territorial.', [('43', '2. La falta de mención')]),
    ('C02', 'No acordamos hasta cuándo ni en qué países podrá usarse la obra.', [('43', '2. La falta de mención')]),
    ('C03', 'Se ceden también todos los medios de difusión que se inventen.', [('43', '5. La transmisión')]),
    ('C04', 'Cedemos los derechos mediante un acuerdo verbal.', [('45', 'Toda cesión')]),
    ('C05', 'La cesión se concede con carácter exclusivo.', [('48', 'La cesión en exclusiva')]),
    ('C06', 'Solo esta editorial podrá explotar la obra.', [('48', 'La cesión en exclusiva')]),
    ('C07', 'El autor renuncia a que figure su nombre.', [('14', 'Corresponden al autor'), ('14', '2.º Determinar'), ('14', '3.º Exigir')]),
    ('C08', 'El contrato de edición omite el número de ejemplares.', [('60', '3.º El número'), ('61', '1. Será nulo')]),
    ('C09', 'Valora la cesión y además una patente estadounidense.', None),
    ('C10', '¿Qué tratamiento fiscal tiene este pago?', None),
    ('C11', 'Aplica esta redacción a un contrato de 1997.', None),
    ('C12', 'Texto ajeno al supuesto con palabras comunes: la obra del puente.', None),
]


def build_report():
    raw = (EVIDENCE / 'boe-articles-review.json').read_bytes()
    articles = json.loads(raw)['articles']
    by_id = {a['article']: a for a in articles}
    chunks = []
    for article in articles:
        if article['repealed_marker']:
            continue
        for piece in split_text(article['text']):
            chunks.append({'article': article['article'], **piece})
    rows = []
    for case_id, query, expected in CASES:
        tokens = tokenize(query)
        ranked = sorted([(len(tokens & tokenize(c['text'])), i, c) for i, c in enumerate(chunks)],
                        key=lambda x: (-x[0], x[1]))
        top = [(score, c) for score, _, c in ranked if score > 0][:6]
        passages = []
        for article_id, prefix in expected or []:
            text = by_id[article_id]['text']
            matches = [p for p in text.split('\n\n')[1:] if p.startswith(prefix)]
            if len(matches) != 1:
                raise ValueError('Ambiguous or missing expected passage')
            passage = matches[0]
            start = text.index(passage)
            end = start + len(passage)
            intervals = sorted((c['char_start'], c['char_end']) for _, c in top if c['article'] == article_id)
            covered_until = start
            for lo, hi in intervals:
                if lo <= covered_until:
                    covered_until = max(covered_until, hi)
            passages.append({'article': article_id, 'prefix': prefix, 'char_start': start,
                             'char_end': end, 'fully_covered': covered_until >= end})
        rows.append({'id': case_id, 'query': query,
                     'kind': 'provisional_passage_reference' if expected else 'scope_or_abstention_probe',
                     'expected_passages': passages,
                     'all_passages_covered': all(p['fully_covered'] for p in passages) if expected else None,
                     'top': [{'article': c['article'], 'score': score,
                              'shared_tokens': sorted(tokens & tokenize(c['text'])),
                              'char_start': c['char_start'], 'char_end': c['char_end']} for score, c in top]})
    positive = [r for r in rows if r['expected_passages']]
    return {'purpose': 'offline_review_diagnostic', 'approved': False, 'activated': False,
            'input_sha256': hashlib.sha256(raw).hexdigest(),
            'method': {'ranking': 'lexical-overlap-v1 score and stable input-order tie break',
                       'top_k': 6, 'max_chars': 1000, 'overlap_chars': 120,
                       'unit': 'independent article windows', 'excluded_repealed_articles': ['54'],
                       'passage_hit': 'full expected paragraph coverage by union of retrieved windows',
                       'production_pipeline_executed': False,
                       'limitations': 'No policy approval, snapshot, Inquiry, legal sufficiency gate or generation. Article order is the DOM order, not necessarily future ingestion order. Expectations are provisional.'},
            'summary': {'articles': len(articles), 'searchable_articles': len(articles)-1,
                        'chunks': len(chunks), 'cases': len(rows), 'provisional_reference_cases': len(positive),
                        'fully_covered_reference_cases': sum(r['all_passages_covered'] for r in positive),
                        'uncovered_reference_cases': [r['id'] for r in positive if not r['all_passages_covered']],
                        'scope_probes_returning_candidates': [r['id'] for r in rows if not r['expected_passages'] and r['top']]},
            'cases': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    report = build_report()
    output = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    target = EVIDENCE / 'boe-retrieval-review.json'
    if args.check:
        if target.read_text() != output:
            raise SystemExit('Recorded diagnostic differs from current inputs/code')
    else:
        target.write_text(output, encoding='utf-8')
    print(json.dumps(report['summary'], ensure_ascii=False))


if __name__ == '__main__':
    main()
