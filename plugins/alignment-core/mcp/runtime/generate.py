"""Contract propagation runtime — generate every layer from one contract descriptor.

The inverse of `runtime/shapes.py` (which extracts + diffs) and greenfield's core payload:
`core/shape-engine.md` run in **generate mode**. One canonical contract →
`{name,type,nullable,enum?,constraints?}` per field → an aligned, idiomatic scaffold for each
layer, so the layers cannot disagree by construction.

Proof of alignment is mechanical and lives in the tests: generate all four layers, then run
`shapes.drift_check` over them — a correct generator produces **zero drift** against its own
contract. That round-trip is greenfield's step-0 STRONG verdict turned into an executable
guarantee (the four frictions recorded there — reserved-word column aliases, enum
value-vs-name storage, snake_case wire casing, non-derivable semantic validators — are handled
here, not left to a developer to trip over).

Targets (the live stack family from the step-0 verdict): Postgres DDL, SQLAlchemy 2.0,
Pydantic v2 + FastAPI routes, TypeScript client. Stdlib-only; new stacks are additive.
"""
from __future__ import annotations

import json
import pathlib
import re
from typing import Optional

# ── canonical → per-layer type projections (the equivalence table, generate direction) ──

_DDL_TYPES = {
    "string": "text", "int": "integer", "float": "double precision", "bool": "boolean",
    "uuid": "uuid", "json": "jsonb", "datetime": "timestamptz",
}
_SA_TYPES = {  # (annotation, column-arg | None)
    "string": ("str", None), "int": ("int", "Integer"), "float": ("float", "Float"),
    "bool": ("bool", None), "uuid": ("uuid.UUID", "UUID(as_uuid=True)"),
    "json": ("dict[str, Any]", "JSONB"), "datetime": ("datetime", "DateTime(timezone=True)"),
}
_PYD_TYPES = {
    "string": "str", "int": "int", "float": "float", "bool": "bool",
    "uuid": "uuid.UUID", "json": "dict[str, Any]", "datetime": "datetime",
}
_TS_TYPES = {
    "string": ("string", ""), "int": ("number", ""), "float": ("number", ""),
    "bool": ("boolean", ""), "uuid": ("string", " // uuid"), "json": ("Record<string, unknown>", ""),
    "datetime": ("string", " // ISO datetime"),
}

# SQLAlchemy reserved instance attributes → column-name aliases (the friction #1 escape).
_SA_RESERVED = {"metadata", "query", "registry"}


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _table_of(entity: str, spec: dict) -> str:
    table = spec.get("table")
    if not table:
        raise ValueError(
            f"contract entity {entity!r} must declare `table` explicitly "
            f"(the table name is a decision, never guessed by pluralizing the entity name)")
    return table


def _enum_type_name(entity: str, field: str) -> str:
    return f"{_snake(entity)}_{field}"


class Contract:
    def __init__(self, data: dict):
        self.entities: dict[str, dict] = data.get("entities", {})

    @classmethod
    def load(cls, path: str | pathlib.Path) -> "Contract":
        return cls(json.loads(pathlib.Path(path).read_text(encoding="utf-8")))

    def enums(self) -> dict[str, list]:
        """(entity, field) enum fields → { enum_type_name: values }."""
        out = {}
        for entity, spec in self.entities.items():
            for f in spec.get("fields", []):
                if f["type"] == "enum" and f.get("enum"):
                    out[_enum_type_name(entity, f["name"])] = f["enum"]
        return out


# ── DDL (Postgres migration) ────────────────────────────────────────────────

