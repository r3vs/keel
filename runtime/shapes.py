"""Field-shape engine runtime — extractors + diff over the shared descriptor.

Implements `core/shape-engine.md` for the live stacks the step-0 experiments validated
(rescue: WEAK → standalone extractors are Plan A; greenfield: STRONG → generated layers,
guarded by this very diff as the CI drift-check):

- extract_contract    : the carrier (contract.json descriptor set) — greenfield's source
- extract_sqlalchemy  : SQLAlchemy 2.0 `Mapped`/`mapped_column` models (Python `ast`, no imports)
- extract_pydantic    : Pydantic-v2 DTOs (`<Entity>Read` = full projection, `<Entity>Create`
                        = partial: present fields must match, missing ones are not drift)
- extract_typescript  : `export interface` / `export type` unions (line parser)
- extract_ddl         : Postgres `CREATE TABLE` / `CREATE TYPE ... AS ENUM`

Every representation reduces to `{name, type, nullable, enum?, constraints?}` with a canonical
type (string|int|float|bool|enum|uuid|json|datetime), then `diff_shapes` compares any two
projections. The two honesty rules are enforced:
  1. uncertain equivalence → `confidence: ambiguous`, downgraded to a note, never asserted;
  2. a field absent on one side IS the finding (missing_field) — never papered over.

Stdlib-only, deliberately dependency-free; new stacks are additive (tree-sitter generalization
stays on the TODO). Findings are dicts shaped to feed `runtime/ledger.py` contract_mismatch pins.
"""
from __future__ import annotations

import ast
import json
import pathlib
import re
from typing import Optional

CANONICAL = ("string", "int", "float", "bool", "enum", "uuid", "json", "datetime")

# ---------------------------------------------------------------------------
# descriptor helpers
# ---------------------------------------------------------------------------


def descriptor(name: str, type_: str, nullable: bool, enum: Optional[list] = None,
               constraints: Optional[dict] = None, confidence: str = "extracted") -> dict:
    d = {"name": name, "type": type_, "nullable": nullable, "confidence": confidence}
    if enum:
        d["enum"] = list(enum)
    if constraints:
        d["constraints"] = constraints
    return d


# ---------------------------------------------------------------------------
# carrier (contract.json)
# ---------------------------------------------------------------------------


def extract_contract(path: str | pathlib.Path) -> dict[str, dict[str, dict]]:
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    out: dict[str, dict[str, dict]] = {}
    for entity, spec in data.get("entities", {}).items():
        fields = {}
        for f in spec.get("fields", []):
            fields[f["name"]] = descriptor(
                f["name"], f["type"], bool(f.get("nullable", False)),
                f.get("enum"), f.get("constraints"),
            )
        out[entity] = fields
    return out


def contract_tables(path: str | pathlib.Path) -> dict[str, str]:
    """table name → entity name (for the DDL layer)."""
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    return {spec.get("table", entity.lower() + "s"): entity
            for entity, spec in data.get("entities", {}).items()}


# ---------------------------------------------------------------------------
# SQLAlchemy 2.0 models (python ast — parses source, imports nothing)
# ---------------------------------------------------------------------------

_PY_TYPE_MAP = {
    "str": "string", "int": "int", "float": "float", "bool": "bool",
    "datetime": "datetime", "date": "datetime",
    "UUID": "uuid", "uuid.UUID": "uuid",
    "dict": "json", "Any": "json",
}


