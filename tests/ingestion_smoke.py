"""Exercise ingestion, snapshot CLI and verified retrieval on synthetic data."""
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

from scripts import ingest, build_index
from tests.test_ingestion import write_fixture
from tests.test_contracts import BOE_POLICY
from lex_domus.snapshots import load_active_snapshot


def main():
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
        for guard in guards:
            guard.assert_not_called()
        print(f"Synthetic snapshot preserves {len(records)} provenance records; lexical retrieval verified; not activated")


if __name__ == "__main__":
    main()
