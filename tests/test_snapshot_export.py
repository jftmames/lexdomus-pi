"""Synthetic CI artifact must be identified, reproducible and never overwrite output."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tests.ingestion_smoke import main


class SnapshotExportTests(unittest.TestCase):
    def test_export_contains_only_verified_fictional_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            out = Path(root) / 'artifact'
            main(['--output-dir', str(out)])
            evidence = json.loads((out / 'evidence.json').read_text())
            descriptor = json.loads((out / 'snapshot/snapshot.json').read_text())
            self.assertTrue(evidence['synthetic_only'])
            self.assertFalse(evidence['activated'])
            self.assertEqual(evidence['snapshot_id'], descriptor['snapshot_id'])
            self.assertEqual(evidence['checks']['external_calls'], 0)
            for name, digest in evidence['files_sha256'].items():
                self.assertEqual(hashlib.sha256((out / name).read_bytes()).hexdigest(), digest)
            self.assertEqual(set(out.iterdir()), {out / name for name in
                             ('snapshot', 'originals', 'policies', 'evidence.json', 'README.txt')})

    def test_existing_destination_is_unchanged(self):
        with tempfile.TemporaryDirectory() as root:
            sentinel = Path(root) / 'sentinel'
            sentinel.write_text('keep')
            with self.assertRaises(SystemExit):
                main(['--output-dir', root])
            self.assertEqual(sentinel.read_text(), 'keep')
            self.assertEqual(list(Path(root).iterdir()), [sentinel])

    def test_failed_preparation_exports_nothing(self):
        with tempfile.TemporaryDirectory() as root:
            out = Path(root) / 'artifact'
            with patch('tests.ingestion_smoke.build_index.main', return_value=2), self.assertRaises(AssertionError):
                main(['--output-dir', str(out)])
            self.assertFalse(out.exists())