def _ann_to_canonical(node: ast.expr, enums: dict[str, list]) -> tuple[str, bool, Optional[list]]:
    """annotation → (canonical type, nullable, enum values). Unknown → ('unknown', …)."""
    if isinstance(node, ast.Subscript):
        base = ast.unparse(node.value)
        if base in ("Optional",):
            t, _, ev = _ann_to_canonical(node.slice, enums)
            return t, True, ev
        if base in ("Mapped",):
            return _ann_to_canonical(node.slice, enums)
        if base in ("dict", "Dict"):
            return "json", False, None
        if base in ("list", "List"):
            return "relationship", False, None      # collection → relationship, not a column
        if base == "Literal":
            elts = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
            values = [e.value for e in elts if isinstance(e, ast.Constant)]
            return "enum", False, values
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):  # X | None
        left, _, ev = _ann_to_canonical(node.left, enums)
        right = ast.unparse(node.right)
        if right == "None":
            return left, True, ev
    name = ast.unparse(node).strip("'\"")
    if name in enums:
        return "enum", False, enums[name]
    if name in _PY_TYPE_MAP:
        return _PY_TYPE_MAP[name], False, None
    short = name.split(".")[-1]
    if short in _PY_TYPE_MAP:
        return _PY_TYPE_MAP[short], False, None
    return "unknown", False, None


def _collect_py_enums(tree: ast.Module) -> dict[str, list]:
    enums: dict[str, list] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            base_names = {ast.unparse(b) for b in node.bases}
            if any("Enum" in b for b in base_names):
                values = [s.value.value for s in node.body
                          if isinstance(s, ast.Assign) and isinstance(s.value, ast.Constant)]
                if values:
                    enums[node.name] = values
    return enums


def extract_sqlalchemy(path: str | pathlib.Path) -> dict[str, dict[str, dict]]:
    tree = ast.parse(pathlib.Path(path).read_text(encoding="utf-8"))
    enums = _collect_py_enums(tree)
    out: dict[str, dict[str, dict]] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        tablename = next((ast.unparse(s.value).strip("'\"") for s in node.body
                          if isinstance(s, ast.Assign)
                          and any(getattr(t, "id", "") == "__tablename__" for t in s.targets)),
                         None)
        if tablename is None:
            continue
        fields: dict[str, dict] = {}
        for stmt in node.body:
            if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
                continue
            attr = stmt.target.id
            call = stmt.value
            if isinstance(call, ast.Call) and ast.unparse(call.func).endswith("relationship"):
                continue
            t, nullable, ev = _ann_to_canonical(stmt.annotation, enums)
            if t == "relationship":
                continue
            col_name, constraints = attr, {}
            if isinstance(call, ast.Call):
                # mapped_column("colname", ...) — explicit column name (reserved-word escape)
                for arg in call.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        col_name = arg.value
                    if isinstance(arg, ast.Call):
                        fn = ast.unparse(arg.func).split(".")[-1]
                        if fn == "String" and arg.args:
                            constraints["max_length"] = ast.literal_eval(arg.args[0])
                        if fn == "ForeignKey" and arg.args:
                            constraints["foreign_key"] = ast.literal_eval(arg.args[0])
                for kw in call.keywords:
                    if kw.arg == "primary_key":
                        constraints["primary_key"] = True
                    if kw.arg == "unique":
                        constraints["unique"] = True
                    if kw.arg in ("default", "server_default"):
                        constraints.setdefault("default", ast.unparse(kw.value))
            conf = "extracted" if t != "unknown" else "ambiguous"
            fields[col_name] = descriptor(col_name, t, nullable, ev, constraints or None, conf)
        out[tablename] = fields
    return out


# ---------------------------------------------------------------------------
# Pydantic v2 DTOs
# ---------------------------------------------------------------------------


