# Data contracts

`datasets/schema.json` is generated from Pydantic. Unknown fields, duplicate IDs, unknown references, naive timestamps, overlapping section windows, invalid horizons and cyclic dependencies are rejected before persistence. Each dataset carries schema version 1, name, synthetic flag, seed when applicable, timezone-aware epoch, 15-minute slot size and a bounded horizon.

- **Section:** ID, display name, station endpoints, disjoint possession windows.
- **Task:** ID, title, ENG/TRD/SNT department, section ID, activity code, integer duration, release and deadline, priority 1–10, required flag, resource demands and predecessor IDs.
- **Train:** unique occupation ID, section ID, half-open interval. Multiple occupations on different sections should use separate IDs even for one train service.
- **Resource:** ID, display name, constant nonnegative capacity.
- **Compatibility:** symmetric activity pairs, explicit allowlist. Missing pairs prohibit simultaneous work on a section.

The JSON dataset is the canonical round-trip import/export format. CSV files are generated for source mapping demonstrations; the API does not pretend to connect to proprietary source systems or infer ambiguous CSV units.

| Synthetic output | Intended mapping |
|---|---|
| assets.csv | Section/station inventory |
| tms.csv | Engineering maintenance demand |
| smms.csv | Signal and telecom demand |
| tdms.csv | Traction distribution demand |
| coa.csv | Section possession windows |
| trains.csv | Train section occupations |
| resources.csv | Crew pool capacities |
| dataset.json | Complete validated source of truth including epoch and compatibility |

Nested CSV fields use JSON encoding. Preserve `dataset.json` alongside CSV exports for metadata, units and compatibility. Goods forecasting is not synthesized as an authoritative prediction; train occupations are explicit deterministic inputs. Synthetic station names describe illustrative topology, not verified sectional geography or actual possession rights.

## Example API use

```bash
curl -s http://localhost:8000/api/v1/datasets/generate \
  -H 'Content-Type: application/json' \
  -d '{"seed":42,"sections":4,"tasks":24,"trains":28,"days":28}'

curl -s http://localhost:8000/api/v1/jobs \
  -H 'Content-Type: application/json' \
  -d '{"dataset_id":"ID_FROM_PREVIOUS_RESPONSE","kind":"monthly"}'
```

When authentication is enabled, send `Authorization: Bearer <deployment key>`. Poll the returned job ID. Copy the monthly result's `commitments` into `options.commitments` of an `optimize` job. For recovery, use `kind: recovery`, a `parent_job_id`, `disruption: {kind: task_overrun, magnitude: 2, target_id: ENG-001}` and optional `options.locked_task_ids`. The browser handles these contracts.
