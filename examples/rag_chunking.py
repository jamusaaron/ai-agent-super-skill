#!/usr/bin/env python3
"""Runnable extract of the RAG chunking strategies from SKILL.md (section 4.2).

Self-contained (standard library only). Run directly to see each chunking
strategy applied to a sample document:

    python3 examples/rag_chunking.py
"""

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Document:
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    doc_id: str = field(default="")

    def __post_init__(self):
        if not self.doc_id:
            self.doc_id = hashlib.md5(self.content.encode()).hexdigest()[:12]


@dataclass
class Chunk:
    content: str
    doc_id: str
    chunk_index: int
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] = field(default_factory=list)


class ChunkingStrategy:
    """Base class -- override chunk()."""

    def chunk(self, doc: Document) -> list[Chunk]:
        raise NotImplementedError


class FixedSizeChunker(ChunkingStrategy):
    """Fixed token-count chunks with overlap. Good for general text."""

    def __init__(self, chunk_size: int = 512, overlap: int = 64):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, doc: Document) -> list[Chunk]:
        words = doc.content.split()
        chunks = []
        step = self.chunk_size - self.overlap

        for i in range(0, len(words), step):
            chunk_words = words[i:i + self.chunk_size]
            if not chunk_words:
                break
            chunks.append(Chunk(
                content=" ".join(chunk_words),
                doc_id=doc.doc_id,
                chunk_index=len(chunks),
                metadata=doc.metadata,
            ))
        return chunks


class SentenceChunker(ChunkingStrategy):
    """Sentence-boundary-aware chunking. Better for structured prose."""

    def __init__(self, sentences_per_chunk: int = 5, overlap_sentences: int = 1):
        self.n = sentences_per_chunk
        self.ov = overlap_sentences

    def chunk(self, doc: Document) -> list[Chunk]:
        sentences = re.split(r'(?<=[.!?])\s+', doc.content.strip())
        chunks = []
        step = self.n - self.ov

        for i in range(0, len(sentences), step):
            batch = sentences[i:i + self.n]
            if not batch:
                break
            chunks.append(Chunk(
                content=" ".join(batch),
                doc_id=doc.doc_id,
                chunk_index=len(chunks),
                metadata=doc.metadata,
            ))
        return chunks


class RecursiveChunker(ChunkingStrategy):
    """Hierarchical chunking -- preserves section structure. Best for long docs."""

    SEPARATORS = ["\n\n", "\n", ". ", " "]

    def __init__(self, max_chunk_size: int = 800, min_chunk_size: int = 100):
        self.max_size = max_chunk_size
        self.min_size = min_chunk_size

    def chunk(self, doc: Document) -> list[Chunk]:
        chunks: list[Chunk] = []
        self._split(doc.content, doc.doc_id, doc.metadata, 0, chunks, [])
        return chunks

    def _split(self, text, doc_id, metadata, depth, chunks, idx_counter):
        if len(text.split()) <= self.max_size or depth >= len(self.SEPARATORS):
            idx_counter.append(None)
            chunks.append(Chunk(
                content=text,
                doc_id=doc_id,
                chunk_index=len(chunks),
                metadata=metadata,
            ))
            return

        sep = self.SEPARATORS[depth]
        parts = text.split(sep)
        current = ""

        for part in parts:
            candidate = (current + sep + part).strip() if current else part
            if len(candidate.split()) <= self.max_size:
                current = candidate
            else:
                if current and len(current.split()) >= self.min_size:
                    self._split(current, doc_id, metadata, depth + 1, chunks, idx_counter)
                current = part

        if current:
            self._split(current, doc_id, metadata, depth + 1, chunks, idx_counter)


SAMPLE = (
    "Agents follow an observe, think, act loop. The loop repeats until a final "
    "answer is produced. ReAct interleaves reasoning and actions. Plan-Execute "
    "plans first, then executes each step. Reflexion critiques its own output. "
    "Retrieval augmented generation grounds answers in a document store. "
    "Chunking splits documents so they fit the embedding model context window."
)


def _demo() -> None:
    doc = Document(content=SAMPLE, metadata={"source": "skill-demo"})
    print(f"Document id: {doc.doc_id}  ({len(SAMPLE.split())} words)\n")

    for chunker in (
        FixedSizeChunker(chunk_size=20, overlap=5),
        SentenceChunker(sentences_per_chunk=2, overlap_sentences=1),
        RecursiveChunker(max_chunk_size=15, min_chunk_size=3),
    ):
        chunks = chunker.chunk(doc)
        print(f"{chunker.__class__.__name__}: {len(chunks)} chunk(s)")
        for c in chunks:
            preview = c.content[:60] + ("..." if len(c.content) > 60 else "")
            print(f"  [{c.chunk_index}] {preview}")
        print()


if __name__ == "__main__":
    _demo()