def extract_pydantic(path: str | pathlib.Path) -> dict[str, dict[str, dict]]:
    """Returns per-CLASS shapes (UserRead, UserCreate, …); mapping to entities is diff's job."""
    tree = ast.parse(pathlib.Path(path).read_text(encoding="utf-8"))
    # module-level Literal aliases: UserRole = Literal["admin", "member"]
    enums: dict[str, list] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Subscript) \
                and ast.unparse(node.value.value) == "Literal":
            elts = node.value.slice.elts if isinstance(node.value.slice, ast.Tuple) \
                else [node.value.slice]
            values = [e.value for e in elts if isinstance(e, ast.Constant)]
            for target in node.targets:
                if isinstance(target, ast.Name):
                    enums[target.id] = values
    out: dict[str, dict[str, dict]] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        bases = {ast.unparse(b) for b in node.bases}
        if not any("BaseModel" in b or b in out for b in bases):
            continue
        fields: dict[str, dict] = {}
        for base in bases:            # single-level inheritance of already-seen DTO bases
            fields.update(out.get(base, {}))
        for stmt in node.body:
            if not isinstance(stmt, ast.AnnAssign) or not isinstance(stmt.target, ast.Name):
                continue
            name = stmt.target.id
            if name == "model_config":
                continue
            t, nullable, ev = _ann_to_canonical(stmt.annotation, enums)
            constraints = {}
            if isinstance(stmt.value, ast.Call) and ast.unparse(stmt.value.func) == "Field":
                for kw in stmt.value.keywords:
                    if kw.arg == "max_length":
                        constraints["max_length"] = ast.literal_eval(kw.value)
                    if kw.arg == "validation_alias":
                        constraints["validation_alias"] = ast.literal_eval(kw.value)
            conf = "extracted" if t != "unknown" else "ambiguous"
            fields[name] = descriptor(name, t, nullable, ev, constraints or None, conf)
        out[node.name] = fields
    return out


# ---------------------------------------------------------------------------
# TypeScript interfaces / type unions
# ---------------------------------------------------------------------------

_TS_TYPE_MAP = {"string": "string", "number": "int", "boolean": "bool",
                "Record<string, unknown>": "json", "unknown": "json"}
_TS_FIELD = re.compile(r"^\s*(\w+)(\?)?:\s*(.+?);\s*(?://\s*(.*))?$")
_TS_UNION = re.compile(r'^export type (\w+) = (.+);', re.M)


def extract_typescript(path: str | pathlib.Path) -> dict[str, dict[str, dict]]:
    """Returns per-INTERFACE shapes. `// uuid` / `// ISO datetime` trailing comments refine
    the branded-string convention from `core/shape-engine.md`'s equivalence table."""
    text = pathlib.Path(path).read_text(encoding="utf-8")
    unions: dict[str, list] = {}
    for m in _TS_UNION.finditer(text):
        parts = [p.strip() for p in m.group(2).split("|")]
        if all(p.startswith('"') and p.endswith('"') for p in parts):
            unions[m.group(1)] = [p.strip('"') for p in parts]
    out: dict[str, dict[str, dict]] = {}
    current: Optional[str] = None
    for line in text.splitlines():
        header = re.match(r"^export interface (\w+)\s*{", line)
        if header:
            current = header.group(1)
            out[current] = {}
            continue
        if current and line.strip().startswith("}"):
            current = None
            continue
        if current:
            m = _TS_FIELD.match(line)
            if not m:
                continue
            name, optional, ts_type, comment = m.groups()
            comment = (comment or "").lower()
            nullable = False
            base = ts_type.strip()
            if base.endswith("| null"):
                nullable = True
                base = base[: -len("| null")].strip()
            if optional:
                nullable = True      # partial DTOs: optional ≈ may be absent; diff treats
                                     # Create-interfaces as partial anyway
            enum_vals = unions.get(base)
            if enum_vals:
                t = "enum"
            elif "uuid" in comment:
                t = "uuid"           # branded string (equivalence-table row: uuid → string)
            elif "datetime" in comment or "iso" in comment:
                t = "datetime"       # ISO string projection
            elif base in _TS_TYPE_MAP:
                t = _TS_TYPE_MAP[base]
            else:
                t = "unknown"
            conf = "extracted" if t != "unknown" else "ambiguous"
            out[current][name] = descriptor(name, t, nullable, enum_vals, None, conf)
    return out


# ---------------------------------------------------------------------------
# Postgres DDL
# ---------------------------------------------------------------------------

_DDL_TYPE_MAP = {"uuid": "uuid", "text": "string", "boolean": "bool", "integer": "int",
                 "bigint": "int", "timestamptz": "datetime", "jsonb": "json",
                 "real": "float", "double precision": "float"}


