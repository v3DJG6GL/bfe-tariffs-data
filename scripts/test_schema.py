#!/usr/bin/env python3
"""Schema tests for tariffs-v1.schema.json + curator lint.

Schema-invariant cases (synthetic docs, expect VALID/INVALID):
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
  13. tarif_urls[] well-formed (label + kind + applies_when)
  14. tarif_urls[] missing url rejected
  15. user_input.value_labels_de well-formed

Data-content cases (walk real tariffs.json, expect well-formed):
  11. End-to-end: each Batch-D sample utility validates clean
  12. Integrity walk: every applies_when / when.user_inputs key (in tiers,
      tier.hkn_cases, bonuses.when, AND tarif_urls.applies_when) is
      declared in the same rate window's user_inputs[].key, with enum
      values + boolean types matching the declaration
  16. No bonus carries forbidden `applies_when` field (v1.3.0+)
  17. No uncovered (kW × user_input combo) — runtime LookupError lint
  18. Rate windows + note dates: chronology + per-utility non-overlap
  19. power_tier.kw_min < kw_max strictly (or kw_max=null)
  20. ht_window: hours in [0,24], start<end, present iff base_model=fixed_ht_nt
  21. seasonal: summer_months ∪ winter_months == {1..12} disjointly
  22. HKN cascade: structure ↔ hkn_rp_kwh ↔ hkn_cases coherence
  23. user_input enum default ∈ values
  24. nr_elcom unique across utilities
  25. No legacy cap_mode field (v1.5.0+ hard-dropped)

Run: `python3 scripts/test_schema.py` (exits non-zero on any failure;
GitHub Actions wires this up via .github/workflows/validate.yml).
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
    rate["bonuses"] = [{"kind": "additive_rp_kwh", "name": "X"}]
    _expect_invalid("03 bonus additive missing rate_rp_kwh", doc, "rate_rp_kwh")


def case_04_bonus_multiplier_requires_multiplier_pct():
    doc = _minimal_doc()
    rate = doc["utilities"]["test_util"]["rates"][0]
    rate["bonuses"] = [{"kind": "multiplier_pct", "name": "X"}]
    _expect_invalid("04 bonus multiplier missing multiplier_pct", doc, "multiplier_pct")


def case_05_bonus_kind_enum_rejects_unknown():
    doc = _minimal_doc()
    rate = doc["utilities"]["test_util"]["rates"][0]
    rate["bonuses"] = [{"kind": "wat", "name": "X"}]
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
    """Yield (location, when_or_applies_dict, declared_inputs_by_key) for each
    user_input reference in the rate. Walks all clause sites:
    power_tiers.applies_when, power_tiers.hkn_cases[].when.user_inputs,
    power_tiers.bonuses[].when.user_inputs (v1.5.0+),
    bonuses[].when.user_inputs, tarif_urls[].applies_when."""
    declared = {ui["key"]: ui for ui in rate.get("user_inputs", [])}
    refs = []
    for i, tier in enumerate(rate.get("power_tiers", [])):
        if "applies_when" in tier:
            refs.append((f"power_tiers[{i}].applies_when", tier["applies_when"], declared))
        for j, case in enumerate(tier.get("hkn_cases", [])):
            ui_match = case.get("when", {}).get("user_inputs")
            if ui_match:
                refs.append((f"power_tiers[{i}].hkn_cases[{j}].when.user_inputs", ui_match, declared))
        for k, bonus in enumerate(tier.get("bonuses", []) or []):
            ui_match = bonus.get("when", {}).get("user_inputs")
            if ui_match:
                refs.append((f"power_tiers[{i}].bonuses[{k}].when.user_inputs", ui_match, declared))
    for k, bonus in enumerate(rate.get("bonuses", [])):
        ui_match = bonus.get("when", {}).get("user_inputs")
        if ui_match:
            refs.append((f"bonuses[{k}].when.user_inputs", ui_match, declared))
    for m, entry in enumerate(rate.get("tarif_urls", []) or []):
        aw = entry.get("applies_when")
        if aw:
            refs.append((f"tarif_urls[{m}].applies_when", aw, declared))
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


def case_16_no_bonus_carries_applies_when():
    """v1.3.0+ schema: bonus.applies_when is dropped. Defend against
    re-introduction in tariffs.json — opt-in bonuses must be gated via
    a `when.user_inputs.<key>: true` clause backed by a declared
    user_inputs[] boolean. v1.5.0+ extends scope to tier-level bonuses."""
    failures = []
    for util_key, util in DATA["utilities"].items():
        for r_idx, rate in enumerate(util.get("rates", [])):
            for b_idx, bonus in enumerate(rate.get("bonuses", [])):
                if "applies_when" in bonus:
                    failures.append(
                        f"{util_key}.rates[{r_idx}].bonuses[{b_idx}] "
                        f"carries forbidden 'applies_when' field"
                    )
            for t_idx, tier in enumerate(rate.get("power_tiers", [])):
                for b_idx, bonus in enumerate(tier.get("bonuses", []) or []):
                    if "applies_when" in bonus:
                        failures.append(
                            f"{util_key}.rates[{r_idx}].power_tiers[{t_idx}]."
                            f"bonuses[{b_idx}] carries forbidden 'applies_when' field"
                        )
    if failures:
        raise AssertionError(
            "16 no-bonus-applies_when:\n  - " + "\n  - ".join(failures)
        )


# Vendored from
# bfe_rueckliefertarif/custom_components/bfe_rueckliefertarif/tariffs_db.py:207-238
# — kept in lock-step with the integration's resolver. Update if upstream
# semantics change.
def _find_tier_for(tiers, kw, user_inputs):
    ui = user_inputs or {}
    fallback = None
    for t in tiers:
        kw_max = t["kw_max"] if t["kw_max"] is not None else float("inf")
        if not (t["kw_min"] <= kw < kw_max):
            continue
        clause = t.get("applies_when")
        if clause:
            if all(ui.get(k) == v for k, v in clause.items()):
                return t
        else:
            if fallback is None:
                fallback = t
    return fallback


def _enumerate_combos(user_inputs):
    """Cartesian of all (key→value) combos a user could pick."""
    if not user_inputs:
        return [{}]
    import itertools
    keys, value_lists = [], []
    for ui in user_inputs:
        keys.append(ui["key"])
        if ui["type"] == "enum":
            value_lists.append(list(ui["values"]))
        elif ui["type"] == "boolean":
            value_lists.append([True, False])
        else:
            value_lists.append([ui.get("default")])
    return [dict(zip(keys, vals)) for vals in itertools.product(*value_lists)]


def _kw_probe_set(tiers):
    """One probe per tier boundary, plus 0.0 and 9999.0."""
    probes = {0.0, 9999.0}
    for t in tiers:
        probes.add(float(t["kw_min"]))
        if t["kw_max"] is not None:
            probes.add(float(t["kw_max"]) - 0.0001)
        else:
            probes.add(float(t["kw_min"]) + 1.0)
    return sorted(probes)


def _kw_in_any_band(tiers, kw):
    return any(
        t["kw_min"] <= kw < (t["kw_max"] if t["kw_max"] is not None else float("inf"))
        for t in tiers
    )


def _combo_effective_bands(tiers, combo):
    """Return list of (kw_min, kw_max) bands where `combo` would resolve
    a tier — tiers whose `applies_when` matches the combo, plus no-clause
    tiers. Empty list = combo never resolves at any kW (curator forgot a
    value)."""
    bands = []
    for t in tiers:
        clause = t.get("applies_when") or {}
        if not clause or all(combo.get(k) == v for k, v in clause.items()):
            bands.append((t["kw_min"], t["kw_max"]))
    return bands


def _kw_in_bands(bands, kw):
    return any(
        kmin <= kw < (kmax if kmax is not None else float("inf"))
        for kmin, kmax in bands
    )


def case_17_no_uncovered_kw_user_input_combinations():
    """For every declared user_input combo:

    (a) The combo must have a non-empty *effective kW domain* — at least
        one tier in the rate must carry an `applies_when` that matches
        it (or no clause at all). An empty domain means the curator
        declared a value (e.g. `mode=b`) without giving any tier for
        it — runtime would always raise LookupError when the user picks
        it. Real curator error.

    (b) For every kW probe inside the combo's effective domain,
        `find_tier_for` must resolve. Catches gaps within the declared
        coverage (overlapping clauses, missing fallback, etc.).

    Combos OUTSIDE their effective domain are intentional: the curator
    scoped them via `applies_when` + `kw_max` (e.g. AEW Fixpreis ≤30 kW
    only), and the integration filters them out at render time. We don't
    flag those — they're a UX shape, not a runtime hole."""
    failures = []
    for util_key, util in DATA["utilities"].items():
        for r_idx, rate in enumerate(util.get("rates", [])):
            tiers = rate.get("power_tiers", [])
            if not tiers:
                continue
            combos = _enumerate_combos(rate.get("user_inputs", []))
            for combo in combos:
                eff_bands = _combo_effective_bands(tiers, combo)
                if not eff_bands:
                    failures.append(
                        f"{util_key}.rates[{r_idx}] combo={combo}: "
                        f"declared in user_inputs but no tier matches "
                        f"at any kW (curator forgot a value)"
                    )
                    continue
                for kw in _kw_probe_set(tiers):
                    if not _kw_in_any_band(tiers, kw):
                        continue
                    if not _kw_in_bands(eff_bands, kw):
                        continue
                    if _find_tier_for(tiers, kw, combo) is None:
                        failures.append(
                            f"{util_key}.rates[{r_idx}] @ kW={kw} "
                            f"combo={combo}: no tier resolves"
                        )
    if failures:
        raise AssertionError(
            "17 uncovered kW×user_input combos:\n  - " + "\n  - ".join(failures)
        )


