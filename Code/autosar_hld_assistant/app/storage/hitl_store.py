"""Human review of extracted entities, with an append-only audit log."""

from __future__ import annotations

import json
from typing import Any

from autosar_hld_assistant.app.storage.db import ENTITY_TABLES, REVIEW_STATUSES, DatabaseManager


class ReviewError(ValueError):
    """A review decision was rejected (missing rationale, no edits, unknown entity...)."""


def entity_label(kind: str, entity: dict[str, Any]) -> str:
    """Human-readable name; ports are qualified by their owner because names repeat."""
    if kind == "ports" and entity.get("swc_owner"):
        return f"{entity['swc_owner']}.{entity['name']}"
    return entity.get("name") or entity.get("flow_name") or str(entity.get("id"))


class HITLReviewManager:

    def __init__(self, db_manager: DatabaseManager | None = None):
        self.db = db_manager or DatabaseManager()

    def log_review(
        self,
        kind: str,
        entity_id: int,
        status: str,
        reviewer: str,
        rationale: str,
        risk_notes: str = "",
        corrections: dict[str, str] | None = None,
    ) -> None:
        """Record a decision on one entity and update its review status.

        For status "Edited", `corrections` holds the changed fields; they are
        applied to the entity and stored in the log together with the old
        values.
        """
        spec = ENTITY_TABLES.get(kind)
        if spec is None or not spec.reviewable:
            raise ReviewError(f"{kind} entities cannot be reviewed.")
        if status not in REVIEW_STATUSES:
            raise ReviewError(f"Unknown status '{status}'.")
        if not reviewer.strip():
            raise ReviewError("Enter the reviewer's name.")
        if not rationale.strip():
            raise ReviewError("Give a rationale for the decision.")

        entity = self.db.get_entity(kind, entity_id)
        if entity is None:
            raise ReviewError("That entity no longer exists. Reload the page.")

        changes = {
            field: value.strip() for field, value in (corrections or {}).items()
            if field in spec.editable and value.strip() != (entity.get(field) or "")
        }
        if status == "Edited" and not changes:
            raise ReviewError("Change at least one field, or choose Approved / Rejected.")
        if status != "Edited":
            changes = {}

        updated_data = {f: {"old": entity.get(f), "new": v} for f, v in changes.items()}
        with self.db.connect() as conn:
            conn.execute(
                """INSERT INTO hitl_reviews (entity_type, entity_id, entity_name, document_name, status,
                                             reviewer, rationale, risk_notes, updated_data)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (spec.label, entity_id, entity_label(kind, entity), entity.get("document_name"), status,
                 reviewer.strip(), rationale.strip(), risk_notes.strip(), json.dumps(updated_data)),
            )
            self.db.update_entity(kind, entity_id, {**changes, "review_status": status}, conn=conn)

    def get_all_reviews(self) -> list[dict[str, Any]]:
        """Audit log, newest first."""
        with self.db.connect() as conn:
            rows = conn.execute("SELECT * FROM hitl_reviews ORDER BY created_at DESC, id DESC").fetchall()
        return [dict(r) for r in rows]
