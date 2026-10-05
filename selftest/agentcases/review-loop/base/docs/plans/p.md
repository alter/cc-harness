---
status: running
created: 2026-10-01
---
# rates

## Goal
Store exchange rates.

## Acceptance criteria
- [ ] AC1 rates stored — `python3 -m unittest discover -s tests`

## Decisions
- D1 Rates are stored as text exactly as the provider returns them; no numeric conversion in this service (the billing service converts).

## Assumptions

## Out of scope
- Billing.

## Tasks
- [x] T01 store_rate — verify: `python3 -m unittest discover -s tests`
- [ ] T02 docs — verify: `test -f docs/rates.md`

## Log
- 2026-10-01 T01 done.
