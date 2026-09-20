"""Offline integration against a real verified fictional snapshot."""
from contextlib import ExitStack
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from scripts import llm_eval
from tests.snapshot_fixtures import create_snapshot_fixture, snapshot_environment


def cases():
    return [{'id': 'hit', 'jurisdiction': 'ES', 'clause': 'zafiroqwerty',
             'expected_gate': 'OK', 'expected_flags': []},
            {'id': 'abstain', 'jurisdiction': 'ES', 'clause': 'inexistenteqwerty',
             'expected_gate': 'NO_EVIDENCE', 'expected_flags': []}]


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.fixture = create_snapshot_fixture(self.root, b'zafiroqwerty\n')
        self.stack.enter_context(patch.dict(os.environ, snapshot_environment(self.fixture), clear=True))
        self.stack.enter_context(patch('lex_domus.snapshots.REGISTRY_PATH', self.fixture['registry_path']))
        self.stack.enter_context(patch('lex_domus.rag_pipeline.POLICY_PATH', self.fixture['policy_path']))
        # Fixed-token harness tests retrieval/reporting, not the placeholder Inquiry.
        self.stack.enter_context(patch('verdiktia.inquiry_engine.decompose_clause',
                                       side_effect=lambda text, _jur: [{"pregunta": text}]))
        for target in ('socket.socket.connect', 'socket.socket.connect_ex', 'socket.create_connection',
                       'llm.provider.call_llm_json'):
            guard = Mock(side_effect=AssertionError('No external calls'))
            self.stack.enter_context(patch(target, guard))
            self.addCleanup(guard.assert_not_called)

    def run_cases(self, records, name='report'):
        path = self.root / 'cases.jsonl'
        path.write_text(''.join(json.dumps(r) + '\n' for r in records))
        out = self.root / name
        code = llm_eval.main(['--cases', str(path), '--output-dir', str(out)])
        return code, json.loads((out / 'llm_eval_details.json').read_text()) if out.exists() else None

    def test_hit_and_correct_abstention_exclude_missing_scores(self):
        os.environ['USE_LLM'] = '1'
        code, report = self.run_cases(cases())
        self.assertEqual(code, 0)
        self.assertEqual(os.environ['USE_LLM'], '1')
        self.assertEqual(report['summary']['correct_abstentions'], 1)
        self.assertEqual(report['summary']['EEE_scored_cases'], 1)
        self.assertIsNone(report['rows'][1]['EEE_T'])
        self.assertEqual(report['retrieval_context']['snapshot_id'], self.fixture['descriptor']['snapshot_id'])
        self.assertNotIn('clause', report['rows'][0])

    def test_all_abstentions_have_null_means(self):
        code, report = self.run_cases(cases()[1:])
        self.assertEqual(code, 0)
        self.assertEqual(report['summary']['EEE_mean'], dict(T=None, J=None, P=None))

    def test_false_retrieval_and_missed_evidence_fail(self):
        records = cases()
        records[0]['expected_gate'] = 'NO_EVIDENCE'
        records[1]['expected_gate'] = 'OK'
        code, report = self.run_cases(records)
        self.assertEqual(code, 1)
        self.assertEqual(report['summary']['unexpected_retrievals'], 1)
        self.assertEqual(report['summary']['missed_evidence'], 1)

    def test_flag_mismatch_fails_even_when_gate_matches(self):
        records = cases()
        records[0]['expected_flags'] = ['expected-but-absent']
        code, report = self.run_cases(records)
        self.assertEqual(code, 1)
        self.assertEqual(report['summary']['pass_rate_gate'], 1)

    def test_bad_case_sets_fail_before_analysis(self):
        variants = [[], cases() * 2]
        for key, value in [('jurisdiction', 'EU'), ('expected_gate', 'unknown'), ('expected_flags', None)]:
            variant = cases(); variant[0][key] = value; variants.append(variant)
        legacy = cases(); del legacy[0]['expected_gate']; variants.append(legacy)
        with patch.object(llm_eval, 'analyze_clause') as analyzer:
            for records in variants:
                self.assertEqual(self.run_cases(records), (2, None))
            analyzer.assert_not_called()

    def test_bad_pin_or_pending_policy_blocks_before_analysis(self):
        with patch.object(llm_eval, 'analyze_clause') as analyzer:
            with patch.dict(os.environ, {'LEXDOMUS_SNAPSHOT_ID': '0' * 64}):
                self.assertEqual(self.run_cases(cases()), (2, None))
            pending = deepcopy(self.fixture['policy']); pending['review']['status'] = 'pending'
            self.fixture['policy_path'].write_text(json.dumps(pending))
            self.assertEqual(self.run_cases(cases()), (2, None))
            analyzer.assert_not_called()

    def test_version_change_between_cases_blocks_export(self):
        original = llm_eval.analyze_clause
        def altered(*args):
            result = original(*args)
            result['retrieval_context']['snapshot_id'] = '0' * 64
            return result
        with patch.object(llm_eval, 'analyze_clause', side_effect=altered):
            self.assertEqual(self.run_cases(cases()), (2, None))

    def test_existing_reports_are_preserved(self):
        self.assertEqual(self.run_cases(cases())[0], 0)
        path = self.root / 'report/llm_eval_details.json'
        before = path.read_bytes()
        self.assertEqual(self.run_cases(cases())[0], 2)
        self.assertEqual(path.read_bytes(), before)
