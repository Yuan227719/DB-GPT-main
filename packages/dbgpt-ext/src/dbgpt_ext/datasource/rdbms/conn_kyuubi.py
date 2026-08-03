"""Kyuubi Connector.

Kyuubi is a multi-tenant Thrift JDBC/ODBC server that provides a
HiveServer2-compatible interface to Spark and Trino engines.
This connector extends HiveConnector with ZooKeeper service discovery and
engine-type session configuration.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Type

from sqlalchemy import create_engine, text

from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    ResourceCategory,
    auto_register_resource,
)
from dbgpt.util.i18n_utils import _

from .conn_hive import HiveConnector, HiveParameters

logger = logging.getLogger(__name__)


def _patch_pyhive_for_trino() -> None:
    """Patch pyhive to use double quotes instead of backticks for Trino engine.

    pyhive hardcodes ``USE `{database}` `` in ``Connection.__init__``, but Trino
    rejects backtick-quoted identifiers and requires double quotes.  When the
    connection configuration indicates a Trino engine
    (``kyuubi.engine.type=TRINO``), this patch replaces backticks with double
    quotes in any SQL executed during connection setup.

    Spark SQL and Hive are unaffected — the patch only triggers for Trino.
    """
    try:
        import pyhive.hive
    except ImportError:
        return

    if getattr(pyhive.hive.Connection, "_dbgpt_trino_patched", False):
        return

    _orig_init = pyhive.hive.Connection.__init__

    def _patched_init(self, *args: Any, **kwargs: Any) -> None:
        configuration = kwargs.get("configuration") or {}
        engine_type = str(configuration.get("kyuubi.engine.type", "")).upper()
        if engine_type != "TRINO":
            _orig_init(self, *args, **kwargs)
            return

        # Temporarily wrap Cursor.execute to replace backticks with double
        # quotes.  This covers the hardcoded ``USE `{database}`` in pyhive.
        _orig_execute = pyhive.hive.Cursor.execute

        def _fixed_execute(
            self_cursor: Any, operation: Any, parameters: Any = None, **kw: Any
        ) -> Any:
            if isinstance(operation, str) and "`" in operation:
                operation = operation.replace("`", '"')
            return _orig_execute(self_cursor, operation, parameters, **kw)

        pyhive.hive.Cursor.execute = _fixed_execute
        try:
            _orig_init(self, *args, **kwargs)
        finally:
            pyhive.hive.Cursor.execute = _orig_execute

    pyhive.hive.Connection.__init__ = _patched_init
    pyhive.hive.Connection._dbgpt_trino_patched = True


def _apply_trino_identifier_preparer(engine: Any) -> None:
    """Swap HiveDialect's backtick preparer for a double-quote one.

    ``HiveDialect`` hardcodes ``initial_quote='`'`` in
    ``HiveIdentifierPreparer``, which breaks Trino.  We replace the
    dialect's ``preparer`` class and live ``identifier_preparer`` instance
    so that reflection SQL such as ``SHOW TABLES IN "schema"`` uses double
    quotes instead of backticks.
    """
    from pyhive.sqlalchemy_hive import HiveIdentifierPreparer

    dialect = engine.dialect

    class _TrinoCompatPreparer(HiveIdentifierPreparer):
        """Same as HiveIdentifierPreparer (quotes everything) but uses
        double quotes instead of backticks, as required by Trino."""

        def __init__(self, dialect_):
            # IdentifierPreparer accepts initial_quote / final_quote.
            # We bypass HiveIdentifierPreparer.__init__ (which forces '`').
            from sqlalchemy.sql.compiler import IdentifierPreparer

            IdentifierPreparer.__init__(
                self,
                dialect_,
                initial_quote='"',
                final_quote='"',
            )

    dialect.preparer = _TrinoCompatPreparer
    # Re-instantiate so the live ``identifier_preparer`` attribute uses the
    # new class with double-quote characters.
    dialect.identifier_preparer = _TrinoCompatPreparer(dialect)


def _patch_pyhive_get_columns_for_trino() -> None:
    """Patch ``HiveDialect.get_columns`` to tolerate extra DESCRIBE columns.

    pyhive hardcodes ``for (col_name, col_type, _comment) in rows`` in
    ``sqlalchemy_hive.py`` (line ~329).  Trino's ``DESCRIBE`` returns 4
    columns (``col_name, col_type, comment, extra``), which makes pyhive
    raise ``ValueError: too many values to unpack (expected 3)`` during
    SQLAlchemy reflection.

    This patch re-implements ``get_columns`` to unpack only the first 3
    columns and ignore any extras.  The patch is module-level: it only
    replaces the method once per process, and is harmless for Hive/Spark
    (which return exactly 3 columns).
    """
    try:
        from pyhive.sqlalchemy_hive import HiveDialect
    except ImportError:
        return

    if getattr(HiveDialect.get_columns, "_dbgpt_trino_patched", False):
        return

    import re as _re
    from sqlalchemy import exc as _exc
    from sqlalchemy import text as _text
    from sqlalchemy.types import (
        TypeEngine as _TypeEngine,
        VARCHAR as _VARCHAR,
    )

    # Keep a handle to the original for the non-patched path.
    _orig_get_columns = HiveDialect.get_columns

    def _trino_compat_get_columns(
        self, connection, table_name, schema=None, **kw
    ):
        # Only behave differently when this looks like a Trino/Kyuubi-Trino
        # context (the inspector is the one we patched).  For plain Hive
        # we delegate to the original implementation.
        preparer = getattr(self, "identifier_preparer", None)
        initial_quote = getattr(preparer, "initial_quote", "`")
        if initial_quote != '"':
            # Backtick-style preparer -> plain Hive, use original.
            return _orig_get_columns(self, connection, table_name, schema, **kw)

        # Build "schema.table" identifier with double quotes.
        full_table = table_name
        if schema:
            full_table = f'{schema}."{table_name}"'
        else:
            full_table = f'"{table_name}"'

        try:
            # 临时调试：打印调用栈，定位谁在重复调 get_columns
            import traceback as _tb
            _tb_str = "".join(_tb.format_stack()[-5:])
            logger.warning(
                "DBGPT_DEBUG _trino_compat_get_columns called for %s, stack=\n%s",
                full_table, _tb_str,
            )
            rows = connection.execute(
                _text(f"DESCRIBE {full_table}")
            ).fetchall()
        except _exc.OperationalError as e:
            # Trino may return an error for views, materialized views, or
            # temp tables listed by SHOW TABLES that cannot be DESCRIBE'd.
            # Return an empty column list rather than raising, so that
            # batch reflection (MetaData.reflect / db_summary) can continue
            # with the remaining tables instead of aborting.
            logger.warning(
                "Trino DESCRIBE %s failed: %s — returning empty column list",
                full_table, e,
            )
            return []

        # DEBUG: 临时调试日志，输出 DESCRIBE 原始返回内容
        # logger.warning(
        #     "DBGPT_DEBUG DESCRIBE %s raw_rows=%d first=%r",
        #     full_table, len(rows), rows[:3] if rows else None,
        # )

        # Strip whitespace, filter header / partition-info rows.
        cleaned = []
        for row in rows:
            # pyhive 返回的是 Row 对象，转成 list
            vals = list(row) if not isinstance(row, (list, tuple)) else list(row)
            vals = [c.strip() if isinstance(c, str) else c for c in vals]
            if not vals:
                continue
            first = vals[0]
            if not first or first.startswith("#"):
                continue
            if first == "# Partition Information":
                break
            cleaned.append(vals)

        result = []
        for vals in cleaned:
            # DESCRIBE 返回 4 列: (col_name, col_type, comment, extra)
            # 但 Trino/Iceberg 实际输出格式: (col_name, col_type, "", real_comment)
            # 第 3 列常常为空，真正的 comment 在第 4 列
            col_name = vals[0] if len(vals) > 0 else None
            col_type = vals[1] if len(vals) > 1 else None
            comment = vals[2] if len(vals) > 2 else None
            # 如果第 3 列为空，尝试从第 4 列取 comment
            if not comment and len(vals) > 3 and vals[3]:
                comment = vals[3]
            if not col_name:
                continue

            # Simplify the type, e.g. 'map<int,int>' -> 'map'.
            if col_type:
                m = _re.search(r"^\w+", col_type)
                col_type_simple = m.group(0) if m else col_type
            else:
                col_type_simple = "string"

            # Build a SQLAlchemy type.  We default to VARCHAR to avoid
            # fragile type mapping; DB-GPT only needs the column list.
            coltype = _VARCHAR()
            result.append(
                {
                    "name": col_name,
                    "type": coltype,
                    "nullable": True,
                    "default": None,
                    "comment": comment,
                }
            )
        return result

    _trino_compat_get_columns._dbgpt_trino_patched = True
    HiveDialect.get_columns = _trino_compat_get_columns

    # Also patch get_indexes: pyhive uses the same 3-tuple unpacking on
    # DESCRIBE rows, which breaks on Trino's 4-column output.  Trino has
    # no Hive-style partitions, so we short-circuit to an empty list when
    # running in Trino mode (detected via the double-quote preparer).
    _orig_get_indexes = HiveDialect.get_indexes

    def _trino_compat_get_indexes(
        self, connection, table_name, schema=None, **kw
    ):
        preparer = getattr(self, "identifier_preparer", None)
        initial_quote = getattr(preparer, "initial_quote", "`")
        if initial_quote != '"':
            # Plain Hive/Spark — use original implementation.
            return _orig_get_indexes(self, connection, table_name, schema, **kw)
        # Trino has no Hive-style partition indexes.
        return []

    _trino_compat_get_indexes._dbgpt_trino_patched = True
    HiveDialect.get_indexes = _trino_compat_get_indexes


_patch_pyhive_for_trino()
_patch_pyhive_get_columns_for_trino()


@auto_register_resource(
    label=_("Apache Kyuubi datasource"),
    category=ResourceCategory.DATABASE,
    tags={"order": TAGS_ORDER_HIGH},
    description=_(
        "Apache Kyuubi - Multi-tenant Thrift JDBC/ODBC server for Spark & Trino."
    ),
)
@dataclass
class KyuubiParameters(HiveParameters):
    """Kyuubi connection parameters.

    Supports two connection modes:
    - Direct: single host:port (uses parent HiveConnector logic)
    - ZooKeeper: comma-separated ZK hosts for HA service discovery
    """

    __type__ = "kyuubi"

    host: str = field(
        default="localhost",
        metadata={
            "help": _(
                "Kyuubi host(s). For ZooKeeper discovery, use comma-separated "
                "ZK hosts with ports, e.g. zk1:2181,zk2:2181,zk3:2181"
            )
        },
    )
    port: int = field(
        default=10009,
        metadata={"help": _("Kyuubi server port, default 10009.")},
    )

    service_discovery_mode: str = field(
        default="",
        metadata={
            "help": _(
                "Service discovery mode, set to 'zooKeeper' when using "
                "ZooKeeper for HA discovery."
            ),
            "valid_values": ["", "zooKeeper"],
        },
    )
    zoo_keeper_namespace: str = field(
        default="",
        metadata={
            "help": _("ZooKeeper namespace for Kyuubi, e.g. 'kyuubi_adhoc'.")
        },
    )

    engine_type: str = field(
        default="",
        metadata={
            "help": _("Engine type: SPARK_SQL, TRINO, FLINK_SQL, etc."),
            "valid_values": ["", "SPARK_SQL", "TRINO", "FLINK_SQL"],
        },
    )

    def _is_zk_mode(self) -> bool:
        """Check if ZooKeeper service discovery should be used."""
        return (
            "," in self.host
            and self.service_discovery_mode == "zooKeeper"
        )

    def db_url(self, ssl: bool = False, charset: Optional[str] = None) -> str:
        """Build Kyuubi connection URL.

        In ZK mode, returns a host-less URL (actual host is resolved by
        the creator function). In direct mode, delegates to parent.
        """
        from urllib.parse import quote, quote_plus as urlquote

        if self._is_zk_mode():
            scheme = self.driver or "hive"
            url = f"{scheme}:///{self.database}"
            params = []
            if self.service_discovery_mode:
                params.append(f"serviceDiscoveryMode={self.service_discovery_mode}")
            if self.zoo_keeper_namespace:
                params.append(f"zooKeeperNamespace={self.zoo_keeper_namespace}")
            if params:
                url += "?" + "&".join(params)
            return url

        scheme = self.driver or "hive"
        if self.username and self.password:
            auth_str = f"{quote(self.username)}:{urlquote(self.password)}@"
        else:
            auth_str = ""
        return f"{scheme}://{auth_str}{self.host}:{self.port}/{self.database}"

    def engine_args(self) -> Optional[Dict[str, Any]]:
        """Get engine args.

        In ZK mode, returns a 'creator' that performs ZK service discovery
        before connecting. In direct mode, extends parent args with Kyuubi
        engine-type session configuration.
        """
        if self._is_zk_mode():
            return {"creator": self._build_zk_creator()}

        args = super().engine_args() or {}
        if self.engine_type:
            connect_args = args.setdefault("connect_args", {})
            config = connect_args.setdefault("configuration", {})
            config["kyuubi.engine.type"] = self.engine_type
        return args

    def _build_zk_creator(self):
        """Build a connection creator that does ZooKeeper service discovery.

        The returned callable will be passed to sqlalchemy.create_engine()
        as the ``creator`` argument.  When called by SQLAlchemy it:

        1. Connects to the ZooKeeper ensemble listed in ``host``
        2. Discovers an available Kyuubi server under the ZK namespace
        3. Returns a pyhive Connection to that server
        """
        # Snapshot parameters to avoid late-binding surprises.
        zk_hosts = self.host
        namespace = self.zoo_keeper_namespace or "kyuubi"
        database = self.database
        auth = self.auth or "NONE"
        username = self.username or None
        password = self.password if self.auth in ("LDAP", "CUSTOM") else None
        kerberos_service = self.kerberos_service_name
        engine_type = self.engine_type

        def creator():
            try:
                from kazoo.client import KazooClient
            except ImportError:
                raise ImportError(
                    "ZooKeeper service discovery requires the 'kazoo' package. "
                    "Install it with: pip install kazoo"
                )

            zk = KazooClient(hosts=zk_hosts)
            zk.start()
            try:
                zk_path = f"/{namespace}"
                if not zk.exists(zk_path):
                    raise RuntimeError(
                        f"ZooKeeper path '{zk_path}' does not exist. "
                        f"Check that the Kyuubi namespace is correct."
                    )

                children = zk.get_children(zk_path)
                # Kyuubi server nodes follow the naming convention:
                #   serverUri=<host>:<port>;version=...;sequence=...
                server_nodes = [c for c in children if c.startswith("serverUri=")]
                if not server_nodes:
                    raise RuntimeError(
                        f"No Kyuubi server nodes found under ZK path '{zk_path}'."
                    )

                # Pick one server (simple random load-balancing).
                import random

                picked = random.choice(server_nodes)
                # The first semicolon-delimited segment is "serverUri=host:port".
                uri_part = picked.split(";")[0]
                server_uri = uri_part.split("=", 1)[1]
                server_host, port_str = server_uri.rsplit(":", 1)
                server_port = int(port_str)

                logger.info(
                    "Kyuubi ZK discovery: ensemble=%s namespace=%s "
                    "-> %s:%s",
                    zk_hosts, namespace, server_host, server_port,
                )
            finally:
                zk.stop()

            from pyhive import hive

            config = {}
            if engine_type:
                config["kyuubi.engine.type"] = engine_type

            connect_kwargs: Dict[str, Any] = {
                "host": server_host,
                "port": server_port,
                "database": database,
                "auth": auth,
                "username": username,
            }
            if config:
                connect_kwargs["configuration"] = config
            if password:
                connect_kwargs["password"] = password
            if auth == "KERBEROS":
                connect_kwargs["kerberos_service_name"] = kerberos_service

            return hive.connect(**connect_kwargs)

        return creator

    def create_connector(self) -> "KyuubiConnector":
        """Create Kyuubi connector."""
        return KyuubiConnector.from_parameters(self)


class KyuubiConnector(HiveConnector):
    """Kyuubi connector.

    Extends HiveConnector with:
    - ZooKeeper service discovery for HA deployments
    - Engine-type session configuration (SPARK_SQL / TRINO / FLINK_SQL)

    When ``engine_type == "TRINO"``, identifier quoting is switched from
    Hive-style backticks (`` `name` ``) to Trino-style double quotes
    (``"name"``) so that SQLAlchemy reflection does not raise
    ``backquoted identifiers are not supported``.
    """

    db_type: str = "kyuubi"
    driver: str = "hive"
    dialect: str = "hive"

    def __init__(
        self,
        engine: Any,
        engine_type: str = "",
        **kwargs: Any,
    ) -> None:
        """Create a Kyuubi connector.

        Args:
            engine: SQLAlchemy engine to wrap.
            engine_type: Kyuubi engine type (``SPARK_SQL``, ``TRINO``,
                ``FLINK_SQL``).  When set to ``TRINO``, the dialect's
                ``identifier_preparer`` is swapped to use double quotes
                instead of backticks before any reflection runs.
        """
        # Swap the identifier preparer BEFORE super().__init__ so that the
        # reflection calls inside RDBMSConnector.__init__ (inspect(engine),
        # _sync_tables_from_db) already use double quotes.
        self._kyuubi_engine_type: str = (engine_type or "").upper()
        if self._kyuubi_engine_type == "TRINO":
            _apply_trino_identifier_preparer(engine)
            # Trino's SHOW TABLES may return objects (views, materialized
            # views, temp tables) that cannot be reflected via DESCRIBE.
            # MetaData.reflect() raises NoSuchTableError on the first
            # failure, aborting the whole connector init.  Patch it to a
            # no-op for Trino — _sync_tables_from_db() still populates
            # the table list via inspector.get_table_names(), and per-table
            # reflection happens lazily through get_columns(table_name).
            from sqlalchemy import MetaData as _MetaData

            _orig_reflect = _MetaData.reflect

            @staticmethod
            def _noop_reflect(*a, **kw):
                return None

            _MetaData.reflect = _noop_reflect
            try:
                super().__init__(engine, **kwargs)
            finally:
                _MetaData.reflect = _orig_reflect
        else:
            super().__init__(engine, **kwargs)

    @classmethod
    def param_class(cls) -> Type[KyuubiParameters]:
        """Return the parameter class."""
        return KyuubiParameters

    def get_table_comment(self, table_name: str) -> Dict:
        """Return table comment.

        For Trino engine, HiveDialect's ``get_table_comment`` does not
        return the comment, and Trino's ``information_schema.tables`` does
        not carry a ``table_comment`` column (the standard schema only has
        ``table_catalog`` / ``table_schema`` / ``table_name`` / ``table_type``).
        We therefore try ``system.metadata.table_comments`` first, then fall
        back to parsing ``SHOW CREATE TABLE`` for a Hive-style ``COMMENT '...'``
        clause. This is the path used by ``_parse_table_summary_with_metadata``
        during vectorization (``DBSchemaAssembler``), so table comments
        will be embedded into the vector store.
        """
        if self._kyuubi_engine_type != "TRINO":
            return super().get_table_comment(table_name)
        # --- Path 1: system.metadata.table_comments --------------------
        try:
            db_name = self.get_current_db_name()
            with self.session_scope() as session:
                cursor = session.execute(
                    text(
                        f"""
                        SELECT comment
                        FROM system.metadata.table_comments
                        WHERE schema_name = '{db_name}'
                          AND table_name = '{table_name}'
                        """
                    )
                )
                row = cursor.fetchone()
                if row and row[0]:
                    return {"text": row[0]}
        except Exception as e:
            logger.debug(
                "Kyuubi get_table_comment: system.metadata.table_comments "
                "not available for %s: %s",
                table_name,
                e,
            )
        # --- Path 2: parse COMMENT '...' from SHOW CREATE TABLE --------
        try:
            with self.session_scope() as session:
                cursor = session.execute(text(f"SHOW CREATE TABLE {table_name}"))
                row = cursor.fetchone()
                if row:
                    create_sql = row[0] if isinstance(row[0], str) else str(row[0])
                    import re

                    match = re.search(r"COMMENT\s+'(.*?)'", create_sql, re.DOTALL)
                    if match:
                        return {"text": match.group(1)}
        except Exception as e:
            logger.warning(
                "Kyuubi get_table_comment failed for %s: %s", table_name, e
            )
        return {"text": None}

    def get_current_db_name(self) -> str:
        """Return current database name.

        Trino does not support ``SELECT DATABASE()`` (MySQL/Hive syntax).
        Fall back to the database portion of the SQLAlchemy URL, which is
        the catalog/schema configured when the connector was built.
        """
        if self._kyuubi_engine_type != "TRINO":
            return super().get_current_db_name()
        return self._engine.url.database

    def table_simple_info(self):
        """Return table simple info for LLM fallback.

        HiveConnector returns [], but Trino supports information_schema.
        When embedding is unavailable, ChatDB falls back to this method
        to feed table schema to the LLM.

        Trino uses ``array_join(array_agg(...), ',')`` instead of
        ``group_concat``.
        """
        if self._kyuubi_engine_type != "TRINO":
            return super().table_simple_info()
        try:
            db_name = self.get_current_db_name()
            _sql = text(
                f"""
                SELECT array_join(array_agg(column_name), ',') AS columns
                FROM information_schema.columns
                WHERE table_schema = '{db_name}'
                GROUP BY table_name
                """
            )
            with self.session_scope() as session:
                cursor = session.execute(_sql)
                results = cursor.fetchall()
                return results
        except Exception as e:
            logger.warning(
                "Kyuubi table_simple_info failed: %s — returning empty list", e
            )
            return []

    @classmethod
    def from_parameters(cls, parameters: KyuubiParameters) -> "KyuubiConnector":
        """Create connector following the parent-class pattern.

        Delegates the heavy lifting to ``parameters.db_url()`` and
        ``parameters.engine_args()``, which encapsulate ZK discovery
        (via creator) when needed.
        """
        db_url = parameters.db_url()
        engine_args = parameters.engine_args() or {}
        return cls(
            create_engine(db_url, **engine_args),
            engine_type=parameters.engine_type,
        )
