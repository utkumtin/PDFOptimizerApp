---
description: Describe when these instructions should be loaded
paths:
. - "src/**/*.ts"
---
# Claude Coding Rules — Clean & Human-Like

## Core Philosophy

Write code the way a **thoughtful senior developer** would write it on a good day —
not a textbook, not a linter, not a code generator.
Code is read far more than it's written. Optimize for the reader.

---

## Naming

- Name things by **what they mean**, not what they are.
  - ❌ `data`, `temp`, `obj`, `val`, `res`
  - ✅ `userInvoices`, `retryDelay`, `activeSession`
- Boolean names should read like questions: `isLoading`, `hasError`, `canSubmit`
- Functions should be **verbs**: `fetchUser`, `parseDate`, `buildQuery`
- Avoid noise words: `Manager`, `Handler`, `Helper`, `Utils`, `Info` — if you must use them, they signal a design smell
- Constants in `SCREAMING_SNAKE_CASE` only for true global constants, not every `const`

---

## Functions

- One function, one job. If you need "and" to describe it, split it.
- Keep functions **short** — if it doesn't fit on one screen, it's doing too much.
- **No surprise side effects.** A function named `getUser` should not also log, mutate state, or fire an event.
- Prefer **returning early** over deeply nested conditions:
  ```ts
  // ❌ Pyramid of doom
  if (user) {
    if (user.isActive) {
      if (user.hasPermission) { ... }
    }
  }

  // ✅ Early returns
  if (!user) return null
  if (!user.isActive) return null
  if (!user.hasPermission) return null
  ...
  ```
- Max **3 parameters**. If you need more, pass an object.

---

## Comments

- **Don't explain what the code does** — that's the code's job.
- **Explain why** something is done a certain way, especially if it's non-obvious:
  ```ts
  // ❌ Bad
  // increment i by 1
  i++

  // ✅ Good
  // Slack API returns 0-indexed pages but our UI is 1-indexed
  const displayPage = page + 1
  ```
- If you find yourself writing a long comment, consider renaming or refactoring instead.
- `TODO:` and `FIXME:` are acceptable — but include *why*, not just *what*.

---

## Code Structure & Layout

- **Group related things together.** Imports, then constants, then types, then logic.
- Leave a **blank line between logical sections** — visual breathing room matters.
- Don't over-engineer small things. A plain `if/else` is often cleaner than a fancy pattern.
- Avoid premature abstraction. Duplication is cheaper than the wrong abstraction.
- Prefer **flat over nested** structures wherever possible.

---

## Error Handling

- Never silently swallow errors. At minimum, log them with context.
- Fail loudly in development, gracefully in production.
- Write **specific** error messages that tell you *where* and *why*, not just *what*:
  ```ts
  // ❌
  throw new Error("Invalid input")

  // ✅
  throw new Error(`createInvoice: amount must be a positive number, got ${amount}`)
  ```
- Use typed errors where the language supports it.

---

## Variables & State

- Declare variables **close to where they're used**, not at the top of the scope.
- Prefer `const` by default. Only use `let` when mutation is intentional.
- Avoid magic numbers and magic strings — give them names:
  ```ts
  // ❌
  if (attempts > 3) retry()

  // ✅
  const MAX_RETRY_ATTEMPTS = 3
  if (attempts > MAX_RETRY_ATTEMPTS) retry()
  ```
- Don't reuse variables for different purposes. New purpose → new variable.

---

## Human-Like Patterns

These are things a real developer does that AI often skips:

- **Write the happy path first**, then handle edge cases.
- **Leave small breadcrumbs** for the next developer (even if that's you in 6 months).
- Don't be overly clever. Readable > impressive.
- Slightly imperfect but clear code beats perfect but cryptic code.
- If something feels awkward to write, it probably needs a redesign — don't paper over it.
- **Consistency beats perfection.** Stick to one style throughout the file.
- Small utility functions are fine — don't be afraid of a 3-line helper if it has a good name.

---

## What to Avoid

| ❌ Avoid | ✅ Instead |
|---|---|
| `// self-explanatory` comments | Rename the thing so it actually is |
| Abstracting after just 2 uses | Wait for the third |
| Clever one-liners | Two readable lines |
| Deep nesting | Early returns / guard clauses |
| Long files (500+ lines) | Split by responsibility |
| Generic names like `utils.ts` | `dateHelpers.ts`, `formatCurrency.ts` |
| Commented-out code | Delete it — git has history |

---

## The Final Check

Before finishing, ask:

1. Would I be comfortable explaining every line of this in a code review?
2. Would a new team member understand this without asking me?
3. Is there anything here I wrote just to look smart?

If yes to 3 — simplify it.