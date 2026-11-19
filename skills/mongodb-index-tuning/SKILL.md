---
name: mongodb-index-tuning
description: Find slow MongoDB queries with the profiler, slow-query logs or Atlas Performance Advisor, read explain("executionStats") output, and add the right compound, partial or covering index using the Equality-Sort-Range rule, then prove the gain and remove unused indexes safely. Use when the user says a MongoDB/Mongoose/PyMongo/Motor query or endpoint is slow, sees COLLSCAN or in-memory SORT in explain output, hits high Atlas CPU or "Query Targeting" alerts, or asks which indexes to add or drop.
metadata:
  category: backend-devops
  added: "2026-11-20"
---

# MongoDB index tuning

Slow MongoDB queries are almost always one of three things: no usable index (COLLSCAN), an index whose field order can't serve the sort (in-memory SORT), or an index that isn't selective enough (it reads thousands of documents to return twenty). This skill finds the queries that matter, reads the evidence in `explain`, designs the smallest index that fixes them, and proves the improvement with before and after numbers. It does not guess.

## When to use

- "This endpoint is slow", "the orders list takes 3 seconds", "Atlas CPU is at 90%"
- An Atlas alert says *Query Targeting: Scanned Objects / Returned has gone above 1000*
- `explain()` output or slow-query logs show `COLLSCAN`, `SORT`, or `planSummary: COLLSCAN`
- "Which indexes should I add?" or "Do we have unused indexes?"
- **Not for:** schema redesign (embedding vs referencing), sharding key choice, or slowness caused by the network or connection pool (check `serverStatus().connections` and driver pool settings first if *every* query is slow, including `_id` lookups)

## Steps

1. **Find the queries that matter. Don't guess from code.** Use whichever source is available, in this order:
   - **Atlas:** Performance Advisor (suggested indexes, ranked by impact) and Query Profiler. Read these before writing anything.
   - **Slow-query log** (mongod logs any operation slower than `slowms`, default 100 ms):
     ```bash
     grep '"Slow query"' /var/log/mongodb/mongod.log | grep -E 'COLLSCAN|"SORT' | tail -20
     ```
     The useful fields are `attr.ns`, `attr.command.filter`, `attr.command.sort`, `attr.planSummary`, `attr.docsExamined`, `attr.nreturned`, `attr.durationMillis`.
   - **Profiler** (self-hosted, temporary only: it adds write load):
     ```javascript
     db.setProfilingLevel(1, { slowms: 50 })
     // ...exercise the app for a few minutes...
     db.system.profile.find({ millis: { $gt: 50 } }, { ns: 1, command: 1, planSummary: 1, docsExamined: 1, nreturned: 1, millis: 1 })
       .sort({ millis: -1 }).limit(10)
     db.setProfilingLevel(0)   // always switch it back off
     ```
   Rank by **frequency × duration**, not duration alone. A 40 ms query run 50 times a second matters more than a 4 s report run nightly.

2. **Reproduce one query with explain.** Copy the exact filter, sort, projection and limit the app sends (from the log, or by reading the code that builds it), then:
   ```javascript
   db.orders.find({ tenant_id: "t_42", status: "paid", created_at: { $gte: ISODate("2026-10-01") } })
     .sort({ created_at: -1 }).limit(20)
     .explain("executionStats")
   ```
   For pipelines use `db.orders.explain("executionStats").aggregate([...])`. Only the leading `$match`/`$sort` stages can use an index.
   From drivers: PyMongo/Motor `cursor.explain()` (default verbosity includes executionStats), Mongoose `Model.find(q).sort(s).explain("executionStats")`.
   To get a quick verdict, save the output and run the helper:
   ```bash
   mongosh "$MONGODB_URI" --quiet --eval 'EJSON.stringify(db.orders.find({tenant_id:"t_42",status:"paid"}).sort({created_at:-1}).limit(20).explain("executionStats"))' > explain.json
   python skills/mongodb-index-tuning/scripts/explain_summary.py explain.json
   ```

