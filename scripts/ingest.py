"""Build an unpromoted corpus candidate from an explicitly reviewed registry."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lex_domus.ingestion import IngestionError, build_bundle, inspect_registry, save_candidate
from lex_domus.policy import PolicyError, read_policy


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=ROOT / "policies/corpus-registry.json")
    parser.add_argument("--policy", type=Path, default=ROOT / "policies/policy.yaml")
    parser.add_argument("--corpus-dir", type=Path, default=ROOT / "data/corpus")
    parser.add_argument("--output-dir", type=Path,
                        help="Parent of a new candidate directory; never the active chunks file")
    parser.add_argument("--check", action="store_true", help="Inspect registry without producing a corpus")
    args = parser.parse_args(argv)
    try:
        if args.check:
            inventory = inspect_registry(args.registry, args.corpus_dir)
            issues = sum(row["integrity_issue"] is not None for row in inventory["quarantined"])
            print(f"[ingest] registered admitted={len(inventory['admitted'])} "
                  f"quarantined={len(inventory['quarantined'])} integrity_issues={issues}; check only, no publication")
            return 2 if issues else 0
        if args.output_dir is None:
            raise IngestionError("Explicit candidate destination required; legacy promotion is unsupported")
        policy = read_policy(args.policy)
        chunks, manifest = build_bundle(args.registry, args.corpus_dir, policy)
        destination = save_candidate(args.output_dir, chunks, manifest)
        print(f"[ingest] candidate -> {destination}; active corpus unchanged")
        return 0
    except (IngestionError, PolicyError):
        print("[ingest] BLOCKED: review policy, registry and source integrity; no corpus published", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