def extract_ddl(path: str | pathlib.Path) -> dict[str, dict[str, dict]]:
    text = pathlib.Path(path).read_text(encoding="utf-8")
    enums: dict[str, list] = {}
    for m in re.finditer(r"CREATE TYPE (\w+) AS ENUM \(([^)]*)\)", text, re.I):
        enums[m.group(1)] = [v.strip().strip("'") for v in m.group(2).split(",")]
    out: dict[str, dict[str, dict]] = {}
    for m in re.finditer(r"CREATE TABLE (\w+)\s*\((.*?)\);", text, re.S | re.I):
        table, body = m.group(1), m.group(2)
        fields: dict[str, dict] = {}
        for raw in re.split(r",\s*\n", body):
            line = raw.strip()
            col = re.match(r"^(\w+)\s+(\w+(?:\(\d+\))?|double precision)(.*)$", line, re.I)
            if not col or line.upper().startswith(("PRIMARY", "FOREIGN", "UNIQUE", "CHECK",
                                                   "CONSTRAINT")):
                continue
            name, sql_type, rest = col.group(1), col.group(2).lower(), col.group(3)
            constraints: dict = {}
            varchar = re.match(r"varchar\((\d+)\)", sql_type)
            if varchar:
                t = "string"
                constraints["max_length"] = int(varchar.group(1))
            elif sql_type in _DDL_TYPE_MAP:
                t = _DDL_TYPE_MAP[sql_type]
            elif sql_type in enums:
                t = "enum"
            else:
                t = "unknown"
            rest_u = rest.upper()
            nullable = "NOT NULL" not in rest_u and "PRIMARY KEY" not in rest_u
            if "PRIMARY KEY" in rest_u:
                constraints["primary_key"] = True
            if "UNIQUE" in rest_u:
                constraints["unique"] = True
            fk = re.search(r"REFERENCES\s+(\w+)\s*\((\w+)\)", rest, re.I)
            if fk:
                constraints["foreign_key"] = f"{fk.group(1)}.{fk.group(2)}"
            conf = "extracted" if t != "unknown" else "ambiguous"
            fields[name] = descriptor(name, t, nullable, enums.get(sql_type),
                                      constraints or None, conf)
        out[table] = fields
    return out


# ---------------------------------------------------------------------------
# the diff (rescue: find drift · greenfield: fail the build on drift)
# ---------------------------------------------------------------------------


def diff_shapes(reference: dict[str, dict], candidate: dict[str, dict],
                ref_layer: str, cand_layer: str, entity: str,
                partial: bool = False) -> list[dict]:
    """Compare one entity's fields across two layers. `partial=True` (Create DTOs):
    fields absent from the candidate are not drift; present ones must still agree."""
    findings: list[dict] = []

    def finding(kind: str, field: str, detail: str, confidence: str = "extracted") -> dict:
        return {"entity": entity, "field": field, "kind": kind, "detail": detail,
                "layers": [ref_layer, cand_layer], "confidence": confidence}

    for name, ref in reference.items():
        cand = candidate.get(name)
        if cand is None:
            if not partial:
                findings.append(finding("missing_field", name,
                                        f"{name} exists in {ref_layer} but not in {cand_layer}"))
            continue
        # honesty rule 1: an unresolved side is a note, never an asserted mismatch
        if ref["type"] == "unknown" or cand["type"] == "unknown":
            findings.append(finding(
                "unresolved", name,
                f"could not resolve type on one side ({ref['type']} vs {cand['type']})",
                confidence="ambiguous"))
            continue
        # equivalence-table projections (core/shape-engine.md): on the client layer,
        # uuid and datetime legitimately project to plain `string` (branded/ISO) — a
        # trailing `// uuid` / `// ISO datetime` comment refines them back when present.
        client_projection = (cand_layer.startswith("client")
                             and ref["type"] in ("uuid", "datetime")
                             and cand["type"] == "string")
        if ref["type"] != cand["type"] and not client_projection:
            findings.append(finding(
                "type_mismatch", name,
                f"{ref_layer}={ref['type']} vs {cand_layer}={cand['type']}"))
        elif ref["type"] == "enum" and ref.get("enum") and cand.get("enum") \
                and set(ref["enum"]) != set(cand["enum"]):
            findings.append(finding(
                "enum_mismatch", name,
                f"{ref_layer}={ref['enum']} vs {cand_layer}={cand['enum']}"))
        if not partial and bool(ref["nullable"]) != bool(cand["nullable"]):
            findings.append(finding(
                "nullability_mismatch", name,
                f"{ref_layer} nullable={ref['nullable']} vs {cand_layer} nullable={cand['nullable']}"))
    for name in candidate:
        if name not in reference:
            findings.append(finding("extra_field", name,
                                    f"{name} exists in {cand_layer} but not in {ref_layer}"))
    return findings


