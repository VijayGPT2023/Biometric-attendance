"""
Database abstraction layer - supports both SQLite (local) and PostgreSQL (production).
Uses DATABASE_URL env var to decide: if set, uses PostgreSQL; otherwise SQLite.
"""
import os
import re
import sqlite3
import logging

logger = logging.getLogger(__name__)

# Try importing psycopg2 for PostgreSQL support
try:
    import psycopg2
    import psycopg2.extras
    HAS_PG = True
except ImportError:
    HAS_PG = False

# Unified IntegrityError
if HAS_PG:
    from psycopg2 import IntegrityError
else:
    from sqlite3 import IntegrityError


def is_postgres():
    return bool(os.environ.get('DATABASE_URL'))


# ================================================================
#  DictRow - mimics sqlite3.Row for PostgreSQL results
# ================================================================

class DictRow:
    """Row object that supports both dict-style and index-style access."""
    def __init__(self, data):
        if isinstance(data, dict):
            self._dict = data
            self._keys = list(data.keys())
            self._values = list(data.values())
        else:
            self._dict = dict(data)
            self._keys = list(self._dict.keys())
            self._values = list(self._dict.values())

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._dict[key]

    def __contains__(self, key):
        return key in self._dict

    def keys(self):
        return self._keys

    def __len__(self):
        return len(self._keys)

    def __iter__(self):
        return iter(self._values)

    def __repr__(self):
        return f"DictRow({self._dict})"

    def get(self, key, default=None):
        return self._dict.get(key, default)


# ================================================================
#  SQL Translation (SQLite -> PostgreSQL)
# ================================================================

def translate_sql(sql):
    """Translate SQLite SQL to PostgreSQL SQL."""
    # Replace ? placeholders with %s
    result = re.sub(r'\?', '%s', sql)
    # INSERT OR IGNORE -> INSERT ... ON CONFLICT DO NOTHING
    result = re.sub(
        r'INSERT\s+OR\s+IGNORE\s+INTO',
        'INSERT INTO',
        result,
        flags=re.IGNORECASE
    )
    # Add ON CONFLICT DO NOTHING for INSERT OR IGNORE
    if 'INSERT OR IGNORE' in sql.upper():
        # Find the VALUES(...) part and append ON CONFLICT DO NOTHING
        if 'ON CONFLICT' not in result.upper():
            result = result.rstrip().rstrip(';') + ' ON CONFLICT DO NOTHING'
    return result


def translate_ddl(sql):
    """Translate SQLite DDL to PostgreSQL DDL."""
    result = sql
    # AUTOINCREMENT -> use SERIAL
    result = re.sub(
        r'INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT',
        'SERIAL PRIMARY KEY',
        result,
        flags=re.IGNORECASE
    )
    # Remove IF NOT EXISTS for sequences (PostgreSQL handles SERIAL automatically)
    # PRAGMA statements -> skip
    return result


# ================================================================
#  PostgreSQL Connection Wrapper
# ================================================================

class PgConnection:
    """Wraps psycopg2 connection to behave like sqlite3 connection."""

    def __init__(self, conn):
        self._conn = conn
        self._conn.autocommit = False

    def execute(self, sql, params=None):
        sql_pg = translate_sql(sql)
        cursor = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cursor.execute(sql_pg, params or ())
        except Exception as e:
            logger.error(f"SQL Error: {e}\nQuery: {sql_pg}\nParams: {params}")
            raise
        return PgCursor(cursor)

    def executescript(self, script):
        """Execute multiple SQL statements (used for DDL)."""
        statements = [s.strip() for s in script.split(';') if s.strip()]
        cursor = self._conn.cursor()
        for stmt in statements:
            if not stmt:
                continue
            # Skip PRAGMA statements
            if stmt.strip().upper().startswith('PRAGMA'):
                continue
            pg_stmt = translate_ddl(translate_sql(stmt))
            try:
                cursor.execute(pg_stmt)
            except Exception as e:
                logger.error(f"DDL Error: {e}\nStatement: {pg_stmt}")
                self._conn.rollback()
                raise
        self._conn.commit()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def get_columns(self, table_name):
        """Get column names for a table (replaces PRAGMA table_info)."""
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
            (table_name,))
        return [row[0] for row in cursor.fetchall()]


class PgCursor:
    """Wraps psycopg2 cursor to return DictRow objects."""

    def __init__(self, cursor):
        self._cursor = cursor

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        return DictRow(row)

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [DictRow(r) for r in rows]

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    @property
    def rowcount(self):
        return self._cursor.rowcount


# ================================================================
#  Unified get_db / init_db
# ================================================================

def get_db(app, g):
    """Get database connection. Uses PostgreSQL if DATABASE_URL is set."""
    if 'db' not in g:
        db_url = os.environ.get('DATABASE_URL')
        if db_url and HAS_PG:
            conn = psycopg2.connect(db_url)
            g.db = PgConnection(conn)
            logger.debug("Connected to PostgreSQL")
        else:
            db_path = app.config.get('DATABASE', 'biometric.db')
            g.db = sqlite3.connect(db_path)
            g.db.row_factory = sqlite3.Row
            g.db.execute('PRAGMA foreign_keys = ON')
            logger.debug(f"Connected to SQLite: {db_path}")
    return g.db


def close_db(g):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def get_table_columns(db, table_name):
    """Get column names for a table. Works with both SQLite and PostgreSQL."""
    if isinstance(db, PgConnection):
        return db.get_columns(table_name)
    else:
        return [r[1] for r in db.execute(f'PRAGMA table_info({table_name})').fetchall()]
