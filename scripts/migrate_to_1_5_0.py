"""One-shot migration: schema 1.4.0 -> 1.5.0.

Three changes:

1. Strip `cap_mode` from every rate (field hard-dropped from schema).
2. HKN dedupe: where every power_tier in a rate shares the same
   `hkn_structure` AND `hkn_rp_kwh`, write rate-level
   `hkn_structure_default` + `hkn_rp_kwh_default` and clear those
   fields from each tier. Otherwise leave per-tier values untouched.
3. Bump `schema_version` to 1.5.0.

Usage:
    python scripts/migrate_to_1_5_0.py [path/to/tariffs.json]

Default path is ./tariffs.json relative to repo root.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


NEW_SCHEMA_VERSION = "1.5.0"


def migrate(data: dict) -> dict:
    """In-place mutation. Returns the same dict for ergonomics."""
    data["schema_version"] = NEW_SCHEMA_VERSION
    utilities = data.get("utilities") or {}
    cap_stripped = 0
    hkn_deduped = 0
    for util in utilities.values():
        for rate in util.get("rates") or []:
            if "cap_mode" in rate:
                del rate["cap_mode"]
                cap_stripped += 1

            tiers = rate.get("power_tiers") or []
            if not tiers:
                continue
            seen: set[tuple] = set()
            for tier in tiers:
                seen.add((tier.get("hkn_structure"), tier.get("hkn_rp_kwh")))
            if len(seen) != 1:
                continue
            structure, rp_kwh = next(iter(seen))
            if structure is None and rp_kwh is None:
                continue
            rate["hkn_structure_default"] = structure
            rate["hkn_rp_kwh_default"] = rp_kwh
            for tier in tiers:
                tier.pop("hkn_structure", None)
                tier.pop("hkn_rp_kwh", None)
            hkn_deduped += 1
    print(f"  cap_mode keys stripped: {cap_stripped}")
    print(f"  rates HKN-deduped:      {hkn_deduped}")
    return data


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tariffs.json")
    if not path.exists():
        print(f"file not found: {path}", file=sys.stderr)
        return 1
    print(f"migrating {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    migrate(data)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"  schema_version -> {NEW_SCHEMA_VERSION}")
    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