def drift_check(contract_path: str, sqlalchemy: Optional[str] = None,
                pydantic: Optional[str] = None, typescript: Optional[str] = None,
                ddl: Optional[str] = None) -> list[dict]:
    """Diff every provided layer against the carrier. This IS greenfield's CI drift-check
    and rescue's contract-reconciliation core, pointed at a shared-types-style carrier."""
    contract = extract_contract(contract_path)
    tables = contract_tables(contract_path)
    findings: list[dict] = []

    if ddl:
        shapes = extract_ddl(ddl)
        for table, entity in tables.items():
            if table not in shapes:
                findings.append({"entity": entity, "field": "*", "kind": "missing_entity",
                                 "detail": f"table {table} absent from DDL",
                                 "layers": ["contract", "db"], "confidence": "extracted"})
                continue
            findings += diff_shapes(contract[entity], shapes[table], "contract", "db", entity)
    if sqlalchemy:
        shapes = extract_sqlalchemy(sqlalchemy)
        for table, entity in tables.items():
            if table in shapes:
                findings += diff_shapes(contract[entity], shapes[table],
                                        "contract", "orm", entity)
    if pydantic:
        classes = extract_pydantic(pydantic)
        for entity in contract:
            if f"{entity}Read" in classes:
                findings += diff_shapes(contract[entity], classes[f"{entity}Read"],
                                        "contract", "api:read", entity)
            if f"{entity}Create" in classes:
                findings += diff_shapes(contract[entity], classes[f"{entity}Create"],
                                        "contract", "api:create", entity, partial=True)
    if typescript:
        interfaces = extract_typescript(typescript)
        for entity in contract:
            if entity in interfaces:
                findings += diff_shapes(contract[entity], interfaces[entity],
                                        "contract", "client", entity)
            if f"{entity}Create" in interfaces:
                findings += diff_shapes(contract[entity], interfaces[f"{entity}Create"],
                                        "contract", "client:create", entity, partial=True)
    return findings


def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Shape drift-check: diff generated/hand-written layers against the carrier")
    parser.add_argument("--contract", required=True)
    parser.add_argument("--sqlalchemy")
    parser.add_argument("--pydantic")
    parser.add_argument("--typescript")
    parser.add_argument("--ddl")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    findings = drift_check(args.contract, args.sqlalchemy, args.pydantic,
                           args.typescript, args.ddl)
    hard = [f for f in findings if f["confidence"] != "ambiguous"]
    if args.json:
        print(json.dumps(findings, indent=2, ensure_ascii=False))
    else:
        for f in findings:
            tag = "DRIFT " if f["confidence"] != "ambiguous" else "NOTE  "
            print(f"{tag} {f['entity']}.{f['field']}  [{f['kind']}]  {f['detail']}")
        print(f"\nshape drift-check: {len(hard)} drift(s), "
              f"{len(findings) - len(hard)} ambiguous note(s)")
    return 1 if hard else 0


if __name__ == "__main__":
    raise SystemExit(main())
