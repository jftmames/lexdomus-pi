"""Prepare an isolated lexical snapshot; no persisted search indices are active.

The filename is retained for operator discoverability. Legacy invocations that
implicitly overwrite BM25/FAISS now fail; maintenance migration belongs to T13.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lex_domus.policy import PolicyError, read_policy
from lex_domus.snapshots import CorpusError, prepare_snapshot


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=ROOT / "policies/corpus-registry.json")
    parser.add_argument("--policy", type=Path, default=ROOT / "policies/policy.yaml")
    parser.add_argument("--corpus-dir", type=Path, default=ROOT / "data/corpus")
    args = parser.parse_args(argv)
    try:
        destination = prepare_snapshot(args.candidate_dir, args.output_dir, read_policy(args.policy), args.registry,
                                       corpus_dir=args.corpus_dir)
        descriptor = json.loads((destination / "snapshot.json").read_bytes())
        print(f"[snapshot] candidate -> {destination}; snapshot_id={descriptor['snapshot_id']}; not activated")
        return 0
    except (CorpusError, PolicyError):
        print("[snapshot] BLOCKED: review policy, registry and candidate integrity; no activation", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
