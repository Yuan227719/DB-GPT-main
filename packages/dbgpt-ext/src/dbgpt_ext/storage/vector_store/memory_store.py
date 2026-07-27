"""Pure-Python in-process vector store with sqlite persistence.

This store is a drop-in replacement for ``ChromaStore`` that avoids any
native C/C++ dependency (no hnswlib, no chromadb).  It stores document
chunks and their embeddings in a single sqlite database and performs
similarity search with numpy brute force (cosine similarity).  It is the
recommended store on Windows when the chromadb hnswlib native wheel
crashes with ``access violation`` (see ``chroma_store.py`` for the full
background).

The store is intentionally minimal: it supports the subset of the
``VectorStoreBase`` interface that DB-GPT's RAG / db-summary flow
exercises -- ``load_document``, ``similar_search``,
``similar_search_with_scores``, ``vector_name_exists``,
``delete_vector_name``, ``delete_by_ids``, ``truncate`` and
``count``.
"""

import json
import logging
import os
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Union

import numpy as np

from dbgpt.configs.model_config import PILOT_PATH, resolve_root_path
from dbgpt.core import Chunk, Embeddings
from dbgpt.core.awel.flow import Parameter, ResourceCategory, register_resource
from dbgpt.storage.vector_store.base import (
    _COMMON_PARAMETERS,
    _VECTOR_STORE_COMMON_PARAMETERS,
    VectorStoreBase,
    VectorStoreConfig,
)
from dbgpt.storage.vector_store.filters import FilterOperator, MetadataFilters
from dbgpt.util.i18n_utils import _

logger = logging.getLogger(__name__)


@register_resource(
    _("Memory Vector Config"),
    "memory_vector_config",
    category=ResourceCategory.VECTOR_STORE,
    description=_("Pure-Python vector store with sqlite persistence."),
    parameters=[
        *_COMMON_PARAMETERS,
        Parameter.build_from(
            _("Persist Path"),
            "persist_path",
            str,
            description=_("the persist path of vector store."),
            optional=True,
            default=None,
        ),
    ],
)
@dataclass
class MemoryVectorConfig(VectorStoreConfig):
    """Pure-Python vector store config."""

    __type__ = "memory"

    persist_path: Optional[str] = field(
        default=os.getenv("MEMORY_VECTOR_PERSIST_PATH", None),
        metadata={
            "help": _("The persist path of vector store."),
        },
    )

    def create_store(self, **kwargs) -> "MemoryVectorStore":
        """Create index store."""
        return MemoryVectorStore(vector_store_config=self, **kwargs)


