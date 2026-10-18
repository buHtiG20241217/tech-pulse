"""Architecture report exports: Markdown, JSON and CSV (zipped)."""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import asdict
from datetime import datetime, timezone

import pandas as pd

from autosar_hld_assistant.app.analysis.consistency import check_document
from autosar_hld_assistant.app.storage.db import ENTITY_TABLES, DatabaseManager
from autosar_hld_assistant.app.storage.hitl_store import HITLReviewManager

_REPORT_SECTIONS = [
    ("swcs", "Software components", ["name", "type", "description", "review_status", "document_name"]),
    ("interfaces", "Port interfaces", ["name", "type", "review_status", "document_name"]),
    ("ports", "Ports", ["swc_owner", "name", "direction", "interface_ref", "review_status"]),
    ("signals", "Signals", ["name", "data_type", "unit", "interface_ref", "review_status"]),
    ("dependencies", "Dependencies", ["source_swc", "interface_name", "target_swc"]),
    ("functional_flows", "Functional flows", ["flow_name", "sequence"]),
]
_REVIEW_COLUMNS = ["created_at", "entity_type", "entity_name", "status", "reviewer", "rationale", "risk_notes"]


def _md_cell(value) -> str:
    return str(value if value not in (None, "") else "-").replace("|", "\\|").replace("\n", " ")


def _md_table(rows: list[dict], columns: list[str]) -> list[str]:
    if not rows:
        return ["_None._"]
    header = "| " + " | ".join(c.replace("_", " ").capitalize() for c in columns) + " |"
    lines = [header, "|" + "---|" * len(columns)]
    lines += ["| " + " | ".join(_md_cell(r.get(c)) for c in columns) + " |" for r in rows]
    return lines


class ArchitectureReportExporter:

    def __init__(self, db_manager: DatabaseManager | None = None, hitl_manager: HITLReviewManager | None = None):
        self.db = db_manager or DatabaseManager()
        self.hitl = hitl_manager or HITLReviewManager(self.db)

    def _tables(self) -> dict[str, list[dict]]:
        tables = {kind: self.db.get_entities(kind) for kind in ENTITY_TABLES}
        tables["consistency_findings"] = self._findings()
        tables["hitl_reviews"] = self.hitl.get_all_reviews()
        return tables

    def generate_markdown_report(self) -> str:
        tables = self._tables()
        documents = self.db.list_documents()
        generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines = [
            "# AUTOSAR HLD Architecture Report",
            "",
            f"Generated {generated} from: "
            + (", ".join(d["document_name"] for d in documents) or "no documents") + ".",
            "",
            "## Summary",
            "",
            "| Element | Count | Approved | Rejected | Edited | Pending |",
            "|---|---|---|---|---|---|",
        ]
        for kind, title, _ in _REPORT_SECTIONS:
            rows = tables[kind]
            if ENTITY_TABLES[kind].reviewable:
                counts = [sum(1 for r in rows if r.get("review_status") == s)
                          for s in ("Approved", "Rejected", "Edited", "Pending")]
                lines.append(f"| {title} | {len(rows)} | " + " | ".join(map(str, counts)) + " |")
            else:
                lines.append(f"| {title} | {len(rows)} | - | - | - | - |")

        for number, (kind, title, columns) in enumerate(_REPORT_SECTIONS, start=1):
            lines += ["", f"## {number}. {title}", ""] + _md_table(tables[kind], columns)

        lines += ["", f"## {len(_REPORT_SECTIONS) + 1}. Consistency checks", ""]
        lines += _md_table(self._findings(documents), ["document", "severity", "check", "element", "message"])
        lines += ["", f"## {len(_REPORT_SECTIONS) + 2}. Review log", ""]
        lines += _md_table(tables["hitl_reviews"], _REVIEW_COLUMNS)
        return "\n".join(lines) + "\n"

    def _findings(self, documents: list[dict] | None = None) -> list[dict]:
        documents = documents if documents is not None else self.db.list_documents()
        return [{"document": d["document_name"], **asdict(f)}
                for d in documents for f in check_document(self.db, d["document_name"])]

    def generate_json_export(self) -> str:
        return json.dumps({"documents": self.db.list_documents(), **self._tables()}, indent=2, default=str)

    def generate_csv_exports(self) -> dict[str, str]:
        return {name: pd.DataFrame(rows).to_csv(index=False) for name, rows in self._tables().items()}

    def generate_csv_zip(self) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, csv in self.generate_csv_exports().items():
                archive.writestr(f"{name}.csv", csv)
        return buffer.getvalue()