def generate_ddl(contract: Contract) -> str:
    lines = ["-- GENERATED from the contract by runtime/generate.py — do not hand-edit shapes.",
             "BEGIN;", "", 'CREATE EXTENSION IF NOT EXISTS "pgcrypto";', ""]
    for name, values in contract.enums().items():
        vals = ", ".join(f"'{v}'" for v in values)
        lines.append(f"CREATE TYPE {name} AS ENUM ({vals});")
    lines.append("")

    indexes = []
    for entity, spec in contract.entities.items():
        table = _table_of(entity, spec)
        cols = []
        for f in spec["fields"]:
            cons = f.get("constraints", {})
            if f["type"] == "enum":
                sql_type = _enum_type_name(entity, f["name"])
            elif f["type"] == "string" and cons.get("max_length"):
                sql_type = f"varchar({cons['max_length']})"
            else:
                sql_type = _DDL_TYPES[f["type"]]
            parts = [f["name"], sql_type]
            if cons.get("primary_key"):
                parts.append("PRIMARY KEY DEFAULT gen_random_uuid()" if f["type"] == "uuid"
                             else "PRIMARY KEY")
            else:
                if not f["nullable"]:
                    parts.append("NOT NULL")
                if cons.get("unique"):
                    parts.append("UNIQUE")
                if "foreign_key" in cons:
                    ref_entity, ref_col = cons["foreign_key"].split(".")
                    ref_table = _table_of(ref_entity, contract.entities.get(ref_entity, {}))
                    on_delete = cons.get("on_delete", "").upper().replace("_", " ")
                    fk = f"REFERENCES {ref_table}({ref_col})"
                    if on_delete:
                        fk += f" ON DELETE {on_delete}"
                    parts.append(fk)
                default = cons.get("default")
                if default is not None and default != "generated":
                    parts.append(f"DEFAULT {_ddl_default(default, f['type'])}")
            cols.append("    " + " ".join(parts))
            if cons.get("index") and not cons.get("primary_key"):
                indexes.append(f"CREATE INDEX {table}_{f['name']}_idx ON {table} ({f['name']});")
        lines.append(f"CREATE TABLE {table} (")
        lines.append(",\n".join(cols))
        lines.append(");")
        lines.append("")
    lines += indexes
    lines += ["", "COMMIT;"]
    return "\n".join(lines) + "\n"


def _ddl_default(default, type_: str) -> str:
    if type_ == "datetime" and default == "now":
        return "now()"
    if type_ == "bool":
        return "true" if default in (True, "true") else "false"
    if type_ == "enum" or type_ == "string":
        return f"'{default}'"
    return str(default)


# ── SQLAlchemy 2.0 models ────────────────────────────────────────────────────

def generate_sqlalchemy(contract: Contract) -> str:
    enums = contract.enums()
    head = ['"""GENERATED from the contract by runtime/generate.py — do not hand-edit shapes."""',
            "from __future__ import annotations", "", "import enum", "import uuid",
            "from datetime import datetime", "from typing import Any, Optional", "",
            "from sqlalchemy import (DateTime, Enum, Float, ForeignKey, Integer, String, Text,",
            "                        func)",
            "from sqlalchemy.dialects.postgresql import JSONB, UUID",
            "from sqlalchemy.orm import (DeclarativeBase, Mapped, mapped_column, relationship)",
            "", "", "class Base(DeclarativeBase):", "    pass", ""]

    enum_classes = []
    for entity, spec in contract.entities.items():
        for f in spec["fields"]:
            if f["type"] == "enum" and f.get("enum"):
                cls = _enum_class_name(entity, f["name"])
                members = "\n".join(f'    {v.upper()} = "{v}"' for v in f["enum"])
                enum_classes.append(f'\n\nclass {cls}(str, enum.Enum):\n{members}')
    body = ["".join(enum_classes), "", "",
            "def _pg_enum(py_enum, name):",
            "    # store enum *values*, not member names — matches the DDL ENUM types (friction #2)",
            "    return Enum(py_enum, name=name,",
            "                values_callable=lambda e: [m.value for m in e])", ""]

    for entity, spec in contract.entities.items():
        table = _table_of(entity, spec)
        body += ["", f"class {entity}(Base):", f'    __tablename__ = "{table}"', ""]
        for f in spec["fields"]:
            body.append("    " + _sa_column(entity, f, contract))
        body.append("")
    return "\n".join(head + body) + "\n"


def _enum_class_name(entity: str, field: str) -> str:
    return f"{entity}{''.join(p.capitalize() for p in field.split('_'))}"