def case_18_rate_window_chronology():
    """Rate windows: valid_from < valid_to (or valid_to=null) per rate;
    no per-utility overlap. Note dates inside each rate follow the same
    half-open rule. Inverted/overlapping windows silently misbehave in
    `find_active`."""
    from datetime import date
    failures = []
    for util_key, util in DATA["utilities"].items():
        ranges = []
        for r_idx, rate in enumerate(util.get("rates", [])):
            f_str = rate.get("valid_from")
            t_str = rate.get("valid_to")
            try:
                f = date.fromisoformat(f_str)
            except (TypeError, ValueError):
                failures.append(f"{util_key}.rates[{r_idx}]: invalid valid_from {f_str!r}")
                continue
            t = date.fromisoformat(t_str) if t_str else date.max
            if t_str is not None and not (f < t):
                failures.append(
                    f"{util_key}.rates[{r_idx}]: valid_from {f_str} >= valid_to {t_str}"
                )
            ranges.append((f, t, r_idx))
            for n_idx, note in enumerate(rate.get("notes", []) or []):
                nf = note.get("valid_from")
                nt = note.get("valid_to")
                if nf and nt:
                    try:
                        if not (date.fromisoformat(nf) < date.fromisoformat(nt)):
                            failures.append(
                                f"{util_key}.rates[{r_idx}].notes[{n_idx}]: "
                                f"valid_from {nf} >= valid_to {nt}"
                            )
                    except ValueError:
                        pass
        ranges.sort()
        for i in range(len(ranges) - 1):
            f1, t1, i1 = ranges[i]
            f2, t2, i2 = ranges[i + 1]
            if f2 < t1:
                failures.append(
                    f"{util_key}.rates: [{i1}] [{f1}..{t1}) overlaps "
                    f"[{i2}] [{f2}..{t2})"
                )
    if failures:
        raise AssertionError("18 rate-window chronology:\n  - " + "\n  - ".join(failures))


