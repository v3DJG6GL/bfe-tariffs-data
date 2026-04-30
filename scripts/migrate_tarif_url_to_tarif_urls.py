"""One-shot migration: tarif_url (string) -> tarif_urls (array of dicts).

Schema bump 1.1.x -> 1.2.0 (Batch BB).

Walks every utility.rates[] entry and converts a top-level `tarif_url`
string into a `tarif_urls` array. Empty/null values become `[]`.
Labels / kind / applies_when fields are NOT inferred — the curator
authors them later via the importer UI.

Usage:
    python scripts/migrate_tarif_url_to_tarif_urls.py [path/to/tariffs.json]

Default path is ./tariffs.json relative to repo root.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


NEW_SCHEMA_VERSION = "1.2.0"


def migrate(data: dict) -> dict:
    """In-place mutation. Returns the same dict for ergonomics."""
    data["schema_version"] = NEW_SCHEMA_VERSION
    utilities = data.get("utilities") or {}
    converted = 0
    cleared = 0
    for util in utilities.values():
        for rate in util.get("rates") or []:
            if "tarif_url" not in rate:
                continue
            old = rate.pop("tarif_url")
            if isinstance(old, str) and old.strip():
                rate["tarif_urls"] = [{"url": old.strip()}]
                converted += 1
            else:
                rate["tarif_urls"] = []
                cleared += 1
    print(
        f"converted {converted} tarif_url -> tarif_urls entries; "
        f"cleared {cleared} empty/null entries"
    )
    return data


def main(argv: list[str]) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    target = Path(argv[1]) if len(argv) > 1 else repo_root / "tariffs.json"
    if not target.exists():
        print(f"ERROR: {target} not found", file=sys.stderr)
        return 1
    data = json.loads(target.read_text(encoding="utf-8"))
    migrate(data)
    target.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
