"""Exercise ingestion, snapshot CLI and verified retrieval on synthetic data."""
from contextlib import ExitStack
import argparse
from copy import deepcopy
import hashlib
import shutil
import json
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

from scripts import ingest, build_index
from tests.test_ingestion import write_fixture
from tests.test_contracts import BOE_POLICY
from lex_domus.snapshots import CorpusError, load_active_snapshot


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, help="New destination for synthetic evidence only")
    args = parser.parse_args(argv)
    if args.output_dir is not None and args.output_dir.exists():
        parser.error("Output destination must not exist")
    with tempfile.TemporaryDirectory(prefix="lexdomus-ingestion-smoke-") as temporary, ExitStack() as stack:
        guards = []
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                       "llm.provider.call_llm_json"):
            guard = Mock(side_effect=AssertionError("External requests forbidden"))
            stack.enter_context(patch(target, guard))
            guards.append(guard)
        fixture = write_fixture(temporary, ("Derechos editoriales sintéticos. 😀\r\n" * 90).encode("utf-8"))
        outputs = Path(temporary) / "candidates"
        assert ingest.main(["--registry", str(fixture["registry_path"]), "--policy", str(fixture["policy_path"]),
                            "--corpus-dir", str(fixture["corpus"]), "--output-dir", str(outputs)]) == 0
        candidate, = outputs.iterdir()
        snapshots = Path(temporary) / "snapshots"
        assert build_index.main(["--candidate-dir", str(candidate), "--output-dir", str(snapshots),
                                 "--registry", str(fixture["registry_path"]), "--policy", str(fixture["policy_path"]),
                                 "--corpus-dir", str(fixture["corpus"])]) == 0
        snapshot_dir, = snapshots.iterdir()
        descriptor = json.loads((snapshot_dir / "snapshot.json").read_bytes())
        stack.enter_context(patch.dict("os.environ", {"LEXDOMUS_SNAPSHOT_DIR": str(snapshot_dir),
                                                      "LEXDOMUS_SNAPSHOT_ID": descriptor["snapshot_id"]}))
        stack.enter_context(patch("lex_domus.snapshots.REGISTRY_PATH", fixture["registry_path"]))
        result = load_active_snapshot(BOE_POLICY).search("derechos", 6, BOE_POLICY)
        records = [json.loads(line) for line in (candidate / "chunks.jsonl").read_bytes().splitlines()]
        by_id = {record["chunk_id"]: record for record in records}
        assert result and len(records) > 1
        for citation in result:
            record = by_id[citation["meta"]["chunk_id"]]
            assert citation["text"] == record["text"]
            assert all(value == record[key] for key, value in citation["meta"].items())
        # A pending policy must fail before preparing any snapshot directory.
        pending = deepcopy(BOE_POLICY)
        pending["review"]["status"] = "pending"
        pending_path = Path(temporary) / "pending-policy.json"
        pending_path.write_text(json.dumps(pending), encoding="utf-8")
        rejected_output = Path(temporary) / "rejected-snapshots"
        assert build_index.main(["--candidate-dir", str(candidate), "--output-dir", str(rejected_output),
                                 "--registry", str(fixture["registry_path"]), "--policy", str(pending_path),
                                 "--corpus-dir", str(fixture["corpus"])]) == 2
        assert not rejected_output.exists()
        with patch.dict("os.environ", {"LEXDOMUS_SNAPSHOT_ID": "0" * 64}):
            try:
                load_active_snapshot(BOE_POLICY)
            except CorpusError:
                pass
            else:
                raise AssertionError("Wrong snapshot pin was accepted")
        for guard in guards:
            guard.assert_not_called()
        if args.output_dir is not None:
            # Export only after every check succeeds. Never export runner environment or real corpus.
            destination = args.output_dir
            destination.mkdir(parents=True, exist_ok=False)
            shutil.copytree(snapshot_dir, destination / "snapshot")
            shutil.copytree(fixture["corpus"], destination / "originals")
            shutil.copytree(fixture["policy_path"].parent, destination / "policies")
            files = {str(path.relative_to(destination)): hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in sorted(destination.rglob("*")) if path.is_file()}
            evidence = {"synthetic_only": True, "activated": False,
                        "snapshot_id": descriptor["snapshot_id"], "corpus_id": descriptor["corpus_id"],
                        "mode": descriptor["mode"], "files_sha256": files,
                        "checks": {"retrieval_provenance": True, "pending_policy_rejected": True,
                                   "wrong_pin_rejected": True, "external_calls": 0}}
            (destination / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
            (destination / "README.txt").write_text(
                "SYNTHETIC TEST DATA ONLY. Not approved legal sources. Never activate in production.\n"
                "Policy review fields are fictional test fixtures. No deployment configuration is included.\n",
                encoding="utf-8")
        print(f"Synthetic snapshot preserves {len(records)} provenance records; lexical retrieval verified; not activated")


if __name__ == "__main__":
    main()
