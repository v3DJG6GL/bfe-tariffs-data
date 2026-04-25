# bfe-tariffs-data

Community-maintained Swiss PV feed-in tariff database for the
[ha-bfe-rueckliefertarif](https://github.com/v3DJG6GL/ha-bfe-rueckliefertarif)
Home Assistant integration.

## What's here

- `tariffs.json` — utility-specific tariffs + federal Mindestvergütung
  floors per [EnV Art. 12 Abs. 1bis (AS 2025 138)](https://www.fedlex.admin.ch/eli/cc/2017/763/de#art_12).
  Date-versioned via half-open `[valid_from, valid_to)` intervals so each
  yearly utility update appends a new record without editing past data.
- `schemas/tariffs-v1.schema.json` — JSON Schema (Draft 2020-12) the
  integration validates against on every fetch. Schema bumps are versioned
  via `schema_version` (semver).

## How the integration consumes this

The integration fetches `tariffs.json` daily from `raw.githubusercontent.com`,
validates against the bundled schema, caches in `<config>/.storage/`, and
falls back to its own bundled copy on any failure (network or schema
violation). Manual refresh: `bfe_rueckliefertarif.refresh_tariffs` service.

## Adding or updating a utility

1. Find your utility's published 2026+ Rückliefertarif (Tarifblatt PDF,
   utility website, or [VESE pvtarif](https://opendata.vese.ch/pvtarif)).
2. Edit `tariffs.json`:
   - **New utility:** add a new top-level entry under `utilities` with
     `name_de`, `homepage`, and a single `rates[0]` record carrying
     `valid_from: "2026-01-01"`, `valid_to: null`, the `power_tiers`
     pricing model, and `cap_mode` (`true` only for utilities that
     enforce the StromVV Art. 4 cost-recovery ceiling on producer
     payments — EKZ, Groupe E, Primeo today).
   - **Yearly update for an existing utility:** close the prior record's
     `valid_to` to the new year start, append a new open-ended record.
3. Bump `last_updated` to today's ISO date.
4. Validate locally:
   ```
   python3 -c "import json,jsonschema; jsonschema.Draft202012Validator(json.load(open('schemas/tariffs-v1.schema.json'))).validate(json.load(open('tariffs.json')))"
   ```
5. Open a PR.

## Sources

- **Federal floor:** [EnV Art. 12 Abs. 1bis (SR 730.01)](https://www.fedlex.admin.ch/eli/cc/2017/763/de#art_12)
  introduced by AS 2025 138, in force 1.1.2026.
- **Cost-recovery ceiling formula:** [StromVV Art. 4 Abs. 3 Bst. e (SR 734.71)](https://www.fedlex.admin.ch/eli/cc/2008/226/de#art_4)
  per AS 2025 139.
- **BFE reference market price (RMP):** [SFOE / opendata.swiss](https://opendata.swiss/de/dataset/referenz-marktpreise-gemass-art-15-enfv).

## License

MIT — see [LICENSE](./LICENSE).