def case_19_power_tier_kw_bounds_valid():
    """Every power_tier has kw_min < kw_max (or kw_max=null). Inverted
    or empty bands `[kw_min, kw_max)` never match in `find_tier_for`."""
    failures = []
    for util_key, util in DATA["utilities"].items():
        for r_idx, rate in enumerate(util.get("rates", [])):
            for t_idx, tier in enumerate(rate.get("power_tiers", [])):
                kw_min = tier.get("kw_min")
                kw_max = tier.get("kw_max")
                if kw_min is None:
                    failures.append(
                        f"{util_key}.rates[{r_idx}].power_tiers[{t_idx}]: kw_min is null"
                    )
                    continue
                if kw_min < 0:
                    failures.append(
                        f"{util_key}.rates[{r_idx}].power_tiers[{t_idx}]: "
                        f"kw_min={kw_min} < 0"
                    )
                if kw_max is not None and not (kw_min < kw_max):
                    failures.append(
                        f"{util_key}.rates[{r_idx}].power_tiers[{t_idx}]: "
                        f"kw_min={kw_min} >= kw_max={kw_max}"
                    )
    if failures:
        raise AssertionError("19 power_tier kw bounds:\n  - " + "\n  - ".join(failures))


def case_20_ht_window_consistency():
    """ht_window: hours ∈ [0,24], start<end strictly per day-group, and
    presence aligned with base_model. Missing on fixed_ht_nt → silent
    NT-always; present on other base_models → flag as smell."""
    failures = []
    for util_key, util in DATA["utilities"].items():
        for r_idx, rate in enumerate(util.get("rates", [])):
            for t_idx, tier in enumerate(rate.get("power_tiers", [])):
                base = tier.get("base_model")
                hw = tier.get("ht_window")
                loc = f"{util_key}.rates[{r_idx}].power_tiers[{t_idx}]"
                if base == "fixed_ht_nt" and hw is None:
                    failures.append(f"{loc}: base_model=fixed_ht_nt missing ht_window")
                    continue
                if base != "fixed_ht_nt" and hw is not None:
                    failures.append(
                        f"{loc}: ht_window present but base_model={base!r} (smell)"
                    )
                if not isinstance(hw, dict):
                    continue
                for day_key in ("mofr", "sa", "su"):
                    win = hw.get(day_key)
                    if win is None:
                        continue
                    if not (isinstance(win, list) and len(win) == 2):
                        failures.append(
                            f"{loc}.ht_window.{day_key}: not a 2-element list"
                        )
                        continue
                    s, e = win
                    if not (0 <= s <= 24 and 0 <= e <= 24):
                        failures.append(
                            f"{loc}.ht_window.{day_key}: hours out of [0,24]: [{s},{e}]"
                        )
                    if not (s < e):
                        failures.append(
                            f"{loc}.ht_window.{day_key}: start {s} >= end {e}"
                        )
    if failures:
        raise AssertionError("20 ht_window consistency:\n  - " + "\n  - ".join(failures))


