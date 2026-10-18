"""SQLite storage for documents, extracted entities and review history."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from autosar_hld_assistant.app.core.config import DB_PATH


@dataclass(frozen=True)
class EntityTable:
    table: str
    label: str                       # singular, as shown in the UI and review log
    columns: tuple[str, ...]         # data columns, in display order
    defaults: dict[str, str]
    editable: tuple[str, ...]        # columns a reviewer may correct
    reviewable: bool = True


ENTITY_TABLES: dict[str, EntityTable] = {
    "swcs": EntityTable(
        "swc_entities", "SW-C", ("name", "type", "description"),
        {"type": "Application", "description": ""}, ("type", "description")),
    "interfaces": EntityTable(
        "interface_entities", "Interface", ("name", "type", "description"),
        {"type": "Sender-Receiver", "description": ""}, ("type", "description")),
    "ports": EntityTable(
        "port_entities", "Port", ("name", "direction", "swc_owner", "interface_ref"),
        {"direction": "Provided", "swc_owner": "", "interface_ref": ""},
        ("direction", "swc_owner", "interface_ref")),
    "signals": EntityTable(
        "signal_entities", "Signal", ("name", "data_type", "unit", "interface_ref"),
        {"data_type": "unknown", "unit": "-", "interface_ref": ""},
        ("data_type", "unit", "interface_ref")),
    "dependencies": EntityTable(
        "dependencies", "Dependency", ("source_swc", "target_swc", "interface_name"),
        {"interface_name": ""}, (), reviewable=False),
    "functional_flows": EntityTable(
        "functional_flows", "Functional flow", ("flow_name", "sequence", "description"),
        {"description": ""}, (), reviewable=False),
}

REVIEW_STATUSES = ("Approved", "Rejected", "Edited")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_name TEXT UNIQUE NOT NULL,
    total_pages INTEGER,
    file_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS hitl_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    entity_name TEXT NOT NULL,
    document_name TEXT,
    status TEXT NOT NULL,
    reviewer TEXT,
    rationale TEXT,
    risk_notes TEXT,
    updated_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def _entity_schema(spec: EntityTable) -> str:
    columns = ",\n    ".join(f"{c} TEXT" for c in spec.columns)
    review = ",\n    review_status TEXT DEFAULT 'Pending'" if spec.reviewable else ""
    return f"""
CREATE TABLE IF NOT EXISTS {spec.table} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_name TEXT,
    {columns},
    source TEXT DEFAULT 'regex'{review}
);
CREATE INDEX IF NOT EXISTS idx_{spec.table}_doc ON {spec.table}(document_name);
"""


class DatabaseManager:

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        with self.connect() as conn:
            conn.executescript(_SCHEMA + "".join(_entity_schema(s) for s in ENTITY_TABLES.values()))
            self._migrate(conn)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Connection that commits on success, rolls back on error, and always closes."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        """Add columns introduced after the first release to existing databases."""
        wanted = {spec.table: ("source", "TEXT DEFAULT 'regex'") for spec in ENTITY_TABLES.values()}
        for table, (column, decl) in wanted.items():
            existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
        review_cols = {row["name"] for row in conn.execute("PRAGMA table_info(hitl_reviews)")}
        for column in ("entity_id", "document_name"):
            if column not in review_cols:
                conn.execute(f"ALTER TABLE hitl_reviews ADD COLUMN {column} "
                             f"{'INTEGER' if column == 'entity_id' else 'TEXT'}")

    # ---------------------------------------------------------- documents

    def add_document(self, document_name: str, total_pages: int, file_path: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO documents (document_name, total_pages, file_path) VALUES (?, ?, ?)",
                (document_name, total_pages, file_path),
            )

    def has_document(self, document_name: str) -> bool:
        with self.connect() as conn:
            row = conn.execute("SELECT 1 FROM documents WHERE document_name = ?", (document_name,)).fetchone()
        return row is not None

    def list_documents(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM documents ORDER BY created_at, id").fetchall()
        return [dict(r) for r in rows]

    def delete_document(self, document_name: str) -> None:
        """Remove a document and its entities. Review history is kept."""
        with self.connect() as conn:
            for spec in ENTITY_TABLES.values():
                conn.execute(f"DELETE FROM {spec.table} WHERE document_name = ?", (document_name,))
            conn.execute("DELETE FROM documents WHERE document_name = ?", (document_name,))

    # ----------------------------------------------------------- entities

    def save_extracted_entities(self, extracted: dict[str, Any]) -> None:
        document_name = extracted["document_name"]
        with self.connect() as conn:
            for kind, spec in ENTITY_TABLES.items():
                cols = ("document_name", *spec.columns, "source")
                sql = f"INSERT INTO {spec.table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})"
                for item in extracted.get(kind, []):
                    values = [document_name]
                    for c in spec.columns:
                        value = item.get(c) or spec.defaults.get(c, "")
                        values.append(", ".join(value) if isinstance(value, list) else str(value))
                    values.append(item.get("source", "regex"))
                    conn.execute(sql, values)

    def get_entities(self, kind: str, document_name: str | None = None) -> list[dict[str, Any]]:
        spec = ENTITY_TABLES[kind]
        sql = f"SELECT * FROM {spec.table}"
        params: tuple = ()
        if document_name:
            sql += " WHERE document_name = ?"
            params = (document_name,)
        with self.connect() as conn:
            rows = conn.execute(sql + " ORDER BY id", params).fetchall()
        return [dict(r) for r in rows]

    def get_entity(self, kind: str, entity_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(f"SELECT * FROM {ENTITY_TABLES[kind].table} WHERE id = ?", (entity_id,)).fetchone()
        return dict(row) if row else None

    def count_entities(self, document_name: str | None = None) -> dict[str, int]:
        return {kind: len(self.get_entities(kind, document_name)) for kind in ENTITY_TABLES}

    def update_entity(self, kind: str, entity_id: int, changes: dict[str, str],
                      conn: sqlite3.Connection | None = None) -> None:
        spec = ENTITY_TABLES[kind]
        unknown = set(changes) - set(spec.editable) - {"review_status"}
        if unknown:
            raise ValueError(f"Not editable for {spec.label}: {', '.join(sorted(unknown))}")
        if not changes:
            return
        assignments = ", ".join(f"{c} = ?" for c in changes)
        sql = f"UPDATE {spec.table} SET {assignments} WHERE id = ?"
        params = (*changes.values(), entity_id)
        if conn is not None:
            conn.execute(sql, params)
        else:
            with self.connect() as own:
                own.execute(sql, params)

    # -------------------------------------------------------------- reset

    def clear_all(self, include_reviews: bool = False) -> None:
        """Delete all documents and entities; the review log only if asked."""
        with self.connect() as conn:
            for spec in ENTITY_TABLES.values():
                conn.execute(f"DELETE FROM {spec.table}")
            conn.execute("DELETE FROM documents")
            if include_reviews:
                conn.execute("DELETE FROM hitl_reviews")
