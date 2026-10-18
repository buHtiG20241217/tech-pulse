"""Extracts AUTOSAR architecture elements from HLD text.

Three passes, each refining the previous one:
1. Naming-convention regexes (works on loosely written documents).
2. Table-row parsers (authoritative when the HLD uses ID-numbered tables).
3. LLM pass (when a model is configured) that fills missing attributes, and
   adds elements only for kinds the document has no table for; anything it
   adds is marked source="llm" so a reviewer can tell it apart.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Iterable

from autosar_hld_assistant.app.core.config import LLM_EXTRACTION_CHARS
from autosar_hld_assistant.app.core.llm import LLMClient, LLMError

log = logging.getLogger(__name__)

ENTITY_KINDS = ("swcs", "interfaces", "ports", "signals", "dependencies", "functional_flows")

# AUTOSAR Basic Software modules: never application SW-Cs, interfaces or signals.
BSW_MODULES = {
    "CanIf", "LinIf", "FrIf", "EthIf", "PduR", "Com", "ComM", "CanSM", "CanTp",
    "CanNm", "Dcm", "Dem", "NvM", "MemIf", "Fee", "Eep", "EcuM", "BswM",
    "Rte", "Os", "WdgM", "WdgIf", "Det", "SchM", "IoHwAb", "Dio", "Adc", "Pwm",
    "Can", "Lin", "Fr", "Spi", "Mcu", "Port", "Gpt", "Icu", "Xcp", "SoAd",
}
_BSW_LOWER = {m.lower() for m in BSW_MODULES}

# Names with a signal-like suffix that are really ports, events or operations.
SIGNAL_EXCLUDE_PREFIXES = ("PP_", "RP_", "P_", "R_", "EVT_")
_OPERATION_NAME = re.compile(r"^(Get|Set)[A-Z_]")

# Keys used to recognise the same element across passes.
MERGE_KEYS: dict[str, tuple[str, ...]] = {
    "swcs": ("name",),
    "interfaces": ("name",),
    "ports": ("swc_owner", "name"),  # RP_DiagEvent exists on five SW-Cs
    "signals": ("name",),
    "dependencies": ("source_swc", "interface_name", "target_swc"),
    "functional_flows": ("flow_name",),
}

# Placeholder values written by the regex pass; the LLM may replace them.
_PLACEHOLDERS = {"", "-", "unknown", "Extracted SW-C", "Extracted_If"}

LLM_SYSTEM_PROMPT = """You extract software architecture elements from AUTOSAR High-Level Design documents.

Return a JSON object with exactly these keys, each holding a list of objects:
- "swcs": {"name", "type", "description"}
- "interfaces": {"name", "type" ("Sender-Receiver" or "Client-Server"), "description"}
- "ports": {"name", "direction" ("Provided" or "Required"), "swc_owner", "interface_ref"}
- "signals": {"name", "data_type", "unit", "interface_ref"}
- "dependencies": {"source_swc", "target_swc", "interface_name"}
- "functional_flows": {"flow_name", "sequence", "description"}

