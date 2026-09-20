"""Extract review-only articles from the recorded BOE DOM, never active corpus."""
import hashlib
import json
from pathlib import Path
import re
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'docs/T04-evidence'


def extract(capture):
    if capture['capture_kind'] != 'browser_dom_selected_blocks_not_http_original':
        raise ValueError('Expected explicitly labelled DOM capture')
    expected = {'14', *(str(i) for i in range(17, 24)),
                *(str(i) for i in range(43, 74)), '48 bis'}
    articles = []
    for block in capture['blocks']:
        soup = BeautifulSoup(block['html'], 'html.parser')
        container = soup.find('div', class_='bloque')
        heading = container.find('h5', class_='articulo', recursive=False)
        title = heading.get_text(' ', strip=True)
        match = re.match(r'^Artículo (\d+(?: bis)?)\.', title)
        if not match or match[1] not in expected:
            raise ValueError('Unexpected or duplicate article')
        expected.remove(match[1])
        paragraphs = []
        for element in container.find_all(recursive=False):
            classes = set(element.get('class', []))
            if element.name == 'p' and classes & {'parrafo', 'parrafo_2'}:
                paragraphs.append(element.get_text(' ', strip=True))
            elif element.name == 'p' and not classes & {'bloque', 'pie_unico'}:
                raise ValueError('Unclassified direct paragraph: ' + str(classes))
            elif element.name not in {'p', 'h5', 'blockquote', 'form'}:
                raise ValueError('Unclassified article element: ' + element.name)
        if not paragraphs or any(not p for p in paragraphs):
            raise ValueError('Empty article')
        text = title + '\n\n' + '\n\n'.join(paragraphs)
        articles.append({
            'article': match[1], 'title': title, 'text': text,
            'state': 'unreviewed', 'repealed_marker': paragraphs == ['(Derogado)'],
            'url': capture['url'] + '#' + block['anchor'],
            'capture_block_sha256': hashlib.sha256(block['html'].encode()).hexdigest(),
            'extracted_text_sha256': hashlib.sha256(text.encode()).hexdigest(),
            'notes': [p.get_text(' ', strip=True) for p in container.select('blockquote, p.pie_unico')],
            'note_links': [{'text': a.get_text(' ', strip=True), 'href': a['href']}
                           for a in container.select('blockquote a[href]')],
        })
    if expected:
        raise ValueError('Missing articles: ' + ', '.join(sorted(expected)))
    return articles


def main():
    raw = (EVIDENCE / 'boe-dom-capture.json').read_bytes()
    capture = json.loads(raw)
    articles = extract(capture)
    document = {
        'purpose': 'offline_extraction_review_only', 'activated': False,
        'review_status': 'pending', 'original_http_sha256': None,
        'capture_sha256': hashlib.sha256(raw).hexdigest(),
        'source': 'Agencia Estatal Boletín Oficial del Estado',
        'source_url': capture['url'], 'consolidation_date': capture['consolidation_date'],
        'notice': 'Texto consolidado de carácter meramente informativo. Extracción de una captura DOM; no copia del archivo HTTP original.',
        'transformation': 'Selección de artículos; título y párrafos directos separados por líneas en blanco; notas conservadas por separado.',
        'articles': articles,
    }
    (EVIDENCE / 'boe-articles-review.json').write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    report = ['# Artículos para revisión — LPI', '', document['notice'], '',
              'Basado en datos de la [Agencia Estatal Boletín Oficial del Estado](https://www.boe.es).',
              '', 'Redacción: 30/03/2022. Revisión pendiente. No incorporado al servicio.', '']
    for article in articles:
        report.extend(['## ' + article['title'], '', '[Fuente](' + article['url'] + ')', '',
                       article['text'].split('\n\n', 1)[1], ''])
        if article['notes']:
            report.extend(['Notas del BOE (separadas del texto):', '', *article['notes'], ''])
    (EVIDENCE / 'boe-articles-review.md').write_text('\n'.join(report), encoding='utf-8')
    print(f'{len(articles)} artículos extraídos; {sum(a["repealed_marker"] for a in articles)} marcador de derogación; no activados.')


if __name__ == '__main__':
    main()