def _sa_column(entity: str, f: dict, contract: Contract) -> str:
    cons = f.get("constraints", {})
    attr = f["name"] + ("_" if f["name"] in _SA_RESERVED else "")
    args: list[str] = []
    if f["name"] in _SA_RESERVED:
        args.append(f'"{f["name"]}"')   # explicit column name (friction #1)

    if f["type"] == "enum":
        enum_cls = _enum_class_name(entity, f["name"])
        ann = enum_cls
        args.append(f'_pg_enum({enum_cls}, "{_enum_type_name(entity, f["name"])}")')
    else:
        ann, col_type = _SA_TYPES[f["type"]]
        if f["type"] == "string" and cons.get("max_length"):
            args.append(f"String({cons['max_length']})")
        elif f["type"] == "string":
            args.append("Text")
        elif col_type:
            args.append(col_type)

    if "foreign_key" in cons:
        ref_entity, ref_col = cons["foreign_key"].split(".")
        ref_table = _table_of(ref_entity, contract.entities.get(ref_entity, {}))
        on_delete = cons.get("on_delete", "").upper().replace("_", " ")
        fk = f'ForeignKey("{ref_table}.{ref_col}"'
        if on_delete:
            fk += f', ondelete="{on_delete}"'
        fk += ")"
        args.append(fk)
    if cons.get("primary_key"):
        args.append("primary_key=True")
    if cons.get("unique"):
        args.append("unique=True")
    if cons.get("index") and not cons.get("primary_key"):
        args.append("index=True")
    default = cons.get("default")
    if cons.get("primary_key") and f["type"] == "uuid":
        args.append("default=uuid.uuid4")
    elif default == "now":
        args.append("server_default=func.now()")
    elif default is not None and default != "generated":
        if f["type"] == "enum":
            args.append(f"default={_enum_class_name(entity, f['name'])}.{str(default).upper()}")
        elif f["type"] == "bool":
            args.append(f"default={bool(default)}")
        elif f["type"] == "string":
            args.append(f'default="{default}"')
        else:
            args.append(f"default={default}")

    type_ann = f"Optional[{ann}]" if f["nullable"] else ann
    return f"{attr}: Mapped[{type_ann}] = mapped_column({', '.join(args)})"


# ── Pydantic v2 DTOs ─────────────────────────────────────────────────────────

def generate_pydantic(contract: Contract) -> str:
    head = ['"""GENERATED from the contract by runtime/generate.py — do not hand-edit shapes."""',
            "from __future__ import annotations", "", "import uuid",
            "from datetime import datetime", "from typing import Any, Literal, Optional", "",
            "from pydantic import BaseModel, ConfigDict, Field", ""]
    aliases = []
    for entity, spec in contract.entities.items():
        for f in spec["fields"]:
            if f["type"] == "enum" and f.get("enum"):
                lit = ", ".join(f'"{v}"' for v in f["enum"])
                aliases.append(f"{_enum_class_name(entity, f['name'])} = Literal[{lit}]")
    body = ["", *aliases, ""]

    for entity, spec in contract.entities.items():
        # Create = writable fields (no PK, no generated default); Read = full projection
        body += ["", f"class {entity}Create(BaseModel):"]
        create_fields = [f for f in spec["fields"]
                         if not f.get("constraints", {}).get("primary_key")
                         and f.get("constraints", {}).get("default") != "now"]
        for f in create_fields:
            body.append("    " + _pyd_field(entity, f, optional_default=True))
        if not create_fields:
            body.append("    pass")

        body += ["", f"class {entity}Read(BaseModel):",
                 "    model_config = ConfigDict(from_attributes=True)", ""]
        for f in spec["fields"]:
            body.append("    " + _pyd_field(entity, f, optional_default=False, read=True))
        body.append("")
    return "\n".join(head + body) + "\n"


def _pyd_field(entity: str, f: dict, optional_default: bool, read: bool = False) -> str:
    cons = f.get("constraints", {})
    ann = (_enum_class_name(entity, f["name"]) if f["type"] == "enum"
           else _PYD_TYPES[f["type"]])
    if f["nullable"]:
        ann = f"Optional[{ann}]"
    extras = []
    if cons.get("max_length"):
        extras.append(f"max_length={cons['max_length']}")
    if read and f["name"] in _SA_RESERVED:
        extras.append(f'validation_alias="{f["name"]}_"')   # read back the aliased ORM attr

    field_call = f"Field({', '.join(extras)})" if extras else None
    default = cons.get("default")
    if read:
        rhs = f" = {field_call}" if field_call else ""
        # nullable read fields carry an explicit default so partial ORM rows validate
        if f["nullable"] and not field_call:
            rhs = " = None"
        return f"{f['name']}: {ann}{rhs}"
    # Create field
    if optional_default and f["type"] == "enum" and default is not None:
        return f'{f["name"]}: {ann} = "{default}"'
    if optional_default and default is not None and default != "generated" and default != "now":
        lit = f'"{default}"' if f["type"] == "string" else (
            "None" if default is None else str(default if f["type"] != "bool" else bool(default)))
        return f"{f['name']}: {ann} = {lit}"
    if f["nullable"]:
        rhs = f" = {field_call}" if field_call else " = None"
        return f"{f['name']}: {ann}{rhs}"
    return f"{f['name']}: {ann}" + (f" = {field_call}" if field_call else "")


