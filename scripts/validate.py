#!/usr/bin/env python3
"""Validate tariffs.json against the bundled JSON Schema."""
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
schema = json.loads((ROOT / "schemas" / "tariffs-v1.schema.json").read_text())
data = json.loads((ROOT / "tariffs.json").read_text())

Draft202012Validator.check_schema(schema)
errors = sorted(
    Draft202012Validator(schema).iter_errors(data),
    key=lambda e: list(e.absolute_path),
)
for e in errors:
    path = "/".join(map(str, e.absolute_path)) or "<root>"
    print(f"  {path}: {e.message}")

if errors:
    print(f"\n{len(errors)} validation error(s)")
    sys.exit(1)

print(f"OK — {len(data['utilities'])} utilities, schema_version {data['schema_version']}")