3. **Read the numbers with these rules:**

   | Signal (in `executionStats` / `winningPlan`) | Meaning | Action |
   |---|---|---|
   | stage `COLLSCAN` | no usable index | add an index (Step 4) |
   | stage `SORT` above `IXSCAN`/`FETCH` | the index doesn't give the sort order, so it sorts in memory (100 MB limit, spills to disk) | put the sort field right after the equality fields |
   | `totalDocsExamined / nReturned` > 10 | index is not selective | add the missing equality field to the index |
   | `totalKeysExamined` ≫ `nReturned` but docs ≈ returned | range field placed before an equality/sort field | reorder by ESR |
   | `totalDocsExamined: 0`, stage `PROJECTION_COVERED` | covered query | already optimal |
   | ratios ≈ 1 and still slow | not an index problem | check result size, `$lookup`, network, or lock contention |

   On MongoDB 7.0+ with the slot-based engine the tree sits under `winningPlan.queryPlan`. Read it the same way.

4. **Design the index with the ESR rule: Equality, then Sort, then Range.**
   - **E**: fields matched exactly (`tenant_id: "t_42"`, `status: "paid"`). Put the most frequently filtered first so other queries can reuse the prefix.
   - **S**: sort fields, in the query's direction (or all reversed: `{a:1,b:-1}` serves `sort({a:-1,b:1})` too).
   - **R**: range filters (`$gt`, `$lt`, `$in` with many values, `$regex` with a prefix).
   For the query above: `{ tenant_id: 1, status: 1, created_at: -1 }`. Here `created_at` is both the sort and the range field, so it goes in the sort position.
   **Prefix rule:** `{a:1,b:1,c:1}` also serves queries on `a` and on `a,b`. Before you add `{a:1}`, check `db.orders.getIndexes()`. If an existing index already has it as a prefix, the new one is redundant.
   Pick the variant that fits:
   - **Partial index**, when queries always include a condition that matches a small subset:
     `{ partialFilterExpression: { status: "pending" } }`. The query must include `status: "pending"` or the index is ignored.
   - **Covering index**, when a hot query reads few fields. Include every projected field and exclude `_id` in the projection.
   - **Case-insensitive search**: `{ collation: { locale: "en", strength: 2 } }`, and the query must pass the same collation. `/^abc/i` cannot use an index efficiently.
   - **TTL**: `{ expireAfterSeconds: 2592000 }` on a date field for sessions and logs, which also shrinks the working set.

5. **Create it safely.** Index builds (4.2+) lock only briefly at start and end, but they use CPU and I/O. On big collections, build off-peak. On Atlas, use the rolling build option. Always name indexes:
   ```javascript
   db.orders.createIndex({ tenant_id: 1, status: 1, created_at: -1 }, { name: "tenant_status_created" })
   ```
   ```python
   orders.create_index([("tenant_id", 1), ("status", 1), ("created_at", -1)], name="tenant_status_created")
   ```
   If the project manages indexes in code (a migration script, Mongoose `schema.index(...)`, Beanie `Settings.indexes`, a startup `create_indexes()`), add it **there** so every environment gets it. Don't only run it in a shell against production. Note that Mongoose `autoIndex` should be off in production, so make sure a migration step actually builds it.

6. **Re-run the same explain and compare** `executionTimeMillis`, `totalDocsExamined`, `totalKeysExamined` and the plan. If the planner still picks another index, check `queryPlanner.rejectedPlans`. Don't use `hint()` in app code unless you have no other choice: a hint pins the plan even after the data changes.

7. **Remove dead weight (optional, carefully).** Every index slows writes and uses RAM.
   ```javascript
   db.orders.aggregate([{ $indexStats: {} }, { $project: { name: 1, ops: "$accesses.ops", since: "$accesses.since" } }])
   ```
   `ops: 0` since a restart weeks ago, on every replica-set member, makes an index a candidate. Also flag indexes that are a prefix of another index. Then **hide before you drop**: `db.orders.hideIndex("old_idx")`, watch latency for a full business cycle (at least a week), and only then `dropIndex`. `unhideIndex` is instant, but a rebuild is not.

8. **Report.** For each query, give the plan and numbers before and after, the index added (with the code location), any indexes hidden or dropped, and the expected write and RAM cost (`db.orders.stats().indexSizes`).

## Examples

### Example 1: multi-tenant order list, 1.8 s → 3 ms

