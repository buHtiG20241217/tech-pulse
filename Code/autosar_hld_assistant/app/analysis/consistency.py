"""Completeness and consistency checks over one document's extracted architecture.

Each check reports a potential problem for an engineer to confirm; none of
them changes data. Checks that need information a document doesn't provide
(for example port owners when no port table was found) are skipped rather
than reported as failures.
"""

from __future__ import annotations

from dataclasses import dataclass

from autosar_hld_assistant.app.storage.db import ENTITY_TABLES, DatabaseManager

ERROR = "Error"
WARNING = "Warning"
INFO = "Info"
_SEVERITY_ORDER = {ERROR: 0, WARNING: 1, INFO: 2}
_UNKNOWN = {"", "unknown", "-", None}


@dataclass(frozen=True)
class Finding:
    severity: str
    check: str
    element: str
    message: str


def check_architecture(data: dict[str, list[dict]]) -> list[Finding]:
    """Run all checks on extracted data shaped like DatabaseManager.get_entities() output."""
    swcs = {s["name"] for s in data.get("swcs", [])}
    interfaces = {i["name"] for i in data.get("interfaces", [])}
    ports = [p for p in data.get("ports", []) if p.get("swc_owner") not in _UNKNOWN]
    findings: list[Finding] = []

    def add(severity, check, element, message):
        findings.append(Finding(severity, check, element, message))

    # Ports: owner and interface must be defined.
    for p in ports:
        label = f"{p['swc_owner']}.{p['name']}"
        if swcs and p["swc_owner"] not in swcs:
            add(ERROR, "Undefined SW-C", label, f"Port owner {p['swc_owner']} is not defined as a SW-C.")
        if interfaces and p.get("interface_ref") not in _UNKNOWN and p["interface_ref"] not in interfaces:
            add(ERROR, "Undefined interface", label, f"Port uses {p['interface_ref']}, which is not defined.")

    # Provider/consumer matching per interface.
    providers: dict[str, set[str]] = {}
    consumers: dict[str, set[str]] = {}
    for p in ports:
        iface = p.get("interface_ref")
        if iface in _UNKNOWN:
            continue
        side = providers if p.get("direction") == "Provided" else consumers
        side.setdefault(iface, set()).add(p["swc_owner"])
    for iface in sorted(set(consumers) - set(providers)):
        add(ERROR, "Missing provider", iface,
            f"Required by {', '.join(sorted(consumers[iface]))}, but no SW-C provides it.")
    for iface in sorted(set(providers) - set(consumers)):
        add(WARNING, "Unused interface", iface,
            f"Provided by {', '.join(sorted(providers[iface]))}, but no SW-C requires it.")

    # SW-Cs without ports (only meaningful when ports carry owners).
    if ports:
        owners = {p["swc_owner"] for p in ports}
        for name in sorted(swcs - owners):
            add(WARNING, "SW-C without ports", name, "No port of this SW-C is listed in the port table.")

    # Dependencies: endpoints defined, and backed by ports when ports are known.
    for d in data.get("dependencies", []):
        label = f"{d['source_swc']} -> {d['target_swc']}"
        for end in (d["source_swc"], d["target_swc"]):
            if swcs and end not in swcs:
                add(ERROR, "Undefined SW-C", label, f"{end} is not defined as a SW-C.")
        iface = d.get("interface_name")
        if ports and iface not in _UNKNOWN:
            provided_by = providers.get(iface, set())
            required_by = consumers.get(iface, set())
            # Sender-receiver dependencies run provider -> consumer; client-server
            # calls are usually written client -> server. Accept either.
            backed = ((d["source_swc"] in provided_by and d["target_swc"] in required_by)
                      or (d["source_swc"] in required_by and d["target_swc"] in provided_by))
            if not backed:
                add(WARNING, "Dependency not backed by ports", label,
                    f"No matching provided/required port pair on {iface}.")

    # Signals must travel over a defined interface.
    known_ifaces = interfaces | set(providers) | set(consumers)
    for s in data.get("signals", []):
        iface = s.get("interface_ref")
        if iface not in _UNKNOWN and known_ifaces and iface not in known_ifaces:
            add(WARNING, "Signal on unknown interface", s["name"], f"Mapped to {iface}, which no port uses.")
        if s.get("data_type") in _UNKNOWN:
            add(INFO, "Missing data type", s["name"], "No data type found for this signal.")

    return sorted(findings, key=lambda f: (_SEVERITY_ORDER[f.severity], f.check, f.element))


def check_document(db: DatabaseManager, document_name: str) -> list[Finding]:
    return check_architecture({kind: db.get_entities(kind, document_name) for kind in ENTITY_TABLES})
