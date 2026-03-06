---
description: Describe when these instructions should be loaded
paths:
. - "src/**/*.ts"
---
# Claude Coding Rules — Optimization

## Core Philosophy

Optimization is not about writing the cleverest algorithm.
It's about **not doing unnecessary work** — and knowing the difference between what's slow and what just *feels* slow.

> "Premature optimization is the root of all evil." — Donald Knuth
> But ignoring performance until it's a crisis is just as bad.

The goal: write code that is **correct first, then fast where it needs to be.**

---

## Measure Before You Fix

- **Never guess where the bottleneck is.** Profile it.
- Use proper tools: browser DevTools, `console.time`, Lighthouse, database query analyzers, flamegraphs — whatever fits the stack.
- A 10ms function that runs once is not worth optimizing. A 2ms function that runs 10,000 times is.
- Document what you measured and why you changed something:
  ```ts
  // Profiling showed this ran ~8000x per session and was rebuilding the map every call.
  // Memoized the result — reduced avg render time from 140ms → 12ms.
  const categoryMap = useMemo(() => buildCategoryMap(categories), [categories])
  ```

---

## Rendering & UI Performance

- **Avoid unnecessary re-renders.** Components should only re-render when their data actually changes.
- Memoize expensive computations (`useMemo`, `computed`, etc.) — but only when the cost is measurable, not by habit.
- Virtualize long lists. Rendering 1,000 DOM nodes when only 20 are visible is always wasteful.
- Lazy-load routes, heavy components, and large assets. Users shouldn't pay the cost of pages they haven't visited.
- Keep the **critical rendering path lean** — defer non-essential scripts, inline above-the-fold CSS where needed.
- Debounce or throttle event handlers that fire at high frequency (scroll, resize, keypress, input).

---

## Data & API Calls

- **Never fetch data you don't need.** Request only the fields you'll actually use.
- Cache aggressively where data doesn't change often — but cache with intention, not as a band-aid.
- Batch related requests. N+1 queries are a silent performance killer:
  ```ts
  // ❌ N+1 — fires one query per user
  const profiles = await Promise.all(userIds.map(id => db.users.findOne(id)))

  // ✅ Single query
  const profiles = await db.users.findMany({ where: { id: { in: userIds } } })
  ```
- Paginate large datasets. Never load everything and filter on the client.
- Avoid waterfalls. Kick off independent requests in parallel:
  ```ts
  // ❌ Sequential — total time = A + B + C
  const user = await fetchUser(id)
  const orders = await fetchOrders(id)
  const prefs = await fetchPreferences(id)

  // ✅ Parallel — total time = max(A, B, C)
  const [user, orders, prefs] = await Promise.all([
    fetchUser(id),
    fetchOrders(id),
    fetchPreferences(id),
  ])
  ```

---

## Memory & Resource Management

- Clean up after yourself: clear intervals, cancel subscriptions, abort in-flight requests on component unmount.
- Avoid creating large objects or arrays inside hot loops — allocate once, reuse.
- Watch for **memory leaks** in long-lived processes: event listeners that are never removed, closures holding references to stale data, growing caches with no eviction policy.
- Prefer streaming for large file reads/writes — don't load a 500MB file into memory to process it.

---

## Bundle & Asset Size

- **Every kilobyte has to earn its place.** Audit bundle size regularly.
- Tree-shake unused code. Don't import an entire library for one utility:
  ```ts
  // ❌
  import _ from 'lodash'
  _.debounce(fn, 300)

  // ✅
  import debounce from 'lodash/debounce'
  ```
- Compress and properly size images. Use modern formats (WebP, AVIF) where supported.
- Split code at natural boundaries — don't ship admin panel code to regular users.
- Set proper cache headers. Static assets that never change should be cached forever with content-hash filenames.

---

## Database & Queries

- **Index what you filter and sort on.** An unindexed query on a large table will eventually bring the system to its knees.
- Avoid `SELECT *` — fetch only the columns you need.
- Run `EXPLAIN` / `EXPLAIN ANALYZE` on queries that touch large tables.
- Keep transactions short. Long-held locks block everything else.
- Consider read replicas for heavy read workloads. Don't let reporting queries compete with your write path.

---

## Correctness Over Cleverness

- An optimized function that returns the wrong result is worse than a slow correct one.
- Always verify behavior is unchanged after an optimization — write tests before refactoring hot paths.
- If an optimization makes code significantly harder to understand, add a comment explaining **what** it's doing and **why** the naive version wasn't acceptable:
  ```ts
  // Using a flat array + manual index instead of a Map here because
  // this runs inside a tight loop (~50k iterations) and Map has
  // measurable overhead at this scale. Benchmarked: 3.1x faster.
  ```

---

## The Optimization Checklist

Before shipping a feature, run through:

- [ ] Are there any N+1 queries?
- [ ] Are independent async operations running in parallel?
- [ ] Are large lists virtualized or paginated?
- [ ] Are expensive computations memoized where it counts?
- [ ] Are event listeners and subscriptions cleaned up?
- [ ] Is the bundle size reasonable? Any accidental heavy imports?
- [ ] Do images have proper sizes and formats?
- [ ] Are database queries hitting indexes?
- [ ] Is nothing being refetched that could reasonably be cached?

---

## What to Avoid

| ❌ Avoid | ✅ Instead |
|---|---|
| Optimizing without profiling | Measure first, always |
| Memoizing everything "just in case" | Memoize what you've measured |
| Loading all records to filter client-side | Filter and paginate on the server |
| Blocking the main thread with heavy sync work | Defer, debounce, or move to a worker |
| Ignoring memory leaks in long-lived processes | Audit cleanup on unmount / shutdown |
| Skipping indexes on frequently queried columns | Add indexes early, not after the incident |