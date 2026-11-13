"""The agent's database: one of BIRD's SQLite files, opened read-only, reads only, with a timeout.

An authorizer allows plain reads and a few schema pragmas and denies everything else
(writes, ATTACH, other pragmas). The grader uses the same connection type.
"""

import sqlite3
import time

from .config import CHAR_CAP, ROW_CAP, SQL_TIMEOUT_S, db_path

ALLOWED = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}
SCHEMA_PRAGMAS = {"table_info", "table_xinfo", "foreign_key_list", "index_list", "index_info"}


def authorize(action, arg1, arg2, db_name, trigger):
    if action in ALLOWED or (action == sqlite3.SQLITE_PRAGMA and (arg1 or "").lower() in SCHEMA_PRAGMAS):
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def cell(v):
    return "NULL" if v is None else str(v)


class DB:
    def __init__(self, db):
        self.con = sqlite3.connect(f"file:{db_path(db)}?mode=ro", uri=True, check_same_thread=False)
        self.con.set_authorizer(authorize)

    def query(self, sql, max_rows=None):
        """Return (columns, rows, truncated). All rows when max_rows is None. Stops after SQL_TIMEOUT_S."""
        deadline = time.monotonic() + SQL_TIMEOUT_S
        self.con.set_progress_handler(lambda: time.monotonic() > deadline, 10_000)
        try:
            cur = self.con.execute(sql)
            rows = cur.fetchall() if max_rows is None else cur.fetchmany(max_rows + 1)
            columns = [d[0] for d in cur.description or []]
        finally:
            self.con.set_progress_handler(None, 0)
        if max_rows is None:
            return columns, rows, False
        return columns, rows[:max_rows], len(rows) > max_rows

    def schema(self):
        """The CREATE TABLE statements, verbatim."""
        rows = self.con.execute("SELECT sql FROM sqlite_master WHERE type = 'table' ORDER BY name").fetchall()
        return "\n\n".join(r[0].strip() for r in rows)

    def run_sql(self, sql):
        """Tool body: a capped text table for the model, plus timing and any error."""
        start = time.perf_counter()
        try:
            columns, rows, truncated = self.query(sql, ROW_CAP)
        except Exception as e:
            msg = str(e).strip().splitlines()[0][:500] if str(e).strip() else e.__class__.__name__
            if msg == "interrupted":
                msg = f"query interrupted after {SQL_TIMEOUT_S} s"
            return {"ok": False, "text": f"ERROR: {msg}", "error": msg,
                    "elapsed_s": round(time.perf_counter() - start, 3)}
        text = "\n".join([" | ".join(columns)] + [" | ".join(cell(v) for v in r) for r in rows])
        if len(text) > CHAR_CAP:
            text = text[:CHAR_CAP] + "\n... (output truncated)"
        text += f"\n({len(rows)} rows{', more rows not shown' if truncated else ''})"
        return {"ok": True, "text": text, "elapsed_s": round(time.perf_counter() - start, 3)}
