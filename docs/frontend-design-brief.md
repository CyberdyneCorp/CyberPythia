# Mnemosyne — Frontend Design Brief

*A prompt for a design collaborator. Copy everything below the line.*

---

I need help designing the UI for a product called **Mnemosyne**. Please propose a clean,
modern, information-dense-but-calm visual design: layout system, navigation, component styles,
color/typography, data-visualization treatments, and how each screen and state should look.
Below is everything about the product, its users, its screens, and the states each screen must
handle. Design for both light and dark themes. The app is a SvelteKit web app rendered in a
browser (desktop-first, but it must be usable on a tablet/narrow window).

## What Mnemosyne is

Mnemosyne is a **GitHub context & memory layer** for a software company. It indexes the
organization's GitHub repositories (docs, issues, pull requests, source code, OpenSpec change
proposals, milestones) and turns them into answers and insights. It serves both **humans** and
**AI agents** (agents use an API; humans use this web app). The whole company uses it to
understand the codebase without reading it directly.

**It is read-mostly and analytical** — think "an intelligence dashboard for engineering," not a
code editor. The feel should be trustworthy, precise, and calm: a tool people check to make
decisions.

## Who uses it (design for all four)

- **Product Owners / Project Managers** — want delivery health: is the backlog under control,
  when will a milestone ship, where are reviews stuck, what's the work-mix (features vs bugs vs
  tech-debt). They scan dashboards; they don't read code.
- **Developers** — want to find things fast: search docs and code, read a file, see a repo's
  structure, ask grounded questions, pull a "context pack" for a task.
- **Business / Leadership** — want the portfolio view: which repos are healthy, which are
  abandoned, which are bug-heavy, overall trends.
- **Admins** — connect GitHub, choose which repos to index, and watch the nightly sync.

## Brand / tone

- Name evokes memory/knowledge (Mnemosyne, Greek goddess of memory). Current placeholder mark is
  a 🧠 emoji + wordmark — feel free to propose a real logomark concept.
- Tone: **precise, quiet confidence, data-forward.** Not playful, not enterprise-drab. Think
  Linear / Vercel / Stripe-dashboard restraint, with excellent typography and generous
  whitespace around dense data.
- A signature accent color is welcome. Must work in light and dark.

## Global shell

- **Top bar**: brand (left), primary nav, and a session area (user name + "Sign out") on the
  right.
- **Primary nav**: `Repositories` · `Intelligence` · `GitHub Connection`. (Design should
  anticipate 1–2 more sections later, e.g. a "Delivery" or "Sync activity" view — make nav
  extensible.)
- **Auth-gated**: signed-out users see a sign-in gate ("Connect with Cyberdyne" — an OIDC
  button). There is also an **"access required"** state for users who are authenticated but lack
  the product entitlement (show a friendly explanation, no app chrome). And a transient
  "Loading session…" state.

## Screens

### 1. Sign-in gate
A centered card: product name, one-sentence value prop, and a single **"Connect with Cyberdyne"**
button (OIDC redirect). Show a sign-in error inline if it fails. Also design the **entitlement-
denied** variant (user is logged in but not granted access).

### 2. Repositories dashboard (home)
The list of indexed repositories. There are **~238 enabled repos out of ~345 discovered**, so
this must scale: search/filter box, sensible sort (indexed/active first), and pagination or
virtualized list. Each **repository card/row** shows:
- Full name (`org/repo`), primary language, visibility (private/public).
- **Indexing mode** badge: `docs_only` / `project_intelligence` / `code_metadata` /
  `code_context` / `full_context` (five levels of depth).
- **Sync status**: last-synced time, and a live state when a sync is running
  (pending → running → succeeded/failed).
- Admin controls: an **enable/disable toggle** + mode selector, and a **"Sync now"** button.
- Clicking a card opens the repository detail.

Design the **empty state** (no repos yet → prompt to connect GitHub) and the **filtered-empty**
state.

### 3. Repository detail
A header with the repo's full name, then a **tabbed** workspace. Tabs:
- **Overview** — description, key stats (docs count, OpenSpec changes, open/closed issues,
  open/merged PRs, avg issue-resolution, avg PR-merge), plus two rich panels:
  - **Health panel**: an overall **0–100 score + letter grade (A–F)**, a breakdown of 5
    component scores (documentation, delivery, maintenance, testing/CI, activity) — each 0–100
    **or "n/a"** when not applicable — and a ranked list of **findings** (severity + message,
    e.g. "No CI configured", "12 stale open items").
  - **Delivery panel** (PM/PO metrics): **cycle-time percentiles (p50/p85/p95)**, work-in-
    progress counts, **aging buckets** (0–7 / 7–30 / 30–90 / 90+ days), untriaged count,
    **work-mix distribution** (feature/bug/tech-debt/docs/other), a **backlog forecast**
    ("projected to clear by <date>" or a "collecting history" note), and a **milestones** table
    (percent complete, due date, projected completion, an "at-risk" flag).
