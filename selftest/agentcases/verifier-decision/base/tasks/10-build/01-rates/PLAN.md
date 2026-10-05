---
status: done
created: 2026-10-01
---
# rate storage

## Decisions
- D1 The rate is fetched from the external client before the database transaction opens; the transaction only writes, so no transaction stays open while the network call is in flight.

## Tasks
- [x] T01 store_rate — verify: `python3 -m unittest discover -s tests`

## Log
- 2026-10-01 T01: done, tests green.
