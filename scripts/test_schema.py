#!/usr/bin/env python3
"""Schema tests for tariffs-v1.schema.json (Batch D extensions).

Twelve cases:
  1.  hkn_cases[] accepts a well-formed entry (season + user_inputs)
  2.  hkn_cases[].rp_kwh: -0.5 rejected (minimum: 0)
  3.  bonus kind=additive_rp_kwh requires rate_rp_kwh
  4.  bonus kind=multiplier_pct requires multiplier_pct
  5.  bonus kind="wat" rejected (enum)
  6.  user_input type=enum requires values list
  7.  user_input type=boolean rejects string default
  8.  when_clause.season rejects "spring"
  9.  when_clause rejects unknown key (additionalProperties: false)
  10. applies_when_clause rejects nested-object value
  11. End-to-end: each Batch-D sample utility validates clean
  12. Integrity walk: every applies_when / when.user_inputs key in the dataset is
      declared in the same rate window's user_inputs[].key, and enum values match.
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "schemas" / "tariffs-v1.schema.json").read_text())
DATA = json.loads((ROOT / "tariffs.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA)


def _minimal_doc():
    return deepcopy({
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "schema_version": "1.1.0",
        "last_updated": "2026-04-28",
        "federal_minimum": [
            {
                "valid_from": "2026-01-01",
                "valid_to": None,
                "rules": [{"kw_min": 0, "kw_max": 30, "self_consumption": None, "min_rp_kwh": 6.0}],
            }
        ],
        "utilities": {
            "test_util": {
                "name_de": "Test",
                "homepage": "https://example.test",
                "rates": [
                    {
                        "valid_from": "2026-01-01",
                        "valid_to": None,
                        "settlement_period": "quartal",
                        "power_tiers": [
                            {
                                "kw_min": 0,
                                "kw_max": None,
                                "base_model": "rmp_quartal",
                                "hkn_rp_kwh": 2.0,
                                "hkn_structure": "additive_optin",
                            }
                        ],
                        "cap_mode": False,
                    }
                ],
            }
        },
    })


def _errors(doc) -> list[str]:
    return [e.message for e in VALIDATOR.iter_errors(doc)]


def _expect_valid(name, doc):
    errs = _errors(doc)
    if errs:
        raise AssertionError(f"{name}: expected valid, got {len(errs)} error(s):\n  - " + "\n  - ".join(errs))


def _expect_invalid(name, doc, needle: str | None = None):
    errs = _errors(doc)
    if not errs:
        raise AssertionError(f"{name}: expected validation error, got none")
    if needle is not None and not any(needle in e for e in errs):
        raise AssertionError(f"{name}: expected error containing {needle!r}, got: {errs}")


def case_01_hkn_cases_well_formed():
    doc = _minimal_doc()
    tier = doc["utilities"]["test_util"]["rates"][0]["power_tiers"][0]
    tier["hkn_cases"] = [
        {"when": {"season": "winter", "user_inputs": {"supply_product": True}}, "rp_kwh": 2.0}
    ]
    _expect_valid("01 hkn_cases well-formed", doc)


def case_02_hkn_cases_negative_rp_kwh():
    doc = _minimal_doc()
    tier = doc["utilities"]["test_util"]["rates"][0]["power_tiers"][0]
    tier["hkn_cases"] = [{"when": {"season": "winter"}, "rp_kwh": -0.5}]
    _expect_invalid("02 hkn_cases negative rp_kwh", doc, "less than the minimum")


def case_03_bonus_additive_requires_rate():
    doc = _minimal_doc()
    rate = doc["utilities"]["test_util"]["rates"][0]
    rate["bonuses"] = [{"kind": "additive_rp_kwh", "name": "X", "applies_when": "always"}]
    _expect_invalid("03 bonus additive missing rate_rp_kwh", doc, "rate_rp_kwh")


def case_04_bonus_multiplier_requires_multiplier_pct():
    doc = _minimal_doc()
    rate = doc["utilities"]["test_util"]["rates"][0]
    rate["bonuses"] = [{"kind": "multiplier_pct", "name": "X", "applies_when": "opt_in"}]
    _expect_invalid("04 bonus multiplier missing multiplier_pct", doc, "multiplier_pct")


def case_05_bonus_kind_enum_rejects_unknown():
    doc = _minimal_doc()
    rate = doc["utilities"]["test_util"]["rates"][0]
    rate["bonuses"] = [{"kind": "wat", "name": "X", "applies_when": "always"}]
    _expect_invalid("05 bonus kind=wat", doc, "'wat'")


def case_06_user_input_enum_requires_values():
    doc = _minimal_doc()
    rate = doc["utilities"]["test_util"]["rates"][0]
    rate["user_inputs"] = [
        {"key": "model", "type": "enum", "default": "a", "label_de": "Modell"}
    ]
    _expect_invalid("06 user_input enum without values", doc, "values")


def case_07_user_input_boolean_rejects_string_default():
    doc = _minimal_doc()
    rate = doc["utilities"]["test_util"]["rates"][0]
    rate["user_inputs"] = [
        {"key": "flag", "type": "boolean", "default": "yes", "label_de": "Flag"}
    ]
    _expect_invalid("07 user_input boolean string default", doc, "boolean")


def case_08_when_clause_rejects_invalid_season():
    doc = _minimal_doc()
    tier = doc["utilities"]["test_util"]["rates"][0]["power_tiers"][0]
    tier["hkn_cases"] = [{"when": {"season": "spring"}, "rp_kwh": 1.0}]
    _expect_invalid("08 when.season=spring", doc, "'spring'")


def case_09_when_clause_rejects_unknown_key():
    doc = _minimal_doc()
    tier = doc["utilities"]["test_util"]["rates"][0]["power_tiers"][0]
    tier["hkn_cases"] = [{"when": {"weekday": "mon"}, "rp_kwh": 1.0}]
    _expect_invalid("09 when unknown key", doc, "weekday")


def case_10_applies_when_rejects_nested_value():
    doc = _minimal_doc()
    tier = doc["utilities"]["test_util"]["rates"][0]["power_tiers"][0]
    tier["applies_when"] = {"tariff_model": {"nested": "x"}}
    _expect_invalid("10 applies_when nested value", doc, "valid under any of the given schemas")


def case_11_real_samples_validate():
    errs = list(VALIDATOR.iter_errors(DATA))
    if errs:
        msgs = "\n  - ".join(f"{'/'.join(map(str,e.absolute_path)) or '<root>'}: {e.message}" for e in errs[:5])
        raise AssertionError(f"11 real tariffs.json: {len(errs)} error(s)\n  - {msgs}")
    required = {"aew", "dkek_ebnat_kappel", "ewn_nidwalden", "regio_energie_solothurn"}
    missing = required - set(DATA["utilities"])
    if missing:
        raise AssertionError(f"11 real samples missing utilities: {missing}")


def _walk_user_input_refs(rate: dict) -> list[tuple[str, dict, dict]]:
    """Yield (location, when_or_applies_dict, declared_inputs_by_key) for each ref."""
    declared = {ui["key"]: ui for ui in rate.get("user_inputs", [])}
    refs = []
    for i, tier in enumerate(rate.get("power_tiers", [])):
        if "applies_when" in tier:
            refs.append((f"power_tiers[{i}].applies_when", tier["applies_when"], declared))
        for j, case in enumerate(tier.get("hkn_cases", [])):
            ui_match = case.get("when", {}).get("user_inputs")
            if ui_match:
                refs.append((f"power_tiers[{i}].hkn_cases[{j}].when.user_inputs", ui_match, declared))
    for k, bonus in enumerate(rate.get("bonuses", [])):
        ui_match = bonus.get("when", {}).get("user_inputs")
        if ui_match:
            refs.append((f"bonuses[{k}].when.user_inputs", ui_match, declared))
    return refs


def case_12_integrity_walk():
    failures = []
    for util_key, util in DATA["utilities"].items():
        for r_idx, rate in enumerate(util.get("rates", [])):
            for loc, ui_match, declared in _walk_user_input_refs(rate):
                for key, val in ui_match.items():
                    if key not in declared:
                        failures.append(f"{util_key}.rates[{r_idx}].{loc} references undeclared key '{key}'")
                        continue
                    decl = declared[key]
                    if decl["type"] == "enum":
                        if not isinstance(val, str) or val not in decl.get("values", []):
                            failures.append(
                                f"{util_key}.rates[{r_idx}].{loc}: key '{key}' value {val!r} "
                                f"not in declared values {decl.get('values')}"
                            )
                    elif decl["type"] == "boolean":
                        if not isinstance(val, bool):
                            failures.append(
                                f"{util_key}.rates[{r_idx}].{loc}: key '{key}' value {val!r} "
                                f"not a boolean (declared type=boolean)"
                            )
    if failures:
        raise AssertionError("12 integrity walk:\n  - " + "\n  - ".join(failures))


def case_13_tarif_urls_well_formed():
    doc = _minimal_doc()
    rate = doc["utilities"]["test_util"]["rates"][0]
    rate["tarif_urls"] = [
        {"url": "https://example.test/a.pdf",
         "label_de": "Energie", "kind": "pdf",
         "applies_when": {"tariff_model": "fixpreis"}},
        {"url": "https://example.test/b", "kind": "html"},
    ]
    _expect_valid("13 tarif_urls well-formed", doc)


def case_14_tarif_urls_rejects_missing_url():
    doc = _minimal_doc()
    rate = doc["utilities"]["test_util"]["rates"][0]
    rate["tarif_urls"] = [{"label_de": "no url here"}]
    _expect_invalid("14 tarif_urls missing url", doc, "url")


def case_15_user_input_value_labels_well_formed():
    doc = _minimal_doc()
    rate = doc["utilities"]["test_util"]["rates"][0]
    rate["user_inputs"] = [
        {"key": "tariff_model", "type": "enum",
         "values": ["fixpreis", "rmp"], "default": "fixpreis",
         "label_de": "Tarifmodell",
         "value_labels_de": {"fixpreis": "AEW Fixpreis",
                             "rmp": "Referenzmarktpreis"}},
    ]
    _expect_valid("15 user_input value_labels", doc)


CASES = [
    case_01_hkn_cases_well_formed,
    case_02_hkn_cases_negative_rp_kwh,
    case_03_bonus_additive_requires_rate,
    case_04_bonus_multiplier_requires_multiplier_pct,
    case_05_bonus_kind_enum_rejects_unknown,
    case_06_user_input_enum_requires_values,
    case_07_user_input_boolean_rejects_string_default,
    case_08_when_clause_rejects_invalid_season,
    case_09_when_clause_rejects_unknown_key,
    case_10_applies_when_rejects_nested_value,
    case_11_real_samples_validate,
    case_12_integrity_walk,
    case_13_tarif_urls_well_formed,
    case_14_tarif_urls_rejects_missing_url,
    case_15_user_input_value_labels_well_formed,
]


def main() -> int:
    Draft202012Validator.check_schema(SCHEMA)
    failed = 0
    for fn in CASES:
        try:
            fn()
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {fn.__name__}\n  {e}")
        else:
            print(f"PASS  {fn.__name__}")
    print()
    if failed:
        print(f"{failed}/{len(CASES)} failed")
        return 1
    print(f"{len(CASES)}/{len(CASES)} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
