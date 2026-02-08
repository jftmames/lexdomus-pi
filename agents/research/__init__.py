# agents/research — Research Plane agents (RAG vivo)
from agents.research.source_watcher import SourceWatcherAgent
from agents.research.ingest_normalizer import IngestNormalizerAgent
from agents.research.ontology_tagger import OntologyTaggerAgent
from agents.research.citation_resolver import CitationResolverAgent
from agents.research.indexer import IndexerAgent

__all__ = [
    "SourceWatcherAgent",
    "IngestNormalizerAgent",
    "OntologyTaggerAgent",
    "CitationResolverAgent",
    "IndexerAgent",
]
