"""No live HTTP: exercise isolation, bounded download and failure cleanup."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from scripts import fetch_corpus as fetch


class DownloadTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name); self.out = self.root / 'candidate'
        self.plan = {'purpose': 'download_for_review', 'sources': [
            {'id': 'synthetic', 'url': 'https://www.boe.es/synthetic-fixture'}]}
        self.response = MagicMock(status_code=200)
        self.response.headers = {'Content-Type': 'text/plain'}
        self.response.iter_content.return_value = [b'fictional source only']
        self.response.__enter__.return_value = self.response
        self.session = MagicMock()
        self.session.__enter__.return_value = self.session
        self.session.get.return_value = self.response
        patcher = patch.object(fetch.requests, 'Session', return_value=self.session)
        patcher.start(); self.addCleanup(patcher.stop)
        blocker = patch('socket.socket.connect', side_effect=AssertionError('Live network forbidden'))
        blocker.start(); self.addCleanup(blocker.stop)

    def run_download(self):
        return fetch.download(json.dumps(self.plan).encode(), self.out)

    def test_isolated_bytes_and_manifest_remain_unreviewed(self):
        manifest = self.run_download()
        raw = (self.out / 'synthetic.body').read_bytes()
        self.assertEqual(manifest['sources'][0]['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(manifest['state'], 'unreviewed')
        self.assertFalse(manifest['activated'])
        self.assertFalse(self.session.trust_env)
        self.assertFalse(self.session.get.call_args.kwargs['allow_redirects'])
        self.assertEqual({p.name for p in self.out.iterdir()},
                         {'synthetic.body', 'download-manifest.json', 'README.txt'})

    def test_existing_destination_untouched_before_network(self):
        self.out.mkdir(); (self.out / 'keep').write_text('keep')
        with self.assertRaises(FileExistsError): self.run_download()
        self.session.get.assert_not_called()
        self.assertEqual((self.out / 'keep').read_text(), 'keep')

    def test_repository_destination_rejected_before_network(self):
        self.out = fetch.ROOT / 'data/corpus/new-candidate'
        with self.assertRaises(ValueError): self.run_download()
        self.session.get.assert_not_called()

    def test_invalid_urls_and_names_block_entire_plan(self):
        for change in ({'url':'http://www.boe.es/a'}, {'url':'https://www.boe.es.evil.invalid/a'},
                       {'url':'https://user:pass@www.boe.es/a'}, {'id':'../escape'},
                       {'url':'https://127.0.0.1/a'}, {'url':'https://www.boe.es:444/a'}):
            self.plan['sources'][0] = {'id':'synthetic','url':'https://www.boe.es/a', **change}
            with self.assertRaises(ValueError): self.run_download()
        self.session.get.assert_not_called()
        self.assertFalse(self.out.exists())

    def test_redirect_http_error_empty_and_oversize_leave_no_candidate(self):
        for status, parts in [(302,[b'x']), (500,[b'x']), (200,[]), (200,[b'12345'])]:
            self.response.status_code = status; self.response.iter_content.return_value = parts
            with patch.object(fetch, 'MAX_BYTES', 4), self.assertRaises(ValueError): self.run_download()
            self.assertFalse(self.out.exists())

    def test_partial_batch_failure_removes_all_downloaded_files(self):
        self.plan['sources'].append({'id':'second','url':'https://www.boe.es/second'})
        self.session.get.side_effect = [self.response, TimeoutError()]
        with self.assertRaises(TimeoutError): self.run_download()
        self.assertFalse(self.out.exists())