@register_resource(
    _("Memory Vector Store"),
    "memory_vector_store",
    category=ResourceCategory.VECTOR_STORE,
    description=_("Pure-Python vector store (numpy brute force + sqlite)."),
    parameters=[
        Parameter.build_from(
            _("Memory Config"),
            "vector_store_config",
            MemoryVectorConfig,
            description=_("the memory config of vector store."),
            optional=True,
            default=None,
        ),
        *_VECTOR_STORE_COMMON_PARAMETERS,
    ],
)
class MemoryVectorStore(VectorStoreBase):
    """Pure-Python vector store backed by sqlite + numpy.

    Vectors are stored as raw float32 blobs in sqlite; similarity search
    loads all vectors for the collection into memory and does a numpy
    cosine-similarity brute-force scan.  This is fine for the few-hundred
    to few-thousand chunk scale that DB-GPT's DB-summary flow produces
    (one collection per database, typically <10k chunks).  For larger
    scale use a real vector database (milvus / qdrant).
    """

    def __init__(
        self,
        vector_store_config: MemoryVectorConfig,
        name: Optional[str],
        embedding_fn: Optional[Embeddings] = None,
        max_chunks_once_load: Optional[int] = None,
        max_threads: Optional[int] = None,
    ) -> None:
        """Create a MemoryVectorStore instance.

        Args:
            vector_store_config(MemoryVectorConfig): vector store config.
            name(str): collection name.
            embedding_fn(Embeddings): embedding function.
            max_chunks_once_load(int): max chunks once load.
            max_threads(int): max threads.
        """
        super().__init__(
            max_chunks_once_load=max_chunks_once_load, max_threads=max_threads
        )
        self._vector_store_config = vector_store_config
        cfg_dict = vector_store_config.to_dict()
        persist_path = cfg_dict.get(
            "persist_path", os.path.join(PILOT_PATH, "data")
        )
        self.persist_dir = os.path.join(resolve_root_path(persist_path) + "/memory_vector")
        os.makedirs(self.persist_dir, exist_ok=True)
        self._db_path = os.path.join(self.persist_dir, "memory_vector.db")
        self._db_lock = threading.RLock()
        self._init_db()
        self.embeddings = embedding_fn
        if not self.embeddings:
            raise ValueError("Embeddings is None")
        self._collection_name = name or "default"
        self._ensure_collection()

    # ------------------------------------------------------------------ #
    # Database helpers
    # ------------------------------------------------------------------ #
    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self) -> None:
        with self._db_lock, self._conn() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS collections (
                    name TEXT PRIMARY KEY,
                    dimension INTEGER,
                    metadata TEXT
                )
                """
            )
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS embeddings (
                    collection_name TEXT NOT NULL,
                    chunk_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    vector BLOB NOT NULL,
                    PRIMARY KEY (collection_name, chunk_id)
                )
                """
            )
            c.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_embeddings_collection
                ON embeddings(collection_name)
                """
            )

    def _ensure_collection(self) -> None:
        with self._db_lock, self._conn() as c:
            row = c.execute(
                "SELECT name FROM collections WHERE name = ?", (self._collection_name,)
            ).fetchone()
            if row is None:
                c.execute(
                    "INSERT INTO collections(name, dimension, metadata) VALUES (?, ?, ?)",
                    (self._collection_name, -1, "{}"),
                )

    # ------------------------------------------------------------------ #
    # VectorStoreBase implementation
    # ------------------------------------------------------------------ #
    def get_config(self) -> MemoryVectorConfig:
        """Get the vector store config."""
        return self._vector_store_config

    def vector_name_exists(self) -> bool:
        """Whether vector name exists."""
        try:
            with self._db_lock, self._conn() as c:
                row = c.execute(
                    "SELECT COUNT(*) FROM embeddings WHERE collection_name = ?",
                    (self._collection_name,),
                ).fetchone()
                return bool(row and row[0] > 0)
        except Exception as e:
            logger.info(f"Collection {self._collection_name} check failed: {e}")
            return False

    def load_document(self, chunks: List[Chunk]) -> List[str]:
        """Load document to vector store."""
        logger.info("MemoryVectorStore load document")
        if not chunks:
            return []
        texts = [chunk.content for chunk in chunks]
        metadatas = [chunk.metadata or {} for chunk in chunks]
        ids = [chunk.chunk_id or str(uuid.uuid4()) for chunk in chunks]
        # Embed all texts in one batch -- remote embedding API supports
        # batches of 10+ comfortably and this keeps HTTP round-trips low.
        vectors = self.embeddings.embed_documents(texts)
        if not vectors:
            raise RuntimeError("Embedding API returned empty result")
        dim = len(vectors[0])
        with self._db_lock, self._conn() as c:
            # Update collection dimension if unset.
            row = c.execute(
                "SELECT dimension FROM collections WHERE name = ?",
                (self._collection_name,),
            ).fetchone()
            if row and (row[0] is None or row[0] < 0):
                c.execute(
                    "UPDATE collections SET dimension = ? WHERE name = ?",
                    (dim, self._collection_name),
                )
            for cid, text, meta, vec in zip(ids, texts, metadatas, vectors):
                arr = np.asarray(vec, dtype=np.float32)
                c.execute(
                    """
                    INSERT OR REPLACE INTO embeddings
                        (collection_name, chunk_id, content, metadata, vector)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        self._collection_name,
                        cid,
                        text,
                        json.dumps(meta, ensure_ascii=False),
                        arr.tobytes(),
                    ),
                )
        return ids

    def similar_search(
        self, text: str, topk: int, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Search similar documents."""
        logger.info("MemoryVectorStore similar search")
        return self._search(text, topk, filters, with_scores=False)

    def similar_search_with_scores(
        self, text: str, topk: int, score_threshold: float, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Search similar documents with scores.

        score_threshold filters by ``1 - cosine_distance`` (i.e. cosine
        similarity).  0 means dissimilar, 1 means identical.
        """
        logger.info("MemoryVectorStore similar search with scores")
        chunks = self._search(text, topk, filters, with_scores=True)
        return self.filter_by_score_threshold(chunks, score_threshold)

    async def afull_text_search(
        self, text: str, topk: int, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Similar search in index database."""
        logger.info("MemoryVectorStore does not support full text search")
        return []

    def is_support_full_text_search(self) -> bool:
        """Support full text search."""
        return False

    def delete_vector_name(self, vector_name: str):
        """Delete vector name and clean up resources."""
        try:
            with self._db_lock, self._conn() as c:
                c.execute(
                    "DELETE FROM embeddings WHERE collection_name = ?",
                    (vector_name,),
                )
                c.execute(
                    "DELETE FROM collections WHERE name = ?", (vector_name,)
                )
            logger.info(f"Deleted vector collection: {vector_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting vector name {vector_name}: {e}")
            return False

    def delete_by_ids(self, ids: List[str]):
        """Delete by chunk ids."""
        if not ids:
            return
        with self._db_lock, self._conn() as c:
            placeholders = ",".join(["?"] * len(ids))
            c.execute(
                f"DELETE FROM embeddings WHERE collection_name = ? AND chunk_id IN ({placeholders})",
                [self._collection_name, *ids],
            )

    def truncate(self):
        """Truncate collection."""
        with self._db_lock, self._conn() as c:
            c.execute(
                "DELETE FROM embeddings WHERE collection_name = ?",
                (self._collection_name,),
            )

    # ------------------------------------------------------------------ #
    # Internal search
    # ------------------------------------------------------------------ #
    def _build_where_clause(
        self, filters: Optional[MetadataFilters]
    ) -> tuple[str, list]:
        """Return (where_sql, params) for the metadata filter, or ('1=1', [])."""
        if not filters or not getattr(filters, "filters", None):
            return "1=1", []
        clauses: List[str] = []
        params: List[Any] = []
        for f in filters.filters:
            # metadata is stored as JSON text; do a best-effort LIKE match
            # for equality.  This is not as expressive as chroma's filter
            # but covers the common {key: value} case used by DB-GPT.
            if f.op == FilterOperator.EQ:
                val = json.dumps(f.value, ensure_ascii=False)
                # json.dumps adds surrounding quotes for strings; we just
                # substring-match the escaped ``"key": "value"`` form.
                clauses.append("metadata LIKE ?")
                params.append(f'%"{f.key}": {f.value}%')
            else:
                # Unsupported operators are skipped silently to avoid
                # breaking search entirely.
                logger.debug(f"MemoryVectorStore skipping filter op {f.op}")
        if not clauses:
            return "1=1", []
        return " AND ".join(clauses), params

    def _search(
        self,
        text: str,
        topk: int,
        filters: Optional[MetadataFilters],
        with_scores: bool,
    ) -> List[Chunk]:
        if not text:
            return []
        if self.embeddings is None:
            raise ValueError("MemoryVectorStore embeddings is None")
        query_vec = np.asarray(self.embeddings.embed_query(text), dtype=np.float32)
        where_sql, params = self._build_where_clause(filters)
        with self._db_lock, self._conn() as c:
            rows = c.execute(
                f"""
                SELECT chunk_id, content, metadata, vector
                FROM embeddings
                WHERE collection_name = ? AND {where_sql}
                """,
                [self._collection_name, *params],
            ).fetchall()
        if not rows:
            return []
        ids = [r[0] for r in rows]
        contents = [r[1] for r in rows]
        metas = [json.loads(r[2]) if r[2] else {} for r in rows]
        mat = np.frombuffer(b"".join(r[3] for r in rows), dtype=np.float32)
        # Each vector has the same dimension; figure it out from the first.
        dim = len(mat) // len(rows) if len(rows) else 0
        mat = mat.reshape(len(rows), dim)
        # Cosine similarity
        q_norm = query_vec / (np.linalg.norm(query_vec) + 1e-12)
        m_norm = mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-12)
        sims = m_norm @ q_norm  # shape: (N,)
        # Take topk
        k = min(topk, len(rows))
        top_idx = np.argpartition(-sims, k - 1)[:k]
        top_idx = top_idx[np.argsort(-sims[top_idx])]
        results: List[Chunk] = []
        for idx in top_idx:
            score = float(sims[idx])
            results.append(
                Chunk(
                    content=contents[idx],
                    metadata=metas[idx] or {},
                    score=score if with_scores else 0.0,
                    chunk_id=ids[idx],
                )
            )
        return results
