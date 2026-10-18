"""Revision comparison: what changed between two indexed documents."""

from __future__ import annotations

from dataclasses import dataclass, field

from autosar_hld_assistant.app.storage.db import ENTITY_TABLES, DatabaseManager

# How an element is identified across revisions.
IDENTITY = {
    "swcs": ("name",),
    "interfaces": ("name",),
    "ports": ("swc_owner", "name"),
    "signals": ("name",),
    "dependencies": ("source_swc", "target_swc", "interface_name"),
    "functional_flows": ("flow_name",),
}


@dataclass
class Change:
    element: str
    field: str
    old: str
    new: str


@dataclass
class KindDiff:
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    changed: list[Change] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.added or self.removed or self.changed)


def _index(rows: list[dict], kind: str) -> dict[str, dict]:
    keys = IDENTITY[kind]
    sep = "." if kind == "ports" else " -> " if kind == "dependencies" else " "
    return {sep.join(str(r.get(k) or "") for k in keys): r for r in rows}


def compare_rows(kind: str, old_rows: list[dict], new_rows: list[dict]) -> KindDiff:
    old, new = _index(old_rows, kind), _index(new_rows, kind)
    compared = [c for c in ENTITY_TABLES[kind].columns if c not in IDENTITY[kind]]
    diff = KindDiff(added=sorted(set(new) - set(old)), removed=sorted(set(old) - set(new)))
    for key in sorted(set(old) & set(new)):
        for column in compared:
            before, after = old[key].get(column) or "", new[key].get(column) or ""
            if before != after:
                diff.changed.append(Change(key, column, before, after))
    return diff


def compare_documents(db: DatabaseManager, old_document: str, new_document: str) -> dict[str, KindDiff]:
    return {
        kind: compare_rows(kind, db.get_entities(kind, old_document), db.get_entities(kind, new_document))
        for kind in ENTITY_TABLES
    }
