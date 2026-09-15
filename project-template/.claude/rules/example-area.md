---
paths:
  - "src/db/**"
  - "alembic/**"
---
# Database layer

- Sessions come from `src/db/session.py`; never open a connection elsewhere.
- Schema changes go through `alembic revision --autogenerate`; never edit a generated migration by hand.
- Timestamps are naive UTC in the database; convert at the API boundary only.
