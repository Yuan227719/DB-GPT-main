"""DBSummaryClient class."""

import logging
import threading
import traceback
from typing import Dict, Tuple

from dbgpt.component import SystemApp
from dbgpt.core import Embeddings
from dbgpt.rag.embedding.embedding_factory import EmbeddingFactory
from dbgpt.rag.text_splitter.text_splitter import RDBTextSplitter
from dbgpt.storage.vector_store.base import VectorStoreBase
from dbgpt_ext.rag import ChunkParameters
from dbgpt_ext.rag.summary.gdbms_db_summary import GdbmsSummary
from dbgpt_ext.rag.summary.rdbms_db_summary import RdbmsSummary
from dbgpt_serve.datasource.manages import ConnectorManager
from dbgpt_serve.rag.storage_manager import StorageManager

logger = logging.getLogger(__name__)


# Per-database mutexes to prevent concurrent indexing of the same db_name from
# trampling each other (e.g. startup auto-summary racing with a manual /refresh
# call). When two indexing flows run for the same db, one path's
# delete_db_profile() can drop a chroma collection while the other path still
# has 1000s of writes queued against its UUID, producing
# ``Collection <uuid> does not exist`` errors for every chunk.
_DB_INDEX_LOCKS: Dict[str, threading.Lock] = {}
_DB_INDEX_LOCKS_GUARD = threading.Lock()


def _get_db_index_lock(dbname: str) -> threading.Lock:
    """Return (creating if needed) the per-db indexing mutex."""
    with _DB_INDEX_LOCKS_GUARD:
        lock = _DB_INDEX_LOCKS.get(dbname)
        if lock is None:
            lock = threading.Lock()
            _DB_INDEX_LOCKS[dbname] = lock
        return lock


