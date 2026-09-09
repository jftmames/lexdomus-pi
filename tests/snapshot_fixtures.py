"""Temporary, fictional evidence snapshots; never approval for actual sources."""
from copy import deepcopy
import json
from pathlib import Path


def create_snapshot_fixture(root, content=b"Derechos patrimoniales morales y licencia editorial sintetica.\n",
                            *, max_chars=1000, overlap_chars=120):
    # Local imports keep the fixture reusable by the existing contract tests.
    from lex_domus.ingestion import build_bundle, save_candidate
    from lex_domus.snapshots import prepare_snapshot
    from tests.test_contracts import BOE_POLICY
    from tests.test_ingestion import write_fixture

    fixture = write_fixture(root, content)
    fixture["policy"] = deepcopy(BOE_POLICY)
    chunks, manifest = build_bundle(fixture["registry_path"], fixture["corpus"], fixture["policy"],
                                    max_chars=max_chars, overlap_chars=overlap_chars)
    fixture["candidate"] = save_candidate(Path(root) / "candidates", chunks, manifest)
    fixture["snapshot"] = prepare_snapshot(fixture["candidate"], Path(root) / "snapshots",
                                            fixture["policy"], fixture["registry_path"], corpus_dir=fixture["corpus"])
    fixture["descriptor"] = json.loads((fixture["snapshot"] / "snapshot.json").read_bytes())
    fixture["chunks_bytes"], fixture["manifest_bytes"] = chunks, manifest
    return fixture


def snapshot_environment(fixture):
    return {"LEXDOMUS_SNAPSHOT_DIR": str(fixture["snapshot"]),
            "LEXDOMUS_SNAPSHOT_ID": fixture["descriptor"]["snapshot_id"], "USE_LLM": "0"}
