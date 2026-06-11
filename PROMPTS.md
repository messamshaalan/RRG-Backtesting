# PROMPTS.md — Reusable Prompt Library

Generic, fill-in-the-bracket prompts for each stage of a build. Designed to work alongside `CLAUDE.md` (which holds the persistent persona and constraints, so these stay short).

---

## 1. Project Initialization (environment only)

```
Initialize a new web application in the current directory using [Next.js / Vite / Nuxt].

1. Run the terminal commands to scaffold the project and install dependencies:
   [TailwindCSS, state management, auth library, testing framework, etc.]
2. Configure: TypeScript strict mode, ESLint + Prettier, path aliases, and a
   `.env.example` with every variable the app will need (documented, no real values).
3. Output the resulting folder structure as a tree with a one-line purpose note
   per directory.

Do NOT write any application logic yet. Stop after setup so I can review the
environment and folder manifest before we proceed.
```

## 2. Phased Build Kickoff (backend first)

```
We are building a [App Type, e.g., SaaS analytics dashboard] with these core features:
1. [Feature 1]
2. [Feature 2]
3. [Feature 3]

Target users: [who] · Scale assumption: [e.g., <10k users initially] · Constraints: [e.g., must deploy on Vercel]

Do not build the entire app. For **Phase 1**, deliver only:
1. A proposed folder structure with rationale.
2. The core database schema (tables, fields, types, relations, indexes) plus a
   short note on any modeling trade-off you made.
3. The minimum viable backend: framework setup, routing skeleton, one fully
   working example endpoint with validation and error handling as the pattern
   for all others.
4. A short list of open questions or risks you spotted.

Stop there. After I review and test Phase 1, we'll define Phase 2 (API surface),
then Phase 3 (frontend).
```

## 3. Frontend UI / Design Pass

```
Build the frontend UI for [feature/page] using [React + TailwindCSS].

Design brief:
- Product/subject: [what it is, who uses it, the single job of this page]
- Mood: [e.g., precise and financial / warm and editorial / technical and dense]

Design directives:
- Typography: [e.g., a characterful display face for headings, a clean grotesque
  for body] with an explicit type scale (display, H1–H3, body, caption).
- Palette: 4–6 named CSS-variable tokens — one distinct brand color, dark
  neutral text (not #000), subtle tinted backgrounds (not #fff), semantic
  success/warning/error colors. Avoid default AI looks (cream + terracotta,
  black + acid green, purple gradients on everything).
- Components: custom card layouts, soft shadows, clean borders, generous and
  consistent spacing.
- Motion: smooth transitions on hover/focus (lift, opacity, border shifts),
  one orchestrated load/scroll moment max, respect prefers-reduced-motion.
- Accessibility: semantic HTML, keyboard focus states, WCAG AA contrast,
  responsive down to 360px.
- Signature: propose ONE memorable element unique to this page and justify it.

Process: show me the design token configuration (CSS variables / Tailwind theme)
and the component architecture FIRST. Wait for my approval before implementing
the views.
```

## 4. TDD Feature Cycle

```
Before implementing [feature/component], write the test suite using
[Vitest / Jest / Cypress / Playwright].

Requirements:
- Unit tests for the happy path.
- At least two edge cases: [e.g., empty input, network failure, unauthorized
  user, boundary values].
- One test for the user-facing error state where applicable.
- Tests must assert behavior (outputs, rendered state, side effects), not
  implementation details.

Step 1: provide ONLY the failing tests. Run them and show me they fail for the
right reasons.
Step 2 (after my confirmation): write the minimum implementation to make them
pass — nothing speculative.
Step 3: refactor for clarity if needed, keeping all tests green.
```

## 5. API / Contract Design

```
Design the API surface for [feature/domain] before any implementation.

Deliver:
1. Endpoint table: method, path, purpose, auth requirement.
2. Request/response schemas for each (as [Zod / TypeScript types / OpenAPI]).
3. Error taxonomy: every failure mode, its status code, and the exact
   user-facing message shape.
4. Pagination, filtering, and rate-limiting strategy where relevant.

Treat this contract as frozen once I approve it — frontend and backend will
both build against it.
```

## 6. Code Review Pass

```
Review [file/PR/module] as a principal engineer. Do not rewrite it yet.

Report, in priority order:
1. Bugs and correctness issues (with the failing scenario).
2. Security vulnerabilities (injection, auth gaps, data exposure, unvalidated
   input).
3. Performance problems (N+1 queries, unnecessary re-renders, missing indexes).
4. Maintainability concerns (coupling, naming, missing tests, dead code).

For each finding: severity (critical / major / minor), the exact location, why
it matters, and the minimal fix. End with the three changes you'd make first.
```

## 7. Refactor (behavior-preserving)

```
Refactor [module/component] with zero behavior change.

Goals: [e.g., extract data access from UI, reduce component to <150 lines,
remove duplication with X].

Rules:
- Existing tests must pass unchanged. If coverage is too thin to refactor
  safely, write characterization tests FIRST and show me.
- One structural change per commit-sized step; narrate each step in one line.
- No new features, no API changes, no "while I'm here" edits.
```

## 8. Debugging Protocol

```
Bug: [observed behavior] · Expected: [expected behavior]
Repro steps: [steps] · Environment: [browser/OS/versions] · Logs/errors: [paste]

Do not jump to a fix. First:
1. List the 2–3 most likely root-cause hypotheses, ranked.
2. For the top hypothesis, tell me exactly what to check or what logging to add
   to confirm or eliminate it.
3. Only after the cause is confirmed, propose the minimal fix plus a regression
   test that would have caught this bug.
```

## 9. Pre-Launch Audit

```
Run a pre-launch audit of the application. Produce a checklist report covering:

- Security: auth on all protected routes, input validation at every boundary,
  secrets out of the client bundle, security headers (CSP, HSTS), dependency
  vulnerabilities.
- Performance: bundle size, image optimization, query efficiency, caching,
  Core Web Vitals risks.
- Accessibility: keyboard navigation end-to-end, contrast, labels, focus traps.
- Reliability: error boundaries, empty states, loading states, behavior on
  failed requests for every screen.
- DX/ops: env variable documentation, build reproducibility, logging, README
  accuracy.

Mark each item ✓ / ⚠️ / ✗ with file references, then list launch blockers
versus fast-follows.
```
