"""Offline mechanical evaluation against an explicitly selected T06 snapshot.

Historical filename retained. No corpus construction, activation or LLM calls.
Cases must declare expected_gate and expected_flags; legacy cases are not inferred.
"""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.pipeline import analyze_clause
from lex_domus.rag_pipeline import load_policy
from lex_domus.snapshots import load_active_snapshot


def validate_cases(cases):
    if not isinstance(cases, list) or not cases:
        raise ValueError('A nonempty evaluation set is required')
    seen = set()
    for case in cases:
        if not isinstance(case, dict) or set(case) != {'id', 'jurisdiction', 'clause', 'expected_gate', 'expected_flags'}:
            raise ValueError('Explicit case contract required')
        if not isinstance(case['id'], str) or not case['id'].strip() or case['id'] in seen:
            raise ValueError('Case identifiers must be unique and nonempty')
        seen.add(case['id'])
        if case['jurisdiction'] != 'ES' or case['expected_gate'] not in ('OK', 'NO_EVIDENCE'):
            raise ValueError('Only ES and explicit gate expectations are supported')
        clause = case['clause']
        if not isinstance(clause, str) or not clause.strip() or len(clause) > 5000:
            raise ValueError('Invalid clause')
        clause.encode('utf-8')
        flags = case['expected_flags']
        if not isinstance(flags, list) or any(not isinstance(f, str) or not f.strip() for f in flags):
            raise ValueError('Expected flags must be an explicit string list')
        if len(flags) != len(set(flags)):
            raise ValueError('Duplicate expected flags')


def evaluate(cases):
    if os.getenv("USE_LLM", "0") != "0":
        raise ValueError("Offline evaluation requires USE_LLM=0")
    validate_cases(cases)
    context = load_active_snapshot(load_policy()).context()
    rows = []
    scores = {key: [] for key in ('T', 'J', 'P')}
    for case in cases:
        result = analyze_clause(case['clause'], case['jurisdiction'])
        if result.get('retrieval_context') != context:
            raise ValueError('Evaluation mixed snapshot versions')
        gate = result.get('gate', {}).get('status')
        if gate not in ('OK', 'NO_EVIDENCE'):
            raise ValueError('Invalid result gate')
        citations = sum(len(node['retrieval']['citations']) for node in result['per_node'])
        if (gate == 'OK') != (citations > 0):
            raise ValueError('Gate and citations disagree')
        flags = result.get('flags')
        if not isinstance(flags, list) or any(not isinstance(f, str) for f in flags):
            raise ValueError('Invalid flags')
        eee = result.get('EEE')
        if gate == 'NO_EVIDENCE':
            if (eee is not None or result.get('engine') != 'NOT_RUN' or result.get('opinion')
                    or result.get('alternative_clause')):
                raise ValueError('Abstention must not contain generated advice or scores')
        else:
            if result.get('engine') != 'MOCK':
                raise ValueError('Offline evaluation requires MOCK results')
            if not isinstance(eee, dict):
                raise ValueError('Missing EEE for evidence-bearing result')
            for key in scores:
                value = eee.get(key)
                if type(value) not in (int, float) or not math.isfinite(value):
                    raise ValueError('Invalid EEE value')
                scores[key].append(value)
        gate_pass = gate == case['expected_gate']
        flags_pass = set(flags) == set(case['expected_flags'])
        rows.append({'id': case['id'], 'jurisdiction': 'ES', 'expected_gate': case['expected_gate'],
                     'gate_status': gate, 'gate_pass': gate_pass, 'flags_pass': flags_pass,
                     'passed': gate_pass and flags_pass, 'expected_flags': case['expected_flags'],
                     'flags_found': flags, 'citations_total': citations, 'engine': result['engine'],
                     **{'EEE_' + k: eee[k] if eee is not None else None for k in scores}})
    # Recheck before writing any report, including changes after the final analysis.
    if load_active_snapshot(load_policy()).context() != context:
        raise ValueError('Snapshot changed during evaluation')
    total = len(rows)
    summary = {'cases': total, 'passed': sum(r['passed'] for r in rows),
               'pass_rate': sum(r['passed'] for r in rows) / total,
               'pass_rate_flags': sum(r['flags_pass'] for r in rows) / total,
               'pass_rate_gate': sum(r['gate_pass'] for r in rows) / total,
               'correct_abstentions': sum(r['expected_gate'] == 'NO_EVIDENCE' and r['gate_pass'] for r in rows),
               'unexpected_retrievals': sum(r['expected_gate'] == 'NO_EVIDENCE' and not r['gate_pass'] for r in rows),
               'missed_evidence': sum(r['expected_gate'] == 'OK' and not r['gate_pass'] for r in rows),
               'EEE_scored_cases': len(scores['T']),
               'EEE_mean': {k: statistics.mean(v) if v else None for k, v in scores.items()}}
    return {'scope': 'Offline mechanical evaluation; not legal validation', 'mode': 'MOCK',
            'retrieval_context': context, 'summary': summary, 'rows': rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True, help='New report directory')
    args = parser.parse_args(argv)
    previous_mode = os.environ.get('USE_LLM')
    try:
        if args.output_dir.exists():
            raise ValueError('Output destination exists')
        raw = args.cases.read_bytes()
        cases = [json.loads(line) for line in raw.decode('utf-8').splitlines() if line.strip()]
        os.environ['USE_LLM'] = '0'
        report = evaluate(cases)
        report['cases_sha256'] = hashlib.sha256(raw).hexdigest()
        args.output_dir.mkdir(parents=True, exist_ok=False)
        (args.output_dir / 'llm_eval_details.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        with (args.output_dir / 'llm_eval_results.csv').open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(report['rows'][0]))
            writer.writeheader()
            writer.writerows(report['rows'])
        passed = report['summary']['passed'] == report['summary']['cases']
        print('Mechanical evaluation: ' + ('PASS' if passed else 'FAIL') + '; not legal validation')
        return 0 if passed else 1
    except Exception:
        # No raw clauses, paths, provider messages or exception details in CI output.
        print('Evaluation BLOCKED: check case contract, policy, selected snapshot and destination.', file=sys.stderr)
        return 2
    finally:
        if previous_mode is None:
            os.environ.pop('USE_LLM', None)
        else:
            os.environ['USE_LLM'] = previous_mode


if __name__ == '__main__':
    raise SystemExit(main())