class DBSummaryClient:
    """The client for DBSummary.

    DB Summary client, provide db_summary_embedding(put db profile and table profile
    summary into vector store), get_similar_tables method(get user query related tables
    info)

    Args:
        system_app (SystemApp): Main System Application class that manages the
            lifecycle and registration of components..
    """

    def __init__(self, system_app: SystemApp):
        """Create a new DBSummaryClient."""
        self.system_app = system_app

        self.app_config = self.system_app.config.configs.get("app_config")
        self.storage_config = self.app_config.rag.storage

    @property
    def embeddings(self) -> Embeddings:
        """Get the embeddings."""
        embedding_factory: EmbeddingFactory = self.system_app.get_component(
            "embedding_factory", component_type=EmbeddingFactory
        )
        return embedding_factory.create()

    def db_summary_embedding(self, dbname, db_type, force: bool = False):
        """Put db profile and table profile summary into vector store.

        Serializes per-db so that concurrent triggers (startup auto-summary,
        ``/refresh`` API, retries on failure) cannot race and delete each
        other's in-flight chroma collections.

        Args:
            dbname: Database name.
            db_type: Database type.
            force: If True, delete existing profile before re-embedding.
                Used by ``/refresh`` so delete + re-embed happen atomically
                under the same lock, avoiding the "Collection <uuid> does
                not exist" race when a concurrent writer still has chunks
                queued against the old collection UUID.
        """
        lock = _get_db_index_lock(dbname)
        if not lock.acquire(blocking=False):
            logger.info(
                f"{dbname} summary already in progress; "
                "skipping concurrent trigger to avoid race with in-flight writes."
            )
            return
        try:
            # 提前检查向量库是否已存在，避免不必要地构造 RdbmsSummary
            # （构造 RdbmsSummary 会遍历所有表跑 DESCRIBE，开销很大）
            vector_store_name = dbname + "_profile"
            table_vector_connector, _ = self._get_vector_connector_by_db(dbname)
            vector_exists = table_vector_connector.vector_name_exists()
            if vector_exists and not force:
                # 向量库已存在，对比 DB 实际表名和向量库里已有表名
                # 只在表名集合发生变化时才刷新，避免无意义的 DESCRIBE
                if not self._has_table_set_changed(dbname, table_vector_connector):
                    logger.info(
                        f"Vector store {vector_store_name} exists and table "
                        f"set unchanged; skip re-embedding"
                    )
                    logger.info("db summary embedding success")
                    return
                logger.info(
                    f"Table set changed for {dbname}, will re-embed vector store"
                )
                # 表名有变化，强制刷新向量库
                self._delete_profile_locked(dbname)

            if force:
                # Must be inside the lock so a concurrent embedding flow
                # cannot queue chunks against the collection we are about
                # to drop.
                self._delete_profile_locked(dbname)
            db_summary_client = self.create_summary_client(dbname, db_type)

            self.init_db_profile(db_summary_client, dbname)

            logger.info("db summary embedding success")
        except Exception as e:
            message = traceback.format_exc()
            logger.warning(
                f"{dbname}, {db_type} summary error!{str(e)}, detail: {message}"
            )
            raise
        finally:
            lock.release()

    def get_db_summary(self, dbname, query, topk):
        """Get user query related tables info."""
        from dbgpt_ext.rag.retriever.db_schema import DBSchemaRetriever

        table_vector_connector, field_vector_connector = (
            self._get_vector_connector_by_db(dbname)
        )
        retriever = DBSchemaRetriever(
            top_k=topk,
            table_vector_store_connector=table_vector_connector,
            field_vector_store_connector=field_vector_connector,
            separator="--table-field-separator--",
        )

        table_docs = retriever.retrieve(query)
        ans = [d.content for d in table_docs]
        return ans

    def init_db_summary(self):
        """Initialize db summary profile."""
        local_db_manager = ConnectorManager.get_instance(self.system_app)
        db_mange = local_db_manager
        dbs = db_mange.get_db_list()
        for item in dbs:
            try:
                self.db_summary_embedding(item["db_name"], item["db_type"])
            except Exception as e:
                message = traceback.format_exc()
                logger.warning(
                    f"{item['db_name']}, {item['db_type']} summary error!{str(e)}, "
                    f"detail: {message}"
                )

    def init_db_profile(self, db_summary_client, dbname):
        """Initialize db summary profile.

        Args:
        db_summary_client(DBSummaryClient): DB Summary Client
        dbname(str): dbname
        """
        vector_store_name = dbname + "_profile"

        table_vector_connector, field_vector_connector = (
            self._get_vector_connector_by_db(dbname)
        )
        if not table_vector_connector.vector_name_exists():
            from dbgpt_ext.rag.assembler.db_schema import DBSchemaAssembler
            from dbgpt_ext.rag.summary.rdbms_db_summary import _DEFAULT_COLUMN_SEPARATOR

            chunk_parameters = ChunkParameters(
                text_splitter=RDBTextSplitter(
                    column_separator=_DEFAULT_COLUMN_SEPARATOR,
                    separator="--table-field-separator--",
                )
            )
            db_assembler = DBSchemaAssembler.load_from_connection(
                connector=db_summary_client.db,
                table_vector_store_connector=table_vector_connector,
                field_vector_store_connector=field_vector_connector,
                chunk_parameters=chunk_parameters,
                max_seq_length=self.app_config.service.web.embedding_model_max_seq_len,
            )

            if len(db_assembler.get_chunks()) > 0:
                db_assembler.persist()
        else:
            logger.info(f"Vector store name {vector_store_name} exist")
        logger.info("initialize db summary profile success...")

    def delete_db_profile(self, dbname):
        """Delete db profile.

        Held under the per-db indexing lock so a delete cannot race with a
        concurrent embedding flow (which would otherwise see chroma drop
        the collection mid-write and fail every subsequent chunk with
        ``Collection <uuid> does not exist``).
        """
        lock = _get_db_index_lock(dbname)
        with lock:
            self._delete_profile_locked(dbname)

    def _delete_profile_locked(self, dbname):
        """Delete profile vectors. Caller must hold the per-db indexing lock."""
        table_vector_store_name = dbname + "_profile"
        field_vector_store_name = dbname + "_profile_field"

        table_vector_connector, field_vector_connector = (
            self._get_vector_connector_by_db(dbname)
        )

        table_vector_connector.delete_vector_name(table_vector_store_name)
        field_vector_connector.delete_vector_name(field_vector_store_name)

        # Drop cached ChromaStore instances so the next
        # ``create_vector_store`` returns a fresh store whose internal
        # ``self._collection`` reference points at the newly created
        # collection instead of the one we just deleted (otherwise every
        # subsequent upsert fails with "Collection <uuid> does not exist").
        storage_manager = StorageManager.get_instance(self.system_app)
        storage_manager.invalidate_store(table_vector_store_name)
        storage_manager.invalidate_store(field_vector_store_name)

        logger.info(f"delete db profile {dbname} success")

    def _has_table_set_changed(self, dbname: str, table_vector_connector) -> bool:
        """Check whether the live table set differs from what is in the vector store.

        Reads only ``table_name`` metadata from the vector store (cheap) and
        ``SHOW TABLES`` from the DB (cheap — no DESCRIBE). If the two sets
        match, we skip the expensive re-embedding that would otherwise run
        ``DESCRIBE`` on every table on every restart.

        Returns:
            True if tables were added/removed (vector store is stale).
            False if the vector store is in sync with the live schema.
        """
        try:
            # 1. 从向量库读取已存储的表名
            # 不用 part=table 过滤，因为 separated=0 的表（字段总长 < 512）没有
            # part 字段（字段内联在表级 chunk 里）。直接读取所有 chunk 的
            # table_name metadata，用集合去重即可。
            metadatas = table_vector_connector.get_all_metadata()
            vector_table_names = {
                m.get("table_name") for m in metadatas if m.get("table_name")
            }

            # 2. 从 DB connector 获取实际表名（直接跑 SHOW TABLES，不跑 DESCRIBE）
            # 注意：不能用 connector.get_table_names()，因为它返回的是 __init__ 时
            # 缓存的表名，可能已过时。这里直接用 inspector.get_table_names() 跑
            # 实时的 SHOW TABLES，确保拿到最新的表名列表。
            from dbgpt_serve.datasource.manages import ConnectorManager

            connector_manager = ConnectorManager.get_instance(self.system_app)
            connector = connector_manager.get_connector(dbname)
            # 直接调用 inspector 获取实时表名，绕过 connector 的初始化缓存
            inspector = connector._inspector  # type: ignore[attr-defined]
            _schema = (
                None
                if connector.db_type in ("sqlite", "duckdb")
                else connector._engine.url.database  # type: ignore[attr-defined]
            )
            live_table_names = set(inspector.get_table_names(schema=_schema))

            # 3. 对比表名集合
            if vector_table_names == live_table_names:
                logger.info(
                    f"Table set unchanged for {dbname}: "
                    f"{len(live_table_names)} tables"
                )
                return False
            added = live_table_names - vector_table_names
            removed = vector_table_names - live_table_names
            logger.info(
                f"Table set changed for {dbname}: "
                f"added={sorted(added)}, removed={sorted(removed)}"
            )
            return True
        except Exception as e:
            # 如果对比失败（比如向量库 schema 不支持过滤），保守地触发刷新
            logger.warning(
                f"Failed to compare table set for {dbname}: {e}; "
                "will trigger re-embedding to be safe"
            )
            return True

    @staticmethod
    def create_summary_client(dbname: str, db_type: str):
        """
        Create a summary client based on the database type.

        Args:
            dbname (str): The name of the database.
            db_type (str): The type of the database.
        """
        if "graph" in db_type:
            return GdbmsSummary(dbname, db_type)
        else:
            return RdbmsSummary(dbname, db_type)

    def _get_vector_connector_by_db(
        self, dbname
    ) -> Tuple[VectorStoreBase, VectorStoreBase]:
        vector_store_name = dbname + "_profile"
        storage_manager = StorageManager.get_instance(self.system_app)
        table_vector_store = storage_manager.create_vector_store(
            index_name=vector_store_name
        )
        field_vector_store_name = dbname + "_profile_field"
        field_vector_store = storage_manager.create_vector_store(
            index_name=field_vector_store_name
        )
        return table_vector_store, field_vector_store