- **Documentation** — list of captured docs; clicking one renders its content (Markdown).
- **OpenSpec** — captured change proposals (proposal/design/tasks), with status.
- **Issues** — list with number, title, state, labels, assignees.
- **Pull Requests** — list with number, title, merged/open, reviewers.
- **Files** — the captured file tree (paths, languages, "important" files flagged).
- **Metrics** — the raw engineering metrics (issue/PR distributions, resolution/merge times).
- **Code Context** — a **semantic code search** box; results are code chunks (path, symbol,
  line range, excerpt, score). Clicking a result can load full file content. (Only meaningful in
  code-capturing modes; show a clear "this repo isn't indexed for code" state otherwise.)
- **Agent Context** — a **grounded Q&A** box ("ask a question about this repo") that returns an
  answer **with citations**, plus a **"context pack"** mode that assembles a task-specific bundle
  (relevant docs, issues, PRs, files, risks, suggested next steps) — the same bundle an AI agent
  would consume. Design a nice way to show sources/citations and the structured pack.

Design **loading**, **empty** (e.g. no issues), and **error** states per tab. Tabs should be
deep-linkable (URL carries the active tab).

### 4. Intelligence dashboard (portfolio)
The cross-repo, leadership/PM view. Sections:
- **Health leaderboard** — repositories ranked by health score, each with grade badge + score.
  Rows link to the repo detail. Repos not yet synced show an "insufficient data" marker (never a
  fake zero).
- **Groupings** — three lists: **Most active**, **Abandoned**, **Bug-heavy**.
- **Delivery scorecard** — a table across repositories: median cycle time, **throughput
  direction** (improving ↓ / growing ↑ / flat), **backlog trend** (shrinking / not shrinking /
  "collecting"), and an **at-risk milestones** count. Some cells will legitimately read
  "collecting" until history accrues — design that gracefully.

This screen is the flagship "wow" surface — it's what a PO or exec opens first. Charts welcome
(sparklines for trends, small bar/stacked bars for work-mix, gauges/rings for health/grade), but
keep them legible and self-contained.

### 5. GitHub Connection (admin)
Admin-only. Contains:
- A **fine-grained PAT** connect form (paste token → connect).
- A **GitHub App** connect form (App ID, installation ID, private-key PEM, webhook secret) — the
  recommended production path.
- **Webhook activity** table (event, repository, outcome, time).
- **Connection cards** (owner, type, status, permissions) with "test connection", "discover
  repositories", and "delete".
- **(Planned, please design too)** a **Sync activity** panel: recent **scheduled-run summaries**
  (per nightly run: discovered / newly-enabled / enqueued / skipped / failed + timestamps) and
  recent **per-repo sync jobs** (repo, status, trigger, time, and failure reason — including
  rate-limit skips). This is how an admin watches the automatic daily sync.

## Cross-cutting states to design (very important)

This product has a strict **"absent-not-zero"** philosophy — it never fabricates data. Please
give first-class visual treatment to:
- **Loading / skeletons**.
- **Insufficient data** ("not synced yet", "no PRs merged", "mode doesn't capture this") — a
  calm, explanatory placeholder, clearly different from a real zero value.
- **"Collecting history"** — trend/forecast charts are empty until a few days of data accrue;
  show an informative, non-alarming state.
- **n/a components** — e.g. a health component that doesn't apply is shown as not-applicable, not
  as 0.
- **Errors** — inline, human-readable, recoverable.
- **Empty lists** and **filtered-empty**.
- **Running/in-progress** (a sync in flight) with live status.

## Data-viz vocabulary to establish

Please define a consistent visual language for: a **0–100 score with an A–F grade**; **letter-
grade badges**; **severity chips** (info/warning/critical) for findings; **percentile triplets**
(p50/p85/p95); **aging/age-bucket bars**; **work-mix distribution** (feature/bug/tech-debt/docs);
**milestone progress + at-risk**; **throughput/net-flow trend sparklines**; **status badges**
(synced/failed/running, indexing-mode levels). Keep it coherent so the same metric looks the same
everywhere.

## Constraints (for eventual implementation, so keep it feasible)

- Built in **SvelteKit + Svelte 5**; components are hand-rolled CSS (no heavy UI kit assumed).
- Charts must be **self-contained** (inline SVG/CSS) — assume no external chart CDN.
- **Light + dark** themes, responsive down to a narrow window, accessible (contrast, keyboard,
  focus states).

## What I want from you

1. A proposed **visual system**: color (light + dark), typography scale, spacing, elevation,
   radius, and the accent.
2. **Component designs** for the recurring pieces: nav/shell, repo card/row, tabbed detail
   header, health panel (score + grade + components + findings), delivery panel, leaderboard row,
   delivery-scorecard table, and the state placeholders (loading / insufficient-data / collecting
   / error / empty).
3. **Screen layouts** (wireframe-to-hi-fi) for: Repositories dashboard, Repository detail
   (Overview + one data tab + Agent Context), Intelligence dashboard, and GitHub Connection.
4. The **data-viz treatments** listed above.
5. Guidance on making the **Intelligence dashboard** feel like the flagship.

Prioritize clarity and trust over decoration. Show me options where a choice matters.
