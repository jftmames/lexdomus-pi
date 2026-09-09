"""Exercise candidate CLI and BM25 construction on temporary synthetic data."""
from contextlib import ExitStack
import json
from pathlib import Path
import pickle
import tempfile
from unittest.mock import Mock, patch

from scripts import ingest, build_index
from tests.test_ingestion import write_fixture


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
        chunks = candidate / "chunks.jsonl"
        records = [json.loads(line) for line in chunks.read_bytes().splitlines()]
        indices = candidate / "indices"
        indices.mkdir()
        stack.enter_context(patch.object(build_index, "CHUNKS", chunks))
        stack.enter_context(patch.object(build_index, "INDICES", indices))
        build_index.build_bm25()  # Never call optional embedding download or FAISS.
        # Only deserialize the object produced by this same test in its own directory.
        with (indices / "bm25.pkl").open("rb") as stream:
            result = pickle.load(stream)
        assert result["metas"] == records
        assert len(result["tokenized"]) == len(records) > 1
        assert result["bm25"].get_scores(["derechos"]).shape == (len(records),)
        for guard in guards:
            guard.assert_not_called()
        print(f"Synthetic candidate and BM25 preserve {len(records)} complete provenance records; active corpus unchanged")


if __name__ == "__main__":
    main()
