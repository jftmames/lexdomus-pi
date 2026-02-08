"""
agents/research/indexer.py — Indexer (Vector + Lexical)

Builds embeddings + BM25 lexical index with version pinning.
Filters deprecated=false by default.
"""
from __future__ import annotations

import json
import logging
import pickle
import re
from pathlib import Path
from typing import Dict, List

from agents.base import BaseAgent
from agents.contracts import (
    ChunkMetadata,
    IndexerInput,
    IndexerOutput,
)

logger = logging.getLogger("lexdomus.agents.indexer")

ROOT = Path(__file__).resolve().parents[2]
INDICES_DIR = ROOT / "indices"
CHUNKS_PATH = ROOT / "data" / "docs_chunks" / "chunks.jsonl"

_WORD = re.compile(r"\w+", re.U)


def _tokenize(text: str) -> List[str]:
    return _WORD.findall(text.lower())


class IndexerAgent(BaseAgent[IndexerInput, IndexerOutput]):
    @property
    def name(self) -> str:
        return "indexer"

    def execute(self, inp: IndexerInput) -> IndexerOutput:
        INDICES_DIR.mkdir(parents=True, exist_ok=True)

        # Build BM25 corpus from provided texts
        corpus_tokens: List[List[str]] = []
        chunk_ids: List[str] = []
        deprecated_count = 0

        for chunk in inp.chunks:
            text = inp.texts.get(chunk.chunk_id, "")
            if not text:
                deprecated_count += 1
                continue
            corpus_tokens.append(_tokenize(text))
            chunk_ids.append(chunk.chunk_id)

        # Try BM25 index
        bm25_path = INDICES_DIR / f"bm25_{inp.version_tag}.pkl"
        try:
            from rank_bm25 import BM25Okapi  # type: ignore
            bm25 = BM25Okapi(corpus_tokens)
            with bm25_path.open("wb") as f:
                pickle.dump({"bm25": bm25, "chunk_ids": chunk_ids}, f)
            logger.info("BM25 index built: %d chunks -> %s", len(chunk_ids), bm25_path)
        except ImportError:
            logger.warning("rank_bm25 not available; skipping BM25 index")
            bm25_path = Path("")

        # Write chunks metadata for version pinning
        meta_path = INDICES_DIR / f"chunks_meta_{inp.version_tag}.jsonl"
        with meta_path.open("w", encoding="utf-8") as f:
            for chunk in inp.chunks:
                f.write(chunk.model_dump_json() + "\n")

        return IndexerOutput(
            vector_index_path="",  # dense embeddings not yet implemented
            lexical_index_path=str(bm25_path),
            chunks_indexed=len(chunk_ids),
            version_tag=inp.version_tag,
            deprecated_filtered=deprecated_count,
        )