def case_21_seasonal_month_coverage():
    """seasonal.summer_months ∪ winter_months must equal {1..12} with
    no overlap. Gaps → ValueError mid-resolve in classify_season;
    overlaps → summer silently wins (first check). v1.5.0+ extends to
    tier-level `power_tiers[*].seasonal` blocks too."""
    failures = []

    def _check(seasonal, loc):
        summer = set(seasonal.get("summer_months") or [])
        winter = set(seasonal.get("winter_months") or [])
        full = summer | winter
        missing = set(range(1, 13)) - full
        overlap = summer & winter
        if missing:
            failures.append(f"{loc}: months {sorted(missing)} not in summer or winter")
        if overlap:
            failures.append(f"{loc}: months {sorted(overlap)} in both summer and winter")

    for util_key, util in DATA["utilities"].items():
        for r_idx, rate in enumerate(util.get("rates", [])):
            seasonal = rate.get("seasonal")
            if seasonal:
                _check(seasonal, f"{util_key}.rates[{r_idx}].seasonal")
            for t_idx, tier in enumerate(rate.get("power_tiers", [])):
                tier_seasonal = tier.get("seasonal")
                if tier_seasonal:
                    _check(
                        tier_seasonal,
                        f"{util_key}.rates[{r_idx}].power_tiers[{t_idx}].seasonal",
                    )
    if failures:
        raise AssertionError("21 seasonal month coverage:\n  - " + "\n  - ".join(failures))


def case_22_hkn_structure_consistency():
    """HKN cascade: hkn_structure ↔ hkn_rp_kwh ↔ hkn_cases coherence.
    - 'additive_optin' → hkn_rp_kwh is set (number) OR hkn_cases is non-empty.
    - 'bundled' / 'none' → hkn_rp_kwh is null AND no hkn_cases.
    Drift is silently ignored at runtime (importer.py:140-141).

    v1.5.0+ allows tier `hkn_structure` / `hkn_rp_kwh` to be omitted; in
    that case rate-level `hkn_structure_default` / `hkn_rp_kwh_default`
    fill in. Both defaults must be set together (or both omitted)."""
    failures = []
    for util_key, util in DATA["utilities"].items():
        for r_idx, rate in enumerate(util.get("rates", [])):
            rate_struct = rate.get("hkn_structure_default")
            rate_rp = rate.get("hkn_rp_kwh_default", "MISSING")
            rate_loc = f"{util_key}.rates[{r_idx}]"
            # rate-level defaults: pair check
            if (rate_struct is None) != (rate_rp == "MISSING"):
                # one set, other not
                failures.append(
                    f"{rate_loc}: hkn_structure_default and hkn_rp_kwh_default "
                    f"must be set together (got struct={rate_struct!r}, "
                    f"rp_kwh_default={'<unset>' if rate_rp == 'MISSING' else rate_rp})"
                )
            for t_idx, tier in enumerate(rate.get("power_tiers", [])):
                struct = tier.get("hkn_structure", rate_struct)
                rp = tier.get("hkn_rp_kwh", rate_rp if rate_rp != "MISSING" else None)
                cases = tier.get("hkn_cases") or []
                loc = f"{util_key}.rates[{r_idx}].power_tiers[{t_idx}]"
                if struct is None:
                    failures.append(
                        f"{loc}: no hkn_structure on tier and no rate-level default"
                    )
                    continue
                if struct == "additive_optin":
                    if rp is None and not cases:
                        failures.append(
                            f"{loc}: hkn_structure=additive_optin but neither "
                            f"hkn_rp_kwh nor hkn_cases set (and no rate-level default)"
                        )
                elif struct in ("bundled", "none"):
                    if rp is not None:
                        failures.append(
                            f"{loc}: hkn_structure={struct!r} but hkn_rp_kwh={rp} "
                            f"(should be null; runtime ignores it)"
                        )
                    if cases:
                        failures.append(
                            f"{loc}: hkn_structure={struct!r} but hkn_cases set "
                            f"(runtime ignores them)"
                        )
    if failures:
        raise AssertionError("22 hkn cascade:\n  - " + "\n  - ".join(failures))


