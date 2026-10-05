# reference.md

PostgreSQL facts behind the two questions, checked against the documentation of version 17 (16 where it differs), retrieved 2026-10-06. Every finding cites the line it rests on; nothing here is from memory.

## Why a long transaction hurts the whole database

- A long-open transaction holds back the xmin horizon; VACUUM cannot remove dead row versions newer than it, so tables and indexes bloat. The wraparound recovery steps tell you to find such sessions by `age(backend_xmin)` in `pg_stat_activity` and commit, roll back or terminate them — https://www.postgresql.org/docs/17/routine-vacuuming.html
- Transaction IDs are 32-bit. Near the limit the server warns ("must be vacuumed within N transactions"); with fewer than about three million left it refuses to assign new transaction IDs until VACUUM runs — https://www.postgresql.org/docs/17/routine-vacuuming.html
- Recovery from wraparound is VACUUM in normal multi-user mode; single-user mode "is no longer necessary, and should be avoided whenever possible" (same text in 16) — https://www.postgresql.org/docs/16/routine-vacuuming.html
- Replication slots and `hot_standby_feedback` hold back the same horizon from a standby, even a disconnected one for slots — https://www.postgresql.org/docs/17/warm-standby.html
- While the transaction waits on something outside the database, its connection is taken from the pool and every row it already changed stays locked for other writers; under load the pool runs out before the database shows any symptom — https://www.postgresql.org/docs/17/explicit-locking.html

## Locks that turn one slow statement into an outage

- Any read takes ACCESS SHARE, which conflicts only with ACCESS EXCLUSIVE; many forms of ALTER TABLE take ACCESS EXCLUSIVE — https://www.postgresql.org/docs/17/explicit-locking.html
- An ALTER TABLE waiting behind a long transaction holds its place in the lock queue, and later ordinary queries on that table wait behind it (Tom Lane, pgsql-general, "Problem running ALTER TABLE…, ALTER TABLE waiting", 2012; quoted by the collector, thread title confirmed) — https://www.postgresql.org/message-id/27601.1344473932%40sss.pgh.pa.us
- Plain CREATE INDEX blocks writes but not reads, so a long SELECT does not block it — https://www.postgresql.org/docs/17/sql-createindex.html
- CREATE INDEX CONCURRENTLY waits for every existing transaction that could use the index and, after its second scan, for every snapshot older than that scan: a long transaction stalls it — https://www.postgresql.org/docs/17/sql-createindex.html

## Settings that cap the damage

- `statement_timeout`, `idle_in_transaction_session_timeout` (both 0 = off by default) and `transaction_timeout`, which also covers single-statement implicit transactions — https://www.postgresql.org/docs/17/runtime-config-client.html
- `transaction_timeout` exists from version 17; 16 has only the first two — https://www.postgresql.org/docs/17/release-17.html

## Transactions a driver opens without being asked

- psycopg2 without autocommit: the first command opens a transaction, and "even a simple SELECT will start a transaction"; the session stays idle in transaction until commit or rollback — https://www.psycopg.org/docs/usage.html
- psycopg 3: not autocommit by default; any operation starts a transaction that lasts until commit() or rollback() — https://www.psycopg.org/psycopg3/docs/basic/transactions.html
- SQLAlchemy 2.0 Session autobegins a transaction on the first operation; it lasts until commit(), rollback() or close() — https://docs.sqlalchemy.org/en/20/orm/session_transaction.html
- pgjdbc with `autoCommit=false`: statements run inside one transaction until commit or rollback (server-side cursors rely on it); the page does not say it in one sentence, it follows from JDBC semantics — https://jdbc.postgresql.org/documentation/query/

## Indexes the planner cannot use, or that do not exist

- A foreign key does not create an index on the referencing columns; the documentation recommends adding one — https://www.postgresql.org/docs/17/ddl-constraints.html
- `WHERE lower(col) = …` needs an index on `lower(col)`; an index on `col` is not used — https://www.postgresql.org/docs/17/indexes-expressional.html
- A B-tree serves `LIKE 'foo%'` but not `LIKE '%bar'` — https://www.postgresql.org/docs/17/indexes-types.html
- Outside the C locale, prefix `LIKE` needs `text_pattern_ops` / `varchar_pattern_ops` / `bpchar_pattern_ops`, and those do not serve ordinary `<`, `>` comparisons — https://www.postgresql.org/docs/17/indexes-opclass.html

## Looking at a live database, read-only

- `EXPLAIN` only plans; `EXPLAIN ANALYZE` executes the statement, side effects included — never on data-changing statements outside `BEGIN; … ROLLBACK;`, never on production — https://www.postgresql.org/docs/17/sql-explain.html
- `pg_stat_activity`: `state = 'idle in transaction'`, `xact_start`, `backend_xmin`; `pg_stat_user_tables`: `seq_scan` against `idx_scan` — https://www.postgresql.org/docs/17/monitoring-stats.html

## Removed from the original note

- "The planner cannot re-plan mid-query, so long queries are dangerous": no official source ties it to long transactions; Tom Lane explains it only as a general limit of the executor — https://www.postgresql.org/message-id/4276.1510613373%40sss.pgh.pa.us