# ── TypeScript client types ──────────────────────────────────────────────────

def generate_typescript(contract: Contract) -> str:
    lines = ["// GENERATED from the contract by runtime/generate.py — do not hand-edit shapes.",
             "// snake_case mirrors the wire format (FastAPI default).", ""]
    for entity, spec in contract.entities.items():
        for f in spec["fields"]:
            if f["type"] == "enum" and f.get("enum"):
                union = " | ".join(f'"{v}"' for v in f["enum"])
                lines.append(f"export type {_enum_class_name(entity, f['name'])} = {union};")
    lines.append("")

    for entity, spec in contract.entities.items():
        lines.append(f"export interface {entity} {{")
        for f in spec["fields"]:
            lines.append("  " + _ts_field(entity, f, optional=False))
        lines.append("}")
        lines.append("")
        # Create interface: writable fields, optional where a default exists
        lines.append(f"export interface {entity}Create {{")
        for f in spec["fields"]:
            cons = f.get("constraints", {})
            if cons.get("primary_key") or cons.get("default") == "now":
                continue
            optional = cons.get("default") is not None
            lines.append("  " + _ts_field(entity, f, optional=optional))
        lines.append("}")
        lines.append("")
    return "\n".join(lines) + "\n"


def _ts_field(entity: str, f: dict, optional: bool) -> str:
    if f["type"] == "enum":
        base, comment = _enum_class_name(entity, f["name"]), ""
    else:
        base, comment = _TS_TYPES[f["type"]]
    ts_type = base
    if f["nullable"]:
        ts_type += " | null"
    q = "?" if optional else ""
    return f"{f['name']}{q}: {ts_type};{comment}"


# ── orchestration ────────────────────────────────────────────────────────────

LAYERS = ("ddl", "sqlalchemy", "pydantic", "typescript")
_GENERATORS = {
    "ddl": generate_ddl, "sqlalchemy": generate_sqlalchemy,
    "pydantic": generate_pydantic, "typescript": generate_typescript,
}
_FILENAMES = {"ddl": "001_initial.sql", "sqlalchemy": "models.py",
              "pydantic": "schemas.py", "typescript": "types.ts"}


def choose_carrier(stack: dict) -> str:
    """Contract-carrier chooser (ponytail: the lightest carrier that spans the stack).
    TS end-to-end / monorepo → a shared-types package; polyglot → OpenAPI/JSON-schema;
    an elected RPC/streaming decision → protobuf."""
    langs = {stack.get("api", ""), stack.get("client", "")}
    text = " ".join(str(v) for v in stack.values()).lower()
    if "protobuf" in text or "grpc" in text:
        return "protobuf"
    if all("ts" in l or "typescript" in l or "js" in l for l in langs if l):
        return "shared-types"
    return "openapi"


def generate_all(contract: Contract, layers=LAYERS) -> dict[str, str]:
    return {layer: _GENERATORS[layer](contract) for layer in layers}


def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Generate aligned layers from one contract")
    parser.add_argument("--contract", required=True)
    parser.add_argument("--out", default="", help="write files to this dir (else stdout)")
    parser.add_argument("--layer", choices=LAYERS, action="append",
                        help="restrict to these layers (default: all)")
    args = parser.parse_args(argv)

    contract = Contract.load(args.contract)
    layers = tuple(args.layer) if args.layer else LAYERS
    outputs = generate_all(contract, layers)
    if args.out:
        out = pathlib.Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        for layer, text in outputs.items():
            (out / _FILENAMES[layer]).write_text(text, encoding="utf-8", newline="\n")
            print(f"wrote {out / _FILENAMES[layer]}")
    else:
        for layer, text in outputs.items():
            print(f"===== {layer} ({_FILENAMES[layer]}) =====\n{text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
