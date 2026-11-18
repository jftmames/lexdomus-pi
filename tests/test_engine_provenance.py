import sys
import types
import unittest
from unittest.mock import patch

from app.pipeline import analyze_clause
from app.writer_llm import draft_opinion_llm


class EngineProvenanceTests(unittest.TestCase):
    def test_disabled_and_missing_key(self):
        for enabled, expected in [('0', 'disabled'), ('1', 'missing_api_key')]:
            with self.subTest(enabled=enabled), patch.dict('os.environ', {'USE_LLM': enabled, 'OPENAI_API_KEY': ''}):
                result = analyze_clause('El autor conserva sus derechos morales.', 'ES')
                self.assertEqual(result['engine'], 'MOCK')
                self.assertEqual(result['engine_reason'], expected)
                self.assertNotIn('_engine', result['opinion'])

    def test_provider_failure_reports_fallback(self):
        def fail(*args):
            raise RuntimeError('provider unavailable')
        provider = types.SimpleNamespace(call_llm_json=fail)
        with patch.dict('os.environ', {'USE_LLM': '1', 'OPENAI_API_KEY': 'test-placeholder'}), patch.dict(sys.modules, {'llm.provider': provider}):
            result = draft_opinion_llm('Una cláusula', 'ES', [], [])
        self.assertEqual(result['_engine'], 'MOCK')
        self.assertEqual(result['_engine_reason'], 'provider_error')
        self.assertNotIn('provider unavailable', str(result))

    def test_provider_success_reports_llm(self):
        response = {'analysis_md': 'Resultado de prueba', 'pros': [], 'cons': [], 'devils_advocate': {}}
        provider = types.SimpleNamespace(call_llm_json=lambda *args: response.copy())
        with patch.dict('os.environ', {'USE_LLM': '1', 'OPENAI_API_KEY': 'test-placeholder'}), patch.dict(sys.modules, {'llm.provider': provider}):
            result = draft_opinion_llm('Una cláusula', 'ES', [], [])
        self.assertEqual(result['_engine'], 'LLM')
        self.assertEqual(result['_engine_reason'], 'provider_response')
        self.assertEqual(result['analysis_md'], 'Resultado de prueba')


if __name__ == '__main__':
    unittest.main()
