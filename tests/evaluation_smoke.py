"""CI-only synthetic evaluator harness; never accepts operator cases or sources."""
import argparse
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from unittest.mock import Mock, patch

from scripts import llm_eval
from tests.snapshot_fixtures import create_snapshot_fixture, snapshot_environment

CASES = Path(__file__).parent / 'fixtures/evaluation_synthetic.jsonl'
SOURCE = b'zafiroqwerty\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True, help='New synthetic report destination')
    args = parser.parse_args(argv)
    if args.output_dir.exists():
        parser.error('Output destination must not exist')
    with tempfile.TemporaryDirectory(prefix='lexdomus-evaluation-') as directory, ExitStack() as stack:
        guards = []
        for target in ('socket.socket.connect', 'socket.socket.connect_ex', 'socket.create_connection',
                       'llm.provider.call_llm_json'):
            guard = Mock(side_effect=AssertionError('External calls forbidden'))
            stack.enter_context(patch(target, guard))
            guards.append(guard)
        fixture = create_snapshot_fixture(directory, SOURCE)
        stack.enter_context(patch.dict('os.environ', snapshot_environment(fixture), clear=True))
        stack.enter_context(patch('lex_domus.snapshots.REGISTRY_PATH', fixture['registry_path']))
        stack.enter_context(patch('lex_domus.rag_pipeline.POLICY_PATH', fixture['policy_path']))
        output = Path(directory) / 'report'
        result = llm_eval.main(['--cases', str(CASES), '--output-dir', str(output)])
        for guard in guards:
            guard.assert_not_called()
        if result != 0:
            return result  # Do not export a failed or blocked evaluation.
        report = json.loads((output / 'llm_eval_details.json').read_text())
        if (report['summary']['cases'] != 2 or report['summary']['passed'] != 2
                or report['summary']['correct_abstentions'] != 1
                or report['summary']['EEE_scored_cases'] != 1
                or report['retrieval_context']['snapshot_id'] != fixture['descriptor']['snapshot_id']
                or report['cases_sha256'] != hashlib.sha256(CASES.read_bytes()).hexdigest()):
            raise AssertionError('Synthetic evaluation evidence does not match the fixture')
        report.update(synthetic_only=True, activated=False, external_calls=0,
                      source_sha256=hashlib.sha256(SOURCE).hexdigest())
        (output / 'llm_eval_details.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        (output / 'README.txt').write_text(
            'SYNTHETIC MECHANICAL EVALUATION ONLY. Not legal validation. No model called.\n'
            'Two fixed cases exercise literal retrieval and abstention; not synonym quality.\n'
            'Reproduce: python -m tests.evaluation_smoke --output-dir NEW_DIRECTORY\n', encoding='utf-8')
        shutil.copytree(output, args.output_dir)  # Existing destinations are never replaced.
    print('Synthetic evaluation verified: 2/2 cases, 1 correct abstention; no activation')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
