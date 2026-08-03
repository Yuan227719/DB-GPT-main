"""Connection manager."""

import json
import logging
import threading
import time
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Type

from dbgpt.component import BaseComponent, ComponentType, SystemApp
from dbgpt.core.awel.flow import ResourceMetadata
from dbgpt.datasource.base import BaseConnector, BaseDatasourceParameters
from dbgpt.util.annotations import Deprecated
from dbgpt.util.configure.manager import _resolve_env_vars
from dbgpt.util.executor_utils import ExecutorFactory
from dbgpt.util.parameter_utils import _get_parameter_descriptions
from dbgpt_ext.datasource.schema import DBType
from dbgpt_serve.core import ResourceParameters, ResourceTypes

from ..api.schemas import DatasourceCreateRequest
from .connect_config_db import ConnectConfigDao
from .db_conn_info import DBConfig

if TYPE_CHECKING:
    # TODO: Don't depend on the rag module.
    from dbgpt_serve.datasource.service.db_summary_client import DBSummaryClient

logger = logging.getLogger(__name__)


class ConnectorManager(BaseComponent):
    """Connector manager."""

    name = ComponentType.CONNECTOR_MANAGER

    # Default TTL for the connector cache below. The expensive part of
    # building a connector is SQLAlchemy ``MetaData.reflect(bind=engine)``
    # inside ``RDBMSConnector.__init__``, which on large schemas (e.g. an
    # MSSQL database with hundreds of tables) takes tens of seconds because
    # the dialect issues per-table reflection queries. Caching the
    # constructed connector lets that cost amortise across many chats.
    _CONNECTOR_CACHE_DEFAULT_TTL = 1800  # 30 minutes

    def __init__(self, system_app: SystemApp):
        """Create a new ConnectorManager."""
        self.storage = ConnectConfigDao()
        self.system_app = system_app
        self._db_summary_client: Optional["DBSummaryClient"] = None

        # Per-db_name cache of (created_at_unix_ts, connector_instance).
        # Lookups are cheap; we serialize them through ``_cache_lock`` to
        # avoid TOCTOU between get / set / pop.
        self._connector_cache: Dict[str, Tuple[float, BaseConnector]] = {}
        self._connector_cache_lock = threading.Lock()
        # Per-db_name "creation" lock so that when many chats race for a
        # cold db_name only one of them runs the expensive reflection;
        # the others wait and reuse the same instance.
        self._connector_creation_locks: Dict[str, threading.Lock] = {}
        self._connector_cache_ttl = self._CONNECTOR_CACHE_DEFAULT_TTL

        super().__init__(system_app)

    def init_app(self, system_app: SystemApp):
        """Init component."""
        self.system_app = system_app

    def on_init(self):
        """Execute on init.

        Load all connector classes.
        """
        from dbgpt.datasource.rdbms.base import RDBMSConnector  # noqa: F401
        from dbgpt_ext.datasource.conn_neo4j import Neo4jConnector  # noqa: F401
        from dbgpt_ext.datasource.conn_spark import SparkConnector  # noqa: F401
        from dbgpt_ext.datasource.conn_tugraph import TuGraphConnector  # noqa: F401
        from dbgpt_ext.datasource.rdbms.conn_clickhouse import (  # noqa: F401
            ClickhouseConnector,
        )
        from dbgpt_ext.datasource.rdbms.conn_doris import DorisConnector  # noqa: F401
        from dbgpt_ext.datasource.rdbms.conn_duckdb import DuckDbConnector  # noqa: F401
        from dbgpt_ext.datasource.rdbms.conn_gaussdb import (  # noqa: F401
            GaussDBConnector,
        )
        from dbgpt_ext.datasource.rdbms.conn_hive import HiveConnector  # noqa: F401
        from dbgpt_ext.datasource.rdbms.conn_kyuubi import (  # noqa: F401
            KyuubiConnector,
        )
        from dbgpt_ext.datasource.rdbms.conn_mssql import MSSQLConnector  # noqa: F401
        from dbgpt_ext.datasource.rdbms.conn_mysql import MySQLConnector  # noqa: F401
        from dbgpt_ext.datasource.rdbms.conn_oceanbase import (  # noqa: F401
            OceanBaseConnector,
        )
        from dbgpt_ext.datasource.rdbms.conn_openGauss import (  # noqa: F401
            openGaussConnector,
        )

        # 添加OracleConnector导入
        from dbgpt_ext.datasource.rdbms.conn_oracle import OracleConnector  # noqa: F401
        from dbgpt_ext.datasource.rdbms.conn_postgresql import (  # noqa: F401
            PostgreSQLConnector,
        )
        from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnector  # noqa: F401
        from dbgpt_ext.datasource.rdbms.conn_starrocks import (  # noqa: F401
            StarRocksConnector,
        )
        from dbgpt_ext.datasource.rdbms.conn_vertica import (  # noqa: F401
            VerticaConnector,
        )
        from dbgpt_ext.datasource.rdbms.dialect.oceanbase.ob_dialect import (  # noqa: F401
            OBDialect,
        )

        from .connect_config_db import ConnectConfigEntity  # noqa: F401

    def before_start(self):
        """Execute before start."""
        from dbgpt_serve.datasource.service.db_summary_client import DBSummaryClient

        self._db_summary_client = DBSummaryClient(self.system_app)
        # 启动后台定时检查线程：每 30 分钟遍历所有 db，对比向量库和实际表名
        # 只有表名集合发生变化时才刷新向量库（由 db_summary_embedding 内部的
        # _has_table_set_changed 决定），避免无意义的 DESCRIBE
        self._schema_check_stop = threading.Event()
        self._schema_check_thread = threading.Thread(
            target=self._periodic_schema_check,
            name="schema-check",
            daemon=True,
        )
        self._schema_check_thread.start()

    def before_stop(self):
        """Stop the periodic schema-check thread on shutdown."""
        if hasattr(self, "_schema_check_stop"):
            self._schema_check_stop.set()
        # 同时清理所有缓存的 connector，释放 SQLAlchemy engine
        self.clear_connector_cache()

    def _periodic_schema_check(self):
        """Background loop that checks every 30 min whether any db's table
        set has changed and refreshes the vector store only when needed.

        This runs in a daemon thread and is best-effort: exceptions are
        logged but do not stop the loop. The 30-minute interval matches
        ``_CONNECTOR_CACHE_DEFAULT_TTL`` so a cold connector build (which
        already does schema-change detection) and this explicit check
        stay roughly in sync.
        """
        # 首次启动延迟 60 秒，避免和 init_db_summary 抢锁
        if self._schema_check_stop.wait(60):
            return
        while not self._schema_check_stop.is_set():
            try:
                dbs = self.get_db_list()
                for item in dbs:
                    if self._schema_check_stop.is_set():
                        return
                    db_name = item.get("db_name")
                    db_type = item.get("db_type")
                    if not db_name or not db_type:
                        continue
                    try:
                        # 不传 force：让 _has_table_set_changed 决定是否刷新
                        self.db_summary_client.db_summary_embedding(
                            db_name, db_type
                        )
                    except Exception as e:
                        logger.warning(
                            "Periodic schema check failed for %s: %s",
                            db_name,
                            e,
                        )
            except Exception as e:
                logger.warning("Periodic schema check iteration failed: %s", e)
            # 等待 30 分钟或停止信号
            if self._schema_check_stop.wait(self._CONNECTOR_CACHE_DEFAULT_TTL):
                return

    @property
    def db_summary_client(self) -> "DBSummaryClient":
        """Get DBSummaryClient."""
        if not self._db_summary_client:
            raise ValueError("DBSummaryClient is not initialized")
        return self._db_summary_client

    def _get_all_subclasses(
        self, cls: Type[BaseConnector]
    ) -> List[Type[BaseConnector]]:
        """Get all subclasses of cls."""
        subclasses = cls.__subclasses__()
        for subclass in subclasses:
            subclasses += self._get_all_subclasses(subclass)
        return subclasses

    @Deprecated(
        version="0.7.0", remove_version="0.8.0", alternative="get_supported_types"
    )
    def get_all_completed_types(self) -> List[DBType]:
        """Get all completed types."""
        support_types: List[DBType] = []
        for db_type in self._supported_types():
            db_type_enum = DBType.of_db_type(db_type)
            if db_type_enum:
                support_types.append(db_type_enum)
        return support_types

    def get_supported_types(self) -> ResourceTypes:
        """Get supported types."""
        support_type_params = []
        for db_type_name, cls in self._supported_types().items():
            db_type = DBType.of_db_type(db_type_name)
            if not db_type:
                continue
            param_cls = cls.param_class()
            parameters = _get_parameter_descriptions(param_cls)
            label = db_type.value()
            description = label
            metadata_name = f"_resource_metadata_{param_cls.__name__}"
            if hasattr(param_cls, metadata_name):
                flow_metadata: ResourceMetadata = getattr(param_cls, metadata_name)
                label = flow_metadata.label
                description = flow_metadata.description
            support_type_params.append(
                ResourceParameters(
                    name=db_type.value(),
                    label=label,
                    description=description,
                    parameters=parameters,
                )
            )
        return ResourceTypes(types=support_type_params)

    def _supported_types(self) -> Dict[str, Type[BaseConnector]]:
        """Get supported types."""
        chat_classes = self._get_all_subclasses(BaseConnector)
        support_types = {}
        for cls in chat_classes:
            if cls.db_type and cls.is_normal_type():
                db_type = DBType.of_db_type(cls.db_type)
                if db_type:
                    support_types[db_type.value()] = cls
        return support_types

    def get_cls_by_dbtype(self, db_type) -> Type[BaseConnector]:
        """Get class by db type."""
        chat_classes = self._get_all_subclasses(BaseConnector)  # type: ignore
        result = None
        for cls in chat_classes:
            if cls.db_type == db_type and cls.is_normal_type():
                result = cls
        if not result:
            raise ValueError("Unsupported Db Type！" + db_type)
        return result

    def get_connector(self, db_name: str):
        """Get or create a connection instance for ``db_name``.

        Constructed connectors are cached for ``_connector_cache_ttl``
        seconds (30 min by default). The motivation is that
        ``RDBMSConnector.__init__`` runs ``MetaData.reflect(bind=engine)``,
        which for a SQL Server database with ~900 tables takes ~60s because
        SQLAlchemy's MSSQL dialect reflects columns/PK/FK per table. Without
        this cache every chat invocation paid that cost; with it, only the
        first chat after a cold start (or after the TTL expires) is slow.

        Concurrency: a per-``db_name`` creation lock ensures that when
        several requests race for the same cold entry only one of them
        runs the slow reflection; the others wait and reuse it.

        Schema-change detection: when the cache entry expires and a new
        connector is built, the new table-name set is compared against the
        previous one. If tables were added/removed, the vector store
        (DBSchemaAssembler output) is refreshed asynchronously via
        ``DBSummaryClient.db_summary_embedding`` so retrieval stays in sync
        with the live schema without manual intervention.

        Args:
            db_name (str): database name
        """
        now = time.time()
        with self._connector_cache_lock:
            cached = self._connector_cache.get(db_name)
            if cached and now - cached[0] < self._connector_cache_ttl:
                return cached[1]

        creation_lock = self._get_connector_creation_lock(db_name)
        with creation_lock:
            # Double-checked locking: another thread may have populated
            # the cache while we were waiting for the creation lock.
            with self._connector_cache_lock:
                cached = self._connector_cache.get(db_name)
                if cached and time.time() - cached[0] < self._connector_cache_ttl:
                    return cached[1]

            # Snapshot the previous table list (if any) before rebuilding
            # so we can detect schema changes after the rebuild.
            prev_tables: Optional[set] = None
            with self._connector_cache_lock:
                cached = self._connector_cache.get(db_name)
                if cached:
                    try:
                        prev_tables = set(
                            cached[1].get_table_names()  # type: ignore[attr-defined]
                        )
                    except Exception:
                        prev_tables = None

            connector = self._build_connector(db_name)
            with self._connector_cache_lock:
                self._connector_cache[db_name] = (time.time(), connector)

            # If the table set changed since the last build, refresh the
            # vector store asynchronously so DBSchemaRetriever stays in sync.
            if prev_tables is not None:
                try:
                    new_tables = set(connector.get_table_names())  # type: ignore[attr-defined]
                except Exception:
                    new_tables = None
                if new_tables is not None and new_tables != prev_tables:
                    self._trigger_schema_embedding(db_name)
            return connector

    def _trigger_schema_embedding(self, db_name: str) -> None:
        """Asynchronously refresh vector store for ``db_name``.

        Looks up the db_type from the persisted config and submits
        ``db_summary_embedding`` to the background executor. Best-effort:
        failures are logged but do not propagate, since a vector-store
        refresh failure should not break the chat request that triggered it.
        """
        try:
            db_config = self.storage.get_db_config(db_name)
            db_type = db_config.get("db_type", "")
            if not db_type:
                logger.warning(
                    "Cannot trigger schema embedding for %s: db_type missing",
                    db_name,
                )
                return
            executor = self.system_app.get_component(
                ComponentType.EXECUTOR_DEFAULT, ExecutorFactory
            ).create()  # type: ignore
            executor.submit(
                self.db_summary_client.db_summary_embedding, db_name, db_type
            )
            logger.info(
                "Schema change detected for %s, scheduled vector store refresh",
                db_name,
            )
        except Exception as e:
            logger.warning(
                "Failed to schedule vector store refresh for %s: %s",
                db_name,
                e,
            )

    def invalidate_connector(self, db_name: str) -> None:
        """Drop the cached connector (if any) for ``db_name``.

        Call this after editing the datasource config, refreshing the
        schema, or deleting the datasource. The next ``get_connector``
        will rebuild from scratch. Best-effort disposal of the underlying
        SQLAlchemy engine is attempted so connections are released
        promptly rather than waiting for GC.
        """
        with self._connector_cache_lock:
            cached = self._connector_cache.pop(db_name, None)
        if cached is not None:
            _, connector = cached
            self._dispose_connector(connector)

    def clear_connector_cache(self) -> None:
        """Drop all cached connectors. Useful for tests / shutdown hooks."""
        with self._connector_cache_lock:
            cache = self._connector_cache
            self._connector_cache = {}
        for _, connector in cache.values():
            self._dispose_connector(connector)

    def _get_connector_creation_lock(self, db_name: str) -> threading.Lock:
        with self._connector_cache_lock:
            lock = self._connector_creation_locks.get(db_name)
            if lock is None:
                lock = threading.Lock()
                self._connector_creation_locks[db_name] = lock
            return lock

    @staticmethod
    def _dispose_connector(connector: BaseConnector) -> None:
        """Best-effort release of the SQLAlchemy engine, if any."""
        for attr in ("_engine", "engine"):
            engine = getattr(connector, attr, None)
            if engine is not None and hasattr(engine, "dispose"):
                try:
                    engine.dispose()
                except Exception as err:  # pragma: no cover - defensive
                    logger.debug(
                        "engine.dispose() failed while evicting connector cache: %s",
                        err,
                    )
                return

    def _build_connector(self, db_name: str):
        """Construct a fresh connector for ``db_name`` (no cache).

        This is the original body of ``get_connector`` prior to caching;
        kept as a private helper so the public ``get_connector`` method
        can stay focused on cache logic.
        """
        db_config = self.storage.get_db_config(db_name)

        pwd = db_config["db_pwd"]
        if pwd:
            db_config["db_pwd"] = _resolve_env_vars(pwd)

        db_type = DBType.of_db_type(db_config.get("db_type"))
        if not db_type:
            raise ValueError("Unsupported Db Type！" + db_config.get("db_type"))
        connect_instance = self.get_cls_by_dbtype(db_type.value())
        if db_type.is_file_db():
            db_path = db_config.get("db_path")
            return connect_instance.from_file_path(db_path)  # type: ignore
        elif db_type.value() == "oracle":
            logger.info("-------------Oracle Datasource------------")
            host = db_config.get("db_host")
            port = db_config.get("db_port")
            user = db_config.get("db_user")
            pwd = db_config.get("db_pwd")
            extConfig = db_config.get("ext_config")
            dbJson = json.loads(extConfig)
            service_name = dbJson.get("service_name", None)
            sid = (dbJson.get("sid", None),)
            return connect_instance.from_uri_db(  # type: ignore
                host=host, port=port, user=user, pwd=pwd, service_name=service_name
            )
        else:
            db_host = db_config.get("db_host")
            db_port = db_config.get("db_port")
            db_user = db_config.get("db_user")
            db_pwd = db_config.get("db_pwd")

            try:
                ext_config = db_config.get("ext_config")
                db_json = json.loads(ext_config) if ext_config else {}
                schema = db_json.get("schema", None)
            except (json.JSONDecodeError, TypeError):
                # Handle JSON decode failure and None/invalid types
                db_json = {}
                schema = None

            # Kyuubi may use ZooKeeper discovery (comma-separated hosts).
            # The plain host:port URL would fail to parse, and the ZK
            # fields live in ext_config — rebuild via from_persisted_state
            # so the connector gets the full parameter set.
            if db_type.value() == "kyuubi" and db_host and "," in db_host:
                param_cls = connect_instance.param_class()
                # from_persisted_state expects ext_config as a dict.
                parsed_config = dict(db_config)
                if isinstance(parsed_config.get("ext_config"), str):
                    try:
                        parsed_config["ext_config"] = json.loads(
                            parsed_config["ext_config"]
                        )
                    except (json.JSONDecodeError, TypeError):
                        parsed_config["ext_config"] = {}
                param = param_cls.from_persisted_state(parsed_config)
                return param.create_connector()

            return connect_instance.from_uri_db(  # type: ignore
                host=db_host,
                port=db_port,
                user=db_user,
                pwd=db_pwd,
                db_name=db_name,
                schema=schema,
            )

    def _create_parameters(
        self, request: DatasourceCreateRequest
    ) -> BaseDatasourceParameters:
        """Create parameters."""
        db_type = DBType.of_db_type(request.type)
        if not db_type:
            raise ValueError("Unsupported Db Type！" + request.type)
        support_types = self._supported_types()
        if db_type.value() not in support_types:
            raise ValueError("Unsupported Db Type！" + request.type)
        cls = support_types[db_type.value()]
        param_cls = cls.param_class()
        # ignore_extra_fields is used to ignore extra fields in the request
        return param_cls.from_dict(request.params, ignore_extra_fields=True)

    def _get_param_cls(self, db_type: str) -> Type[BaseDatasourceParameters]:
        """Get param class."""
        support_types = self._supported_types()
        if db_type not in support_types:
            raise ValueError("Unsupported Db Type！" + db_type)
        cls = support_types[db_type]
        return cls.param_class()

    def create_connector(self, param: BaseDatasourceParameters) -> BaseConnector:
        """Create a new connector instance."""
        return param.create_connector()

    @Deprecated(
        version="0.7.0",
        remove_version="0.8.0",
        alternative="test_connection",
    )
    def test_connect(self, db_info: DBConfig) -> BaseConnector:
        """Test connectivity.

        (Deprecated) Use test_connection instead.

        Args:
            db_info (DBConfig): db connect info.

        Returns:
            BaseConnector: connector instance.

        Raises:
            ValueError: Test connect Failure.
        """
        try:
            db_type = DBType.of_db_type(db_info.db_type)
            if not db_type:
                raise ValueError("Unsupported Db Type！" + db_info.db_type)
            connect_instance = self.get_cls_by_dbtype(db_type.value())
            if db_type.is_file_db():
                db_path = db_info.file_path
                return connect_instance.from_file_path(db_path)  # type: ignore
            else:
                db_name = db_info.db_name
                db_host = db_info.db_host
                db_port = db_info.db_port
                db_user = db_info.db_user
                db_pwd = db_info.db_pwd
                return connect_instance.from_uri_db(  # type: ignore
                    host=db_host,
                    port=db_port,
                    user=db_user,
                    pwd=db_pwd,
                    db_name=db_name,
                )
        except Exception as e:
            logger.error(f"{db_info.db_name} Test connect Failure!{str(e)}")
            raise ValueError(f"{db_info.db_name} Test connect Failure!{str(e)}")

    def test_connection(self, request: DatasourceCreateRequest) -> bool:
        """Test connection.

        Args:
            request (DatasourceCreateRequest): The request.

        Returns:
            bool: True if connection is successful.
        """
        try:
            pwd = request.params.get("password")
            if pwd:
                request.params["password"] = _resolve_env_vars(pwd)

            param = self._create_parameters(request)
            _connector = self.create_connector(param)
            return True
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error(f"Test connection Failure!{str(e)}\n{tb}")
            # Write full traceback to file for debugging.
            try:
                with open(r"e:\embed_agent\DB-GPT-main\test_conn_error.log",
                          "a", encoding="utf-8") as f:
                    f.write(f"=== Test conn failed ===\n{tb}\n\n")
            except Exception:
                pass
            raise ValueError(f"Test connection Failure!{str(e)}")

    def get_db_list(self, db_name: Optional[str] = None, user_id: Optional[str] = None):
        """Get db list."""
        return self.storage.get_db_list(db_name, user_id)

    @Deprecated(
        version="0.7.0",
        remove_version="0.8.0",
    )
    def delete_db(self, db_name: str):
        """Delete db connect info."""
        return self.storage.delete_db(db_name)

    @Deprecated(
        version="0.7.0",
        remove_version="0.8.0",
    )
    def edit_db(self, db_info: DBConfig):
        """Edit db connect info."""
        return self.storage.update_db_info(
            db_info.db_name,
            db_info.db_type,
            db_info.file_path,
            db_info.db_host,
            db_info.db_port,
            db_info.db_user,
            db_info.db_pwd,
            db_info.comment,
        )

    async def async_db_summary_embedding(self, db_name, db_type):
        """Async db summary embedding."""
        executor = self.system_app.get_component(
            ComponentType.EXECUTOR_DEFAULT, ExecutorFactory
        ).create()  # type: ignore
        executor.submit(self.db_summary_client.db_summary_embedding, db_name, db_type)
        return True

    @Deprecated(
        version="0.7.0",
        remove_version="0.8.0",
    )
    def add_db(self, db_info: DBConfig, user_id: Optional[str] = None):
        """Add db connect info.

        Args:
            db_info (DBConfig): db connect info.
        """
        logger.info(f"add_db:{db_info.__dict__}")
        try:
            db_type = DBType.of_db_type(db_info.db_type)
            if not db_type:
                raise ValueError("Unsupported Db Type！" + db_info.db_type)
            if db_type.is_file_db():
                self.storage.add_file_db(
                    db_info.db_name,
                    db_info.db_type,
                    db_info.file_path,
                    db_info.comment,
                    user_id,
                )
            else:
                self.storage.add_url_db(
                    db_info.db_name,
                    db_info.db_type,
                    db_info.db_host,
                    db_info.db_port,
                    db_info.db_user,
                    db_info.db_pwd,
                    db_info.comment,
                    user_id,
                )
            # async embedding
            executor = self.system_app.get_component(
                ComponentType.EXECUTOR_DEFAULT, ExecutorFactory
            ).create()  # type: ignore
            executor.submit(
                self.db_summary_client.db_summary_embedding,
                db_info.db_name,
                db_info.db_type,
            )
        except Exception as e:
            raise ValueError("Add db connect info error!" + str(e))

        return True
