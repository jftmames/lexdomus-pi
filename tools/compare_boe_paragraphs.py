"""Review-only paragraph-preserving BM25 comparison, never active ingestion."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.compare_boe_rankers import build_report as reference, covered, rank

EVIDENCE = ROOT / 'docs/T04-evidence'


def paragraph_chunks(text, target=1000):
    """Pack whole paragraphs without overlap. Oversized paragraphs stay intact.

    Contiguous offsets preserve all original separators; no text is synthesized.
    """
    if type(target) is not int or target <= 0:
        raise ValueError('Positive integer target required')
    if not text:
        return []
    boundaries = []
    cursor = 0
    for part in text.split('\n\n'):
        cursor += len(part)
        if cursor < len(text):
            cursor += 2
        boundaries.append(cursor)
    chunks = []
    start = end = 0
    for boundary in boundaries:
        if boundary - start > target and end > start:
            chunks.append({'text': text[start:end], 'char_start': start, 'char_end': end})
            start = end
        end = boundary
    if end > start:
        chunks.append({'text': text[start:end], 'char_start': start, 'char_end': end})
    return chunks


def build_report():
    raw = (EVIDENCE / 'boe-articles-review.json').read_bytes()
    articles = json.loads(raw)['articles']
    chunks = [dict(article=a['article'], **p) for a in articles if not a['repealed_marker'] for p in paragraph_chunks(a['text'])]
    previous = reference()
    rows = []
    for case in previous['cases']:
        top = rank([c['text'] for c in chunks], case['query'], 'bm25')
        chosen = [chunks[i] for _, i in top]
        expected = case['expected_passages']
        hits = [covered(chosen, p['article'], p['start'], p['end']) for p in expected]
        before = case['results']['bm25']
        rows.append({'id': case['id'], 'set': case['set'], 'query': case['query'],
                     'expected_passages': expected,
                     'window_covered': before['all_passages_covered'],
                     'paragraph_covered': all(hits) if expected else None,
                     'window_returned_chars': sum(c['char_end']-c['char_start'] for c in before['top']),
                     'paragraph_returned_chars': sum(len(c['text']) for c in chosen),
                     'top': [dict(article=chunks[i]['article'], char_start=chunks[i]['char_start'],
                                  char_end=chunks[i]['char_end'], score=round(score,10)) for score,i in top]})
    positive = [r for r in rows if r['expected_passages']]
    return {'purpose':'offline_paragraph_comparison','activated':False,'approved':False,
            'input_sha256':hashlib.sha256(raw).hexdigest(),
            'method':{'target_chars':1000,'top_k':6,'ranking':'same BM25 formula, k1=1.2, b=0.75',
                      'overlap':0,'oversize_policy':'retain complete paragraph, report size',
                      'limitation':'Different chunks change BM25 collection statistics and candidate count; this is a chunking comparison, not a fixed-index rerank.'},
            'summary':{'chunks':len(chunks),'oversized_chunks':sum(len(c['text'])>1000 for c in chunks),
                       'max_chunk_chars':max(len(c['text']) for c in chunks),
                       'reference_cases':len(positive),
                       'window_hits':sum(r['window_covered'] for r in positive),
                       'paragraph_hits':sum(r['paragraph_covered'] for r in positive),
                       'gains':[r['id'] for r in positive if r['paragraph_covered'] and not r['window_covered']],
                       'regressions':[r['id'] for r in positive if r['window_covered'] and not r['paragraph_covered']],
                       'misses':[r['id'] for r in positive if not r['paragraph_covered']],
                       'mean_window_returned_chars':sum(r['window_returned_chars'] for r in rows)/len(rows),
                       'mean_paragraph_returned_chars':sum(r['paragraph_returned_chars'] for r in rows)/len(rows),
                       'scope_probes_with_candidates':[r['id'] for r in rows if not r['expected_passages'] and r['top']]},
            'cases':rows}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    report=build_report()
    out=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    path=EVIDENCE/'boe-paragraph-comparison.json'
    if args.check:
        if path.read_text()!=out: raise SystemExit('Paragraph evidence changed')
    else: path.write_text(out,encoding='utf-8')
    print(json.dumps(report['summary'],ensure_ascii=False,indent=2))

if __name__=='__main__': main()