A FastAPI + Motor endpoint `GET /orders?status=paid` runs:
```python
cursor = db.orders.find({"tenant_id": tid, "status": "paid"}).sort("created_at", -1).limit(20)
```
Existing indexes: `_id_` and `{ created_at: -1 }`. Before:
```
plan:          LIMIT -> FETCH -> IXSCAN(created_at_-1)
nReturned:     20
keysExamined:  412988
docsExamined:  412988
docs/returned: 20649.4
verdict:       NEEDS INDEX WORK
```
The planner walks the `created_at` index newest-first and fetches every order from every tenant until it finds 20 matches. Following ESR: equality `tenant_id`, `status`, then sort `created_at`:
```python
await db.orders.create_index([("tenant_id", 1), ("status", 1), ("created_at", -1)], name="tenant_status_created")
```
After: `IXSCAN(tenant_status_created)`, keys 20, docs 20, 3 ms. `{created_at: -1}` was still used by an admin export, so it stayed.

### Example 2: in-memory sort caused by a wrong field order

A Mongoose query `Ticket.find({ assignee: id, priority: { $gte: 3 } }).sort({ updatedAt: -1 })` already had the index `{ assignee: 1, priority: 1, updatedAt: -1 }`. The explain showed `SORT -> FETCH -> IXSCAN`: the range field `priority` sat before the sort field, so the index output wasn't ordered by `updatedAt`. Reorder to ESR:
```javascript
ticketSchema.index({ assignee: 1, updatedAt: -1, priority: 1 }, { name: "assignee_updated_priority" });
```
Ship the new index through the migration, confirm `SORT` is gone and the time dropped from 640 ms to 12 ms, then `hideIndex` the old one. Drop it a week later.

### Example 3: case-insensitive email lookup

`users.find({ email: /^ali@example\.com$/i })` did a full index scan. Fix:
```javascript
db.users.createIndex({ email: 1 }, { name: "email_ci", collation: { locale: "en", strength: 2 } })
db.users.find({ email: "ali@example.com" }).collation({ locale: "en", strength: 2 })
```
Update the app query to pass the same collation. Without it, the planner ignores `email_ci`.

## Pitfalls

- **Indexing every field separately.** MongoDB rarely combines single-field indexes (index intersection is seldom chosen). One well-ordered compound index beats five single ones.
- **Ignoring the sort.** An index that matches the filter but not the sort still triggers an in-memory `SORT`. This is the most common miss.
- **Explaining a different query than the app sends.** Mongoose casting, default projections, or an added `deleted: false` filter change the plan. Copy the real query from logs or the profiler.
- **Testing on a tiny dev database.** With 200 documents, COLLSCAN looks fast and the planner may choose differently. Use production-like volume, or read production's explain output.
- **Low-selectivity leading fields.** `{ is_active: 1 }` alone, on a field where 95% of documents are true, barely helps. Put it after a selective equality field, or use a partial index.
- **`$ne`, `$nin`, `$not` and unanchored regex** can't use an index selectively. Rewrite them as positive matches where possible.
- **Multikey limits.** A compound index can contain at most one array field, and a sort on an array field behaves unexpectedly.
- **Leaving the profiler on**, or dropping an index without hiding it first.
- **Never** build large indexes on a production primary at peak time, paste connection strings with credentials into the report or commands (use `$MONGODB_URI` from the environment), or add `hint()` to app code just to make a benchmark pass.

## Verification

- `explain("executionStats")` for each tuned query shows `IXSCAN` on the new index name, no `COLLSCAN`, no `SORT` stage, and `totalDocsExamined / nReturned` ≤ 2 (0 for covered queries).
- `python skills/mongodb-index-tuning/scripts/explain_summary.py after.json` prints `verdict: OK` and exits 0. On the "before" file it prints `NEEDS INDEX WORK` and exits 1.
- `db.orders.getIndexes()` lists the index with the expected key order and name, and the same index is defined in the project's migration or model code (`git grep tenant_status_created`).
- The endpoint's p95 latency (APM, Atlas Query Profiler, or `hey`/`ab` against staging) drops, and the Atlas "Query Targeting" alert clears.
- After a few hours, `$indexStats` shows `accesses.ops` increasing on the new index.