def case_23_user_input_default_in_values():
    """For every declared user_input with type=enum, default must be in
    values. Schema's allOf checks the type but not list membership."""
    failures = []
    for util_key, util in DATA["utilities"].items():
        for r_idx, rate in enumerate(util.get("rates", [])):
            for ui_idx, ui in enumerate(rate.get("user_inputs", []) or []):
                if ui.get("type") != "enum":
                    continue
                values = ui.get("values") or []
                default = ui.get("default")
                if default not in values:
                    failures.append(
                        f"{util_key}.rates[{r_idx}].user_inputs[{ui_idx}] "
                        f"({ui.get('key')!r}): default {default!r} not in {values}"
                    )
    if failures:
        raise AssertionError("23 user_input default in values:\n  - " + "\n  - ".join(failures))


def case_24_nr_elcom_unique_across_utilities():
    """No two utilities share the same nr_elcom. The importer's override
    bucket is keyed by str(nr_elcom) — collisions silently mash overrides
    from one utility onto another."""
    seen: dict[str, str] = {}
    failures = []
    for util_key, util in DATA["utilities"].items():
        nr = util.get("nr_elcom")
        if nr in (None, ""):
            continue
        nr_str = str(nr)
        if nr_str in seen:
            failures.append(
                f"nr_elcom={nr_str!r} on both {seen[nr_str]!r} and {util_key!r}"
            )
        else:
            seen[nr_str] = util_key
    if failures:
        raise AssertionError("24 nr_elcom uniqueness:\n  - " + "\n  - ".join(failures))


def case_25_no_legacy_cap_mode():
    """v1.5.0 hard-drops `cap_mode` from the schema. Lint against
    re-introduction in tariffs.json — cap activation is now inferred
    from `cap_rules` (null/[] ⇒ no cap, non-empty ⇒ cap active)."""
    failures = []
    for util_key, util in DATA["utilities"].items():
        for r_idx, rate in enumerate(util.get("rates", [])):
            if "cap_mode" in rate:
                failures.append(
                    f"{util_key}.rates[{r_idx}] carries legacy 'cap_mode' field"
                )
    if failures:
        raise AssertionError(
            "25 no legacy cap_mode:\n  - " + "\n  - ".join(failures)
        )


def case_26_tier_seasonal_coherence_with_base_model():
    """v1.6.0: tier-level `seasonal` is the source of truth ONLY when
    `base_model = fixed_seasonal`. Inverse: every `fixed_seasonal`
    tier MUST carry a non-null seasonal block. Mirrors the schema's
    `power_tier.allOf` clause at data-lint level so a stray tier-
    seasonal block on (e.g.) `rmp_quartal` fails CI immediately."""
    failures = []
    for util_key, util in DATA["utilities"].items():
        for r_idx, rate in enumerate(util.get("rates", [])):
            for t_idx, tier in enumerate(rate.get("power_tiers", [])):
                base = tier.get("base_model")
                tier_seasonal = tier.get("seasonal")
                loc = f"{util_key}.rates[{r_idx}].power_tiers[{t_idx}]"
                if tier_seasonal is not None and base != "fixed_seasonal":
                    failures.append(
                        f"{loc}: tier-level seasonal but "
                        f"base_model={base!r} (must be fixed_seasonal)"
                    )
                if base == "fixed_seasonal" and tier_seasonal is None:
                    failures.append(
                        f"{loc}: base_model=fixed_seasonal but "
                        f"seasonal is null (required)"
                    )
    if failures:
        raise AssertionError(
            "26 tier seasonal coherence:\n  - " + "\n  - ".join(failures)
        )


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
    case_16_no_bonus_carries_applies_when,
    case_17_no_uncovered_kw_user_input_combinations,
    case_18_rate_window_chronology,
    case_19_power_tier_kw_bounds_valid,
    case_20_ht_window_consistency,
    case_21_seasonal_month_coverage,
    case_22_hkn_structure_consistency,
    case_23_user_input_default_in_values,
    case_24_nr_elcom_unique_across_utilities,
    case_25_no_legacy_cap_mode,
    case_26_tier_seasonal_coherence_with_base_model,
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
