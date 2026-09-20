"""Deployed synthetic boundary: no real input, policy selection, network or LLM."""
import os
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from pilot.main import app, synthetic_snapshot
from lex_domus.policy import PolicyError
from lex_domus.rag_pipeline import load_policy


class PilotTests(unittest.TestCase):
    def test_fixed_examples_are_isolated_even_with_real_environment_selected(self):
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, {"USE_LLM": "1", "OPENAI_API_KEY": "test-only",
                "LEXDOMUS_SNAPSHOT_DIR": "/nonexistent-real-corpus", "LEXDOMUS_SNAPSHOT_ID": "0" * 64}))
            guards = []
            for target in ("socket.socket.connect", "socket.create_connection", "llm.provider.call_llm_json",
                           "metrics_eee.logger.append_log", "app.writer_llm.draft_opinion_llm"):
                guard = Mock(side_effect=AssertionError("Forbidden side effect"))
                stack.enter_context(patch(target, guard))
                guards.append(guard)
            synthetic_snapshot.cache_clear()
            client = TestClient(app)
            found = client.post('/analyze', json={"clause": "zafiroqwerty", "jurisdiction": "ES"})
            self.assertEqual(found.status_code, 200)
            body = found.json()
            self.assertEqual(body['engine'], 'MOCK')
            self.assertEqual(body['gate']['status'], 'OK')
            self.assertIsNone(body['EEE'])
            self.assertIsNone(body['alternative_clause'])
            for node in body['per_node']:
                for citation in node['retrieval']['citations']:
                    self.assertEqual(citation['meta']['source'], 'SYNTHETIC')
            absent = client.post('/analyze', json={"clause": "inexistenteqwerty", "jurisdiction": "ES"}).json()
            self.assertEqual(absent['engine'], 'NOT_RUN')
            self.assertEqual(absent['gate']['status'], 'NO_EVIDENCE')
            self.assertIsNone(absent['opinion'])
            self.assertEqual(body['retrieval_context'], absent['retrieval_context'])
            self.assertEqual(client.get('/health').json()['retrieval_context'], body['retrieval_context'])
            for guard in guards:
                guard.assert_not_called()
            with self.assertRaises(PolicyError):
                load_policy()  # the real policy remains pending

    def test_rejects_free_text_and_unsupported_jurisdiction(self):
        client = TestClient(app)
        for clause, jurisdiction in [('Una cláusula privada', 'ES'), ('zafiroqwerty', 'US'), ('', 'ES')]:
            response = client.post('/analyze', json={'clause': clause, 'jurisdiction': jurisdiction})
            self.assertEqual(response.status_code, 422)
            self.assertNotIn(clause, response.text) if clause else None
