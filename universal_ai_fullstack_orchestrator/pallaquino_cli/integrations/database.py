"""Database adapter: authorized, read-only inspection of SQLite databases inside the workspace.

Read-only is enforced three times: the file is opened with `mode=ro`, `PRAGMA query_only` is set, and an
authorizer allows only reads (no INSERT/UPDATE/DELETE/DDL/ATTACH/PRAGMA writes), so a query that looks like a read
but writes is refused by SQLite itself. A progress handler enforces the deadline and the cancel signal. Write
connections, migrations and other engines (PostgreSQL, MySQL/MariaDB) are not part of 0.5.0: `DatabaseAdapter`
is the extension point a DATABASE_CONNECTOR plugin implements.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any, Protocol

from ..tools.contracts import new_tool
from ..tools.registry import ToolContext, tool_result
from .filesystem import PATH, confine

SOURCE = {"kind": "builtin", "id": "core.sqlite", "trust": "builtin"}
ALLOWED_ACTIONS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, getattr(sqlite3, "SQLITE_RECURSIVE", 33)}
READ_PRAGMAS = {"table_info", "table_xinfo", "index_list", "index_info", "foreign_key_list", "query_only"}
SQLITE_SUFFIXES = {".db", ".sqlite", ".sqlite3"}


class DatabaseAdapter(Protocol):
    """Contract for database connectors: separate read connections, explicit write paths (governed)."""

    def test_connection(self) -> dict[str, Any]: ...
    def tables(self) -> list[str]: ...
    def schema(self, table: str | None = None) -> dict[str, Any]: ...
    def query_read_only(self, sql: str, params: list[Any], max_rows: int) -> dict[str, Any]: ...


class SqliteReadOnly:
    def __init__(self, path: Path, *, deadline: float | None = None, cancel: Any = None):
        if path.suffix.lower() not in SQLITE_SUFFIXES: raise PermissionError(f"{path.name} is not a SQLite database file ({sorted(SQLITE_SUFFIXES)})")
        if not path.is_file(): raise FileNotFoundError(f"{path.name} does not exist")
        self.conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, timeout=5, check_same_thread=False)
        self.conn.execute("PRAGMA query_only = ON")
        self.conn.set_authorizer(self._authorize)
        self.conn.set_progress_handler(lambda: int(bool((deadline and time.monotonic() > deadline) or (cancel is not None and cancel.is_set()))), 1000)

    @staticmethod
    def _authorize(action: int, arg1: Any, arg2: Any, db: Any, trigger: Any) -> int:
        if action in ALLOWED_ACTIONS: return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_PRAGMA and arg1 in READ_PRAGMAS - {"query_only"}: return sqlite3.SQLITE_OK  # introspection pragmas only
        return sqlite3.SQLITE_DENY

    def close(self) -> None:
        self.conn.close()

    def test_connection(self) -> dict[str, Any]:
        return {"ok": self.conn.execute("SELECT 1").fetchone()[0] == 1, "sqlite_version": sqlite3.sqlite_version}

    def tables(self) -> list[str]:
        return [r[0] for r in self.conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY name")]

    def schema(self, table: str | None = None) -> dict[str, Any]:
        names = [table] if table else self.tables(); known = set(self.tables()); result = {}
        for name in names:
            if name not in known: raise LookupError(f"table {name!r} does not exist")
            columns = [{"name": r[1], "type": r[2], "not_null": bool(r[3]), "primary_key": bool(r[5])} for r in self.conn.execute(f"PRAGMA table_info({_quote(name)})")]
            sql = self.conn.execute("SELECT sql FROM sqlite_master WHERE name=?", (name,)).fetchone()
            result[name] = {"columns": columns, "ddl": sql[0] if sql else None}
        return result

    def query_read_only(self, sql: str, params: list[Any], max_rows: int) -> dict[str, Any]:
        try: cursor = self.conn.execute(sql, params)
        except sqlite3.DatabaseError as exc:
            if "not authorized" in str(exc) or "readonly" in str(exc).lower(): raise PermissionError(f"query refused by the read-only policy: {exc}") from None
            if "interrupted" in str(exc): raise TimeoutError("query exceeded its deadline or was cancelled") from None
            raise
        columns = [d[0] for d in cursor.description or []]; rows = cursor.fetchmany(max_rows + 1)
        return {"columns": columns, "rows": [list(r) for r in rows[:max_rows]], "truncated": len(rows) > max_rows}


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _open(args: dict[str, Any], ctx: ToolContext) -> SqliteReadOnly:
    return SqliteReadOnly(confine(ctx.workspace, args["database"]), deadline=ctx.deadline, cancel=ctx.cancel)


def _with_db(work):
    def run(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        db = _open(args, ctx)
        try: return work(db, args)
        finally: db.close()
    return run


def tools() -> list[tuple[dict[str, Any], Any]]:
    obj = lambda props, required=(): {"type": "object", "additionalProperties": False, "properties": props, "required": list(required)}
    read = dict(source=SOURCE, capabilities=["DATABASE_READ"], operation="READ_ONLY")
    return [
        (new_tool("core.sqlite.test_connection", description="Open a workspace SQLite database read-only and check it answers.", input_schema=obj({"database": PATH}, ["database"]), **read),
         _with_db(lambda db, a: tool_result(text="connection ok", structured=db.test_connection()))),
        (new_tool("core.sqlite.tables", description="List tables and views.", input_schema=obj({"database": PATH}, ["database"]), **read),
         _with_db(lambda db, a: tool_result(text=", ".join(db.tables()) or "no tables", structured={"tables": db.tables()}))),
        (new_tool("core.sqlite.schema", description="Columns and DDL of one table or all tables.", input_schema=obj({"database": PATH, "table": {"type": "string", "maxLength": 200}}, ["database"]), **read),
         _with_db(lambda db, a: tool_result(text="schema", structured=db.schema(a.get("table"))))),
        (new_tool("core.sqlite.query", description="Run one read-only SQL statement with bound parameters.", provides=["sql_read"], input_schema=obj({
            "database": PATH, "sql": {"type": "string", "minLength": 1, "maxLength": 20_000}, "params": {"type": "array", "maxItems": 100},
            "max_rows": {"type": "integer", "minimum": 1, "maximum": 1000}}, ["database", "sql"]), **read),
         _with_db(lambda db, a: (lambda r: tool_result(text=f"{len(r['rows'])} rows" + (" (truncated)" if r["truncated"] else ""), structured=r))(
             db.query_read_only(a["sql"], a.get("params", []), a.get("max_rows", 200))))),
    ]