Copy names exactly as written in the text. Include only elements that appear in the text.
List each element once. Keep every description under 12 words.
A functional flow "sequence" is a chain of component names such as "A -> B -> C".
Do not list AUTOSAR Basic Software modules such as CanIf, PduR, Com, NvM, Dem or Rte."""


def is_bsw(name: str) -> bool:
    return name.lower() in _BSW_LOWER


def is_valid_signal(name: str) -> bool:
    return not (
        name.startswith(SIGNAL_EXCLUDE_PREFIXES) or _OPERATION_NAME.match(name) or is_bsw(name)
    )


def merge_entities(
    base: list[dict[str, Any]],
    extra: Iterable[dict[str, Any]],
    key: tuple[str, ...],
    fill_only: bool = False,
    add_new: bool = True,
) -> list[dict[str, Any]]:
    """Merge `extra` into `base` by `key`.

    With fill_only=False, fields from `extra` overwrite. With fill_only=True,
    `extra` only fills fields that are missing or hold a placeholder.
    With add_new=False, items of `extra` not already in `base` are dropped.
    Items lacking any key field are skipped.
    """
    def key_of(item: dict[str, Any]):
        return tuple(item[f] for f in key) if all(item.get(f) for f in key) else None

    merged: dict[tuple, dict[str, Any]] = {}
    for item in base:
        k = key_of(item)
        if k is not None:
            merged[k] = dict(item)
    for item in extra:
        k = key_of(item)
        if k is None:
            continue
        if k not in merged:
            if add_new:
                merged[k] = dict(item)
        elif fill_only:
            target = merged[k]
            for field, value in item.items():
                current = target.get(field)
                is_gap = current is None or (isinstance(current, str) and current in _PLACEHOLDERS)
                if is_gap and value not in (None, ""):
                    target[field] = value
        else:
            merged[k].update(item)
    return list(merged.values())


class AUTOSAREntityExtractor:

    def extract_all(self, text: str, document_name: str, llm: LLMClient | None = None) -> dict[str, Any]:
        """Extract all element kinds from `text`.

        Pass a configured `llm` to enable the LLM pass; without one, extraction
        is fully deterministic.
        """
        text = text.replace("→", "->")
        found = {
            "swcs": self._swcs_regex(text),
            "interfaces": self._interfaces_regex(text),
            "ports": self._ports_regex(text),
            "signals": self._signals_regex(text),
            "dependencies": self._dependencies_regex(text),
            "functional_flows": self._flows_regex(text),
        }

        # Table rows are authoritative: when a document has a definition table
        # for an element kind, the table replaces the name-based guesses. That
        # is what makes "depends on an undefined SW-C" detectable later.
        # ID-numbered rows (SWC-01, P-01, ...) are tried first, plain rows second.
        tables = {
            "swcs": self._swcs_from_tables(text) or self._swcs_from_plain_rows(text),
            "interfaces": self._interfaces_from_tables(text),
            "ports": self._ports_from_tables(text) or self._ports_from_plain_rows(text),
            "signals": self._signals_from_tables(text) or self._signals_from_plain_rows(text),
            "dependencies": self._dependencies_from_tables(text),
            "functional_flows": self._flows_from_headings(text),
        }
        for kind, rows in tables.items():
            if rows:
                found[kind] = rows

        if llm is not None and llm.is_configured():
            # Where the document has a table for a kind, the table is the complete
            # list: the model may fill gaps in those rows but not add new elements.
            for kind, items in self._llm_pass(text, document_name, llm).items():
                found[kind] = merge_entities(found[kind], items, MERGE_KEYS[kind],
                                             fill_only=True, add_new=not tables[kind])
            found["functional_flows"] = dedupe_flows(found["functional_flows"])

        # Final filters also apply to anything the LLM proposed.
        found["swcs"] = [s for s in found["swcs"] if not is_bsw(s["name"])]
        found["interfaces"] = [i for i in found["interfaces"] if not is_bsw(i["name"])]
        port_names = {p["name"] for p in found["ports"]}
        found["signals"] = [
            s for s in found["signals"] if is_valid_signal(s["name"]) and s["name"] not in port_names
        ]

        result: dict[str, Any] = {"document_name": document_name}
        for kind in ENTITY_KINDS:
            result[kind] = [{**item, "document_name": document_name} for item in found[kind]]
        return result

    # ------------------------------------------------------------ regex pass

    @staticmethod
    def _swcs_regex(text: str) -> list[dict[str, Any]]:
        # Case-sensitive on purpose: with IGNORECASE any word ending in
        # "component" matched.
        names = set(re.findall(r"\b([A-Z][A-Za-z0-9_]*(?:SWC|_SWC|Component))\b", text))
        out = []
        for name in sorted(n for n in names if not is_bsw(n)):
            if "Sensor" in name or "Actuator" in name:
                kind = "Sensor/Actuator"
            elif "Service" in name or "Manager" in name:
                kind = "Service Component"
            else:
                kind = "Application"
            out.append({"name": name, "type": kind, "description": "", "source": "regex"})
        return out

    @staticmethod
    def _interfaces_regex(text: str) -> list[dict[str, Any]]:
        names = set(re.findall(r"\b([A-Z][A-Za-z0-9_]*(?:_If|_Interface|If))\b", text))
        out = []
        for name in sorted(n for n in names if not is_bsw(n)):
            kind = "Client-Server" if any(w in name for w in ("Control", "Cmd", "Service")) else "Sender-Receiver"
            out.append({"name": name, "type": kind, "description": "", "source": "regex"})
        return out

    @staticmethod
    def _ports_regex(text: str) -> list[dict[str, Any]]:
        names = set(re.findall(r"\b((?:PP|RP|P|R)_[A-Za-z0-9_]+)\b", text))
        out = []
        for name in sorted(names):
            base = re.sub(r"^(?:PP|RP|P|R)_", "", name)
            out.append({
                "name": name,
                "direction": "Provided" if name.startswith(("PP_", "P_")) else "Required",
                "swc_owner": "unknown",
                "interface_ref": base + "_If",
                "source": "regex",
            })
        return out

    @staticmethod
    def _signals_regex(text: str) -> list[dict[str, Any]]:
        names = set(re.findall(
            r"\b([A-Z][A-Za-z0-9_]*(?:Speed|Pressure|Temp|Val|Cmd|Flag|Sig|Status))\b", text))
        out = []
        for name in sorted(n for n in names if is_valid_signal(n)):
            if "Flag" in name or "Status" in name:
                data_type = "boolean"
            elif "Speed" in name or "Pressure" in name:
                data_type = "float32"
            else:
                data_type = "unknown"
            unit = "km/h" if "Speed" in name else ("kPa" if "Pressure" in name else "-")
            out.append({"name": name, "data_type": data_type, "unit": unit,
                        "interface_ref": "unknown", "source": "regex"})
        return out

    @staticmethod
    def _dependencies_regex(text: str) -> list[dict[str, Any]]:
        # "Flow: A -> B -> C" lines describe execution order, not dependencies.
        text = re.sub(r"(?im)^.*\bflow:.*$", "", text)
        pattern = re.compile(
            r"([A-Z][A-Za-z0-9_]*(?:SWC|_SWC))\s*(?:->|connects to|sends to|calls)\s*"
            r"([A-Z][A-Za-z0-9_]*(?:SWC|_SWC))(?:\s*\(via\s+(\w+)\))?",
            re.IGNORECASE,
        )
        out, seen = [], set()
        for src, tgt, via in pattern.findall(text):
            if (src, tgt) in seen or src.lower() == tgt.lower():
                continue
            seen.add((src, tgt))
            out.append({"source_swc": src, "target_swc": tgt,
                        "interface_name": via or "unknown", "source": "regex"})
        return out

    @staticmethod
    def _flows_regex(text: str) -> list[dict[str, Any]]:
        sequences = re.findall(r"Flow:\s*([A-Za-z0-9_]+(?:\s*->\s*[A-Za-z0-9_]+)+)", text, re.IGNORECASE)
        return [
            {"flow_name": f"Flow {i}", "sequence": seq, "description": "", "source": "regex"}
            for i, seq in enumerate(sequences, start=1)
        ]

    # -------------------------------------------------------- table parsers
    # Each AUTOSAR table has a recognisable row shape: an ID cell (P-01, IF-01,
    # D-01, SWC-01) followed by typed cells. Cells are matched with \s+ so the
    # parsers work whether the PDF text came out of pypdf or pdftotext, with
    # or without -layout.

    _SWC_ROW = re.compile(r"\bSWC-(\d+)\s+(\w+SWC)\b")
    _IF_ROW = re.compile(r"\bIF-(\d+)\s+(\w+If)\s+(Sender-Receiver|Client-Server)\b")
    _PORT_ROW = re.compile(
        r"\bP-(\d+)\s+((?:PP|RP)_\w+)\s+(Provided|Required)\s+(\w+SWC)\s+(\w+If)\s+"
        r"(Sender-Receiver|Client-Server)\s+(Sender|Receiver|Client|Server)\b")
    _SIG_MAP_ROW = re.compile(r"(?m)^[ \t]*([A-Z][A-Za-z0-9_]*)\s+(\w+If)\s+(\w+SWC)\.((?:PP)_\w+)")
    _DEP_ROW = re.compile(
        r"\bD-(\d+)\s+(\w+SWC)\s+(\w+If)\s+(\w+SWC)\s+(SR\s+data(?:\s+flow)?|CS\s+call)\s+"
        r"((?:PP|RP)_\w+)\s+((?:PP|RP)_\w+)\b")

    def _swcs_from_tables(self, text: str) -> list[dict[str, Any]]:
        # Cell order is unreliable once a cell wraps, so ECU and role are
        # searched in the text that follows the row ID.
        rows = list(self._SWC_ROW.finditer(text))
        out, seen = [], set()
        for i, m in enumerate(rows):
            name = m.group(2)
            if name in seen:
                continue
            seen.add(name)
            end = rows[i + 1].start() if i + 1 < len(rows) else len(text)
            tail = text[m.end():min(end, m.end() + 400)]
            ecu = re.search(r"\b(SIE|BCU|BAM)\b", tail)
            role = re.search(r"\((Sensor|Actuator) SW-C\)", tail)
            if re.search(r"\bApplication\s+SW-C\b", tail):
                kind = "Application"
            elif role:
                kind = f"Sensor/Actuator ({role.group(1)})"
            elif "Sensor/Actuator" in tail:
                kind = "Sensor/Actuator"
            else:
                kind = "unknown"
            ecu_name = ecu.group(1) if ecu else ""
            out.append({
                "name": name, "id": f"SWC-{m.group(1)}", "type": kind,
                "description": f"{kind} SW-C" + (f" on ECU {ecu_name}" if ecu_name else ""),
                "source": "table",
            })
        return out

    def _interfaces_from_tables(self, text: str) -> list[dict[str, Any]]:
        out, seen = [], set()
        for m in self._IF_ROW.finditer(text):
            name = m.group(2)
            if name in seen or is_bsw(name):
                continue
            seen.add(name)
            out.append({"name": name, "id": f"IF-{m.group(1)}", "type": m.group(3),
                        "description": "", "source": "table"})
        return out

    def _ports_from_tables(self, text: str) -> list[dict[str, Any]]:
        out, seen = [], set()
        for m in self._PORT_ROW.finditer(text):
            pid, name, direction, owner, iface, itype, role = m.groups()
            if (owner, name) in seen:
                continue
            seen.add((owner, name))
            out.append({"name": name, "id": f"P-{pid}", "direction": direction, "swc_owner": owner,
                        "interface_ref": iface, "interface_type": itype, "role": role, "source": "table"})
        return out

    def _signals_from_tables(self, text: str) -> list[dict[str, Any]]:
        # One mapping row per signal (signal, interface, provider port);
        # data type and unit come from the signal-definition table.
        rows = list(self._SIG_MAP_ROW.finditer(text))
        out, seen = [], set()
        for i, m in enumerate(rows):
            name, iface, provider, pport = m.groups()
            if name in seen or not is_valid_signal(name):
                continue
            seen.add(name)
            end = rows[i + 1].start() if i + 1 < len(rows) else len(text)
            receivers = sorted({f"{o}.{p}" for o, p in
                                re.findall(r"(\w+SWC)\.(RP_\w+)", text[m.end():min(end, m.end() + 300)])})
            definition = re.search(
                r"(?m)^[ \t]*" + re.escape(name) +
                r"\s+(float32|boolean|VehicleMode(?:\s*Type)?(?:\s*\(uint8\))?)\s+(km/h|bar|%|degC|-)(?=\s)", text)
            data_type, unit = "unknown", "-"
            if definition:
                data_type = re.sub(r"\s+", "", definition.group(1)).replace("(uint8)", "")
                if data_type == "VehicleMode":
                    data_type = "VehicleModeType"
                unit = definition.group(2)
            out.append({"name": name, "data_type": data_type, "unit": unit, "interface_ref": iface,
                        "provider_port": f"{provider}.{pport}", "receiver_ports": receivers,
                        "source": "table"})
        return out

    def _dependencies_from_tables(self, text: str) -> list[dict[str, Any]]:
        out, seen = [], set()
        for m in self._DEP_ROW.finditer(text):
            did, src, iface, tgt, kind, sport, tport = m.groups()
            if did in seen:
                continue
            seen.add(did)
            out.append({"id": f"D-{did}", "source_swc": src, "target_swc": tgt, "interface_name": iface,
                        "kind": "SR" if kind.startswith("SR") else "CS",
                        "source_port": sport, "target_port": tport, "source": "table"})
        return out

    # Plain tables without an ID column: "Name_SWC  Application  Description",
    # "P_X  Provided  Owner_SWC  X_If", "Sig  float32  km/h  X_If".

    _PLAIN_SWC_ROW = re.compile(
        r"\b([A-Z]\w*SWC)\s+(Sensor/Actuator|Application|Service Component|Complex Driver|ECU Abstraction)"
        r"[ \t]*\n?[ \t]*([^\n]*)")
    _PLAIN_PORT_ROW = re.compile(r"\b((?:PP|RP|P|R)_\w+)\s+(Provided|Required)\s+([A-Z]\w*SWC)\s+([A-Z]\w*If)\b")
    _PLAIN_SIGNAL_ROW = re.compile(
        r"\b([A-Z]\w*)\s+(float32|float64|uint8|uint16|uint32|sint8|sint16|sint32|boolean)\s+(\S+)\s+([A-Z]\w*If)\b")

    def _swcs_from_plain_rows(self, text: str) -> list[dict[str, Any]]:
        out, seen = [], set()
        for name, kind, description in self._PLAIN_SWC_ROW.findall(text):
            if name not in seen and not is_bsw(name):
                seen.add(name)
                out.append({"name": name, "type": kind, "description": description.strip(), "source": "table"})
        return out

    def _ports_from_plain_rows(self, text: str) -> list[dict[str, Any]]:
        out, seen = [], set()
        for name, direction, owner, iface in self._PLAIN_PORT_ROW.findall(text):
            if (owner, name) not in seen:
                seen.add((owner, name))
                out.append({"name": name, "direction": direction, "swc_owner": owner,
                            "interface_ref": iface, "source": "table"})
        return out

    def _signals_from_plain_rows(self, text: str) -> list[dict[str, Any]]:
        out, seen = [], set()
        for name, data_type, unit, iface in self._PLAIN_SIGNAL_ROW.findall(text):
            if name not in seen and is_valid_signal(name):
                seen.add(name)
                out.append({"name": name, "data_type": data_type, "unit": unit,
                            "interface_ref": iface, "source": "table"})
        return out

    def _flows_from_headings(self, text: str) -> list[dict[str, Any]]:
        # "8.3 FF-02 Wheel-Speed to Brake-Command Flow" followed by a
        # "Chain: A -> B -> C." line, or "Path A is ... (flow FF-0x)" lines.
        heading = re.compile(r"(?m)^(\d+\.\d+)\s+(FF-\d+)\s+(.+?)\s*$")
        next_heading = re.compile(r"(?m)^\d+\.\d+\s+\S")
        flows: dict[str, dict[str, Any]] = {}
        for m in heading.finditer(text):
            if ". ." in m.group(3):  # table-of-contents line
                continue
            nxt = next_heading.search(text, m.end())
            body = text[m.end():nxt.start() if nxt else len(text)]
            chain = re.search(r"Chain:\s*(.+?)\.(?:\s|$)", body, re.S)
            if chain:
                sequence = re.sub(r"\s+", " ", chain.group(1)).strip()
            else:
                paths = re.findall(r"Path [AB] is\s+(.+?)\s+\(flow", body, re.S)
                sequence = " and ".join(re.sub(r"\s+", " ", p).strip() for p in paths)
            if sequence:
                flow_id = m.group(2)
                flows[flow_id] = {"flow_id": flow_id, "flow_name": f"{flow_id} {m.group(3).strip()}",
                                  "sequence": sequence, "description": "", "source": "table"}
        return list(flows.values())

    # ------------------------------------------------------------- LLM pass

    @staticmethod
    def _llm_pass(text: str, document_name: str, llm: LLMClient) -> dict[str, list[dict[str, Any]]]:
        prompt = f"Document: {document_name}\n\n{select_llm_input(text, LLM_EXTRACTION_CHARS)}"
        try:
            reply = llm.chat_json(LLM_SYSTEM_PROMPT, prompt)
        except LLMError as exc:
            log.warning("LLM extraction skipped: %s", exc)
            return {}
        if not reply:
            return {}
        return {kind: clean_llm_items(kind, reply.get(kind, [])) for kind in ENTITY_KINDS}


# ---------------------------------------------------------------- LLM helpers

_PAGE_SPLIT = re.compile(r"--- Page \d+ ---\n")
_ARCH_NAME = re.compile(r"\b(?:\w+(?:SWC|_If|If|Interface|Port|Component)|(?:PP|RP)_\w+)\b")

# Fields the extraction prompt asks for, per kind; anything else is dropped.
LLM_FIELDS = {
    "swcs": ("name", "type", "description"),
    "interfaces": ("name", "type", "description"),
    "ports": ("name", "direction", "swc_owner", "interface_ref"),
    "signals": ("name", "data_type", "unit", "interface_ref"),
    "dependencies": ("source_swc", "target_swc", "interface_name"),
    "functional_flows": ("flow_name", "sequence", "description"),
}
_IDENTIFIER = re.compile(r"^[A-Za-z][\w.\-]*$")
_IDENTIFIER_FIELDS = {"name", "swc_owner", "interface_ref", "source_swc", "target_swc", "interface_name"}


def select_llm_input(full_text: str, budget: int) -> str:
    """The most architecture-dense pages of the document, in page order, within `budget` characters.

    The first pages of a document are usually title, history and contents, so
    taking the text from the start would often give the model nothing to extract.
    """
    pages = [p for p in _PAGE_SPLIT.split(full_text) if p.strip()]
    scores = [len(_ARCH_NAME.findall(p)) for p in pages]
    if not any(scores):
        return full_text[:budget]
    ranked = sorted((i for i in range(len(pages)) if scores[i]), key=lambda i: scores[i], reverse=True)
    chosen, used = [], 0
    for i in ranked:
        if used + len(pages[i]) > budget and chosen:
            continue
        chosen.append(i)
        used += len(pages[i])
        if used >= budget:
            break
    return "\n\n".join(pages[i] for i in sorted(chosen))[:budget]


def clean_llm_items(kind: str, items: Any) -> list[dict[str, Any]]:
    """Keep only well-formed items: known fields, string values, identifier-like names."""
    if not isinstance(items, list):
        return []
    cleaned = []
    for item in items:
        if not isinstance(item, dict):
            continue
        out: dict[str, Any] = {}
        for field in LLM_FIELDS[kind]:
            value = item.get(field)
            if isinstance(value, list):
                value = " -> ".join(str(v) for v in value) if field == "sequence" else "; ".join(map(str, value))
            if value is None:
                continue
            value = str(value).strip()
            if field in _IDENTIFIER_FIELDS and value and not _IDENTIFIER.match(value):
                out = {}
                break  # a "name" that is really a sentence: not a usable element
            out[field] = value
        if kind == "functional_flows" and not _CHAIN.match(out.get("sequence", "")):
            continue  # must be a component chain, not prose
        if out:
            cleaned.append({**out, "source": "llm"})
    return cleaned


_CHAIN = re.compile(r"^\s*[A-Za-z][\w.]*(\s*->\s*[A-Za-z][\w.]*)+\s*$")


def dedupe_flows(flows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the first flow for each component sequence."""
    seen, out = set(), []
    for flow in flows:
        key = _normalise_sequence(str(flow.get("sequence", "")))
        if key not in seen:
            seen.add(key)
            out.append(flow)
    return out


def _normalise_sequence(sequence: str) -> str:
    return re.sub(r"\s+", "", sequence).lower()
