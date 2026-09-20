"""CI export must follow a successful, offline evaluation and preserve destinations."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tests import evaluation_smoke


class EvaluationExportTests(unittest.TestCase):
    def test_success_exports_identified_synthetic_report(self):
        with tempfile.TemporaryDirectory() as root:
            out = Path(root) / 'export'
            self.assertEqual(evaluation_smoke.main(['--output-dir', str(out)]), 0)
            self.assertEqual({p.name for p in out.iterdir()},
                             {'README.txt', 'llm_eval_details.json', 'llm_eval_results.csv'})
            report = json.loads((out / 'llm_eval_details.json').read_text())
            self.assertTrue(report['synthetic_only'])
            self.assertFalse(report['activated'])
            self.assertEqual(report['external_calls'], 0)
            self.assertEqual(report['summary']['passed'], 2)
            self.assertEqual(report['summary']['correct_abstentions'], 1)

    def test_failure_and_blocked_evaluation_export_nothing(self):
        with tempfile.TemporaryDirectory() as root:
            for code in (1, 2):
                out = Path(root) / str(code)
                with patch('tests.evaluation_smoke.llm_eval.main', return_value=code):
                    self.assertEqual(evaluation_smoke.main(['--output-dir', str(out)]), code)
                self.assertFalse(out.exists())

    def test_existing_destination_is_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            sentinel = Path(root) / 'keep.txt'
            sentinel.write_text('keep')
            with self.assertRaises(SystemExit):
                evaluation_smoke.main(['--output-dir', root])
            self.assertEqual(sentinel.read_text(), 'keep')
            self.assertEqual(list(Path(root).iterdir()), [sentinel])
