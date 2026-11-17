# Design: remediation of the November 2026 audit

Date: 2026-11-15. Source: [codebase-audit.md](codebase-audit.md).

## Status and purpose

The owner confirmed this audit as the source and instructed that its findings
are verified. This design accepts them without another audit. Source inspection
is only to identify integration points and preserve contracts.

This is the design for Phase 47, divided into independently reviewable parts.
It fixes correctness risks first, then removes specific duplication and growth
pressure. It does not authorize implementing all parts in one change.

The last implemented baseline is Phase 46: 4,310 tests and migration
`0026_proposal_findings.py`, confirmed by its progress entry and PASS review.
The working tree contains unrelated uncommitted work. Preserve it.

This document fixes outcomes, boundaries, and acceptance scenarios. Each part
gets its executable phase spec and matching verification guide immediately before
implementation, after its predecessor's actual result is known. Those specs
must supply exact Scope paths, given tests/diffs, collected counts, coverage
commands, and validated spot checks under `phase-conventions.md`. Do not hand this
umbrella design to a coder as an implementation-ready phase spec.

## Decisions

**Owner decisions (2026-11-15):** use the November 15 audit as verified input;
produce a design; split the work into phases rather than do it all at once.

**Architect decisions:** preserve external behavior except the named pairing
repair, unknown-kind refusal, and separately scheduled lock-wait change. Keep
existing data and schemas. Use existing runtime dependencies; 47b permits pytest-xdist for development. Retain explicit proposal
branches; do not introduce a plugin registry or generic ORM mapper. Keep WAL
conditional because backup/restore and cross-process access need their own design.

## Delivery order

| Part | Outcome | Depends on | Primary test sections |
|---|---|---|---|
| 47a | Categorize and pair through one application operation | 46 | web, cli, core |
| 47b | Parallel test runner, timings and measured worker recommendation | 47a | scripts |
| 47c | Refuse unsupported proposal kinds before mutation | 47b | core, mcp, web, cli |
| 47d | Share proposal reason validation and repository UTC time | 47c | core, mcp |
| 47e | Share statement line flattening | 47d | parsers |
| 47f | Use analysis account ownership in MCP | 47e | core, mcp |
| 47g | Share reporting period selection | 47f | core, cli, web, mcp |
| 47h1 | Extract MCP serialization | 47g | mcp |
| 47h2 | Extract proposal/advice tools | 47h1 | mcp |
| 47h3 | Extract reporting tools | 47h2 | mcp |
| 47h4 | Extract accounts/queues, finalize facade and size gate | 47h3 | mcp |
| 47i | Document test organization and tighten stale guards | 47h4 | core, scripts |
| 47j | Configure a bounded database lock wait | 47i | core, web, sync |

This is a serial release order to keep one baseline at a time. Parts 47d–47g are
largely independent design concerns. Each part must stay within about ten
requirements, three to five public units, and thirty given test functions; split
again before writing tests if the actual contract surface exceeds those bounds.
47h may move many existing functions without adding public units. No part here
requires a migration. Never add a migration merely to move Python code.

## 47a: categorize and pair as one operation

**Problem:** web rule, alias, and category-clear operations return after
categorizing, leaving eligible transfers counted as spending until a later run.

Add `categorize_and_pair(session: Session) -> CategorizeResult` in
`finances.categorize.service`. It calls `categorize(session)`, then
`pair_transfers(session)`, in that order and in the same supplied session. It
returns the original categorization result, preserving existing count text.
It does not commit, open a session, or swallow errors. Keep `categorize` as the
lower-level operation for callers that explicitly need categorization alone.

The CLI's existing `categorize_all()` remains a thin session/output adapter over
the new operation. Replace the web's categorize-only calls for rule creation,
editing and deletion, alias creation and deletion, bulk “Leave to the rules”,
and a single category clear. Replace existing adjacent categorize/pair calls in
web import, sync, and split clearing so each operation pairs exactly once.
Pair-only operations, including removing a share, keep their narrower behavior.

Accepted rule/alias proposals also change categorization. Route the existing
recategorization in `accept_proposals` through the new operation, preserving
`Accepted` and its conditional `categorized` value. No MCP proposal-submission
tool may invoke it: submission remains inert until a person accepts.

For web mutations the original change, categorization, pairing, and audit records
must commit or roll back together in the existing request session. Do not broaden
this work into changing CLI import/sync transaction boundaries.

**Acceptance scenarios:** each affected web action makes a deliberately freed
synthetic transfer pair visible immediately; spending, budgets, and findings
exclude it in that same completed request. Repeating the action creates no
duplicate pair. Manual categories, split/shared exclusions, confirmed pairs,
and rejected transfers retain existing rules. A forced pairing failure rolls
back the initiating web change and its audit rows. CLI categorization text and
already-working import/sync paths retain their outputs. Proposal creation changes
no pair; accepting a rule/alias proposal performs the intended recategorization.

**Boundaries:** `categorize/service.py`, CLI categorization adapter, affected web
routes, their behavior tests; no pairing algorithm changes and no session-helper
rename. `web/access.py` need not change just to rename `_reading`.

## 47b: faster test execution

Owner-prioritized tooling work (2026-11-15): opt-in local pytest-xdist workers,
timing reports, serial/2/4-worker count and coverage parity, and measured guidance.
Executable [spec](phases/phase-47b-faster-tests.md) and
[guide](verification/phase-47b-faster-tests.md) govern this part. No fixture caching
or evidence-cache automation; migration profiling informs a later decision.

## 47c: explicit proposal-kind refusal

Both `accept_proposal` and `proposal_out_of_date` must reject a kind outside
`finances.domain.proposals.KINDS` with `ValueError("unsupported proposal kind")`.
The message never echoes stored values. Check before dependency/staleness
dispatch or any write. Existing missing/non-open proposal checks still apply
when loading an acceptance target.

Acceptance must have an explicit `CATEGORY` branch. Staleness must have explicit
`TRANSFER` and `NOT_TRANSFER` branches. Every remaining fallback raises the same
error, including a future kind added to `KINDS` before its handler exists.
Unknown kinds must not mark a proposal decided, alter categories or pairings,
or create an audit record. Existing kinds preserve their validation order,
refusals, dependency ordering, and accepted results.

Use a complete kind-coverage test matrix for acceptance and staleness. An unknown
kind's test must reach dispatch even if the current schema prevents persisting
that value: use a synthetic domain proposal and an isolated fake row/load seam
for acceptance, without weakening database constraints. A schema rejection alone
does not prove safe dispatch.

**Acceptance scenarios:** all known kinds take their intended path; an unknown
kind with an otherwise valid category target produces the constant refusal and
zero writes; a kind temporarily added to the supported inventory but without a
handler is still refused; normal category and transfer proposals still work.

**Boundaries:** proposal dispatch, focused tests, and existing boundary error
adapters only if they need to translate this ValueError. No dispatch framework,
new kind, migration, or MCP write permission.

## 47d: reason and timestamp helpers

Add pure `clean_reason(reason: str) -> str` in `domain/proposals.py`. Collapse
whitespace using the existing domain helper, then require one through
`PROPOSAL_TEXT_LIMIT` characters. Preserve exactly
`a reason must be 1 to 200 characters` on refusal. Validate the cleaned length;
do not truncate a person's reason. Replace all proposal-reason copies, retaining
each caller's surrounding validation order.

Add `utc_now() -> datetime` in `db/time.py`, returning an aware UTC timestamp.
Repository modules call it through the module so tests have one replacement
point. Replace the eight repository `_now` copies named by the audit, including
audit, advice, and finding decisions. Migrate affected test clock patches in the
given diff. Keep local calendar `clock.today()` and web session/auth clocks
separate; no timestamp precision or ordering changes.

**Acceptance scenarios:** whitespace-only refusal; collapsed whitespace; exactly
200 characters accepted and 201 refused; each proposal writer actually uses the
helper; one controlled UTC clock reaches created, decided, advice, finding, and
audit timestamps. Existing before/after audit values and validation precedence
remain identical. Retain distinct event times where existing calls read twice.

**Boundaries:** the two helpers, their callers, and tests patching moved clocks.
No generic repository superclass or mass rewrite of timestamps outside this set.

## 47e: parser line flattening

Add `flatten(pages: list[str]) -> list[str]` in
`ingest/parsers/helpers.py`. Return each `splitlines()` line, stripped, in page
and line order. Preserve blank lines as empty strings. Do not squeeze internal
whitespace, drop empty lines, join page boundaries, or alter dates/signs.
Replace the duplicated flatten expressions in the six parser modules, including
Marcus CD handling. Every parser continues to own detection and section rules.

**Acceptance scenarios:** empty input/page, blank lines, CRLF, multiple pages,
internal spaces, and no final newline; all existing synthetic bank layouts
produce identical records, section totals, and reconciliation. Give complete
branch coverage for the touched critical helper module. No real statement text
is inspected or used to produce fixtures.

**Boundaries:** parser helper and six callers plus tests. Shared fixture-loading
helpers may be extracted only when the affected tests actually duplicate the
same operation. Do not introduce parser inheritance or a section-walker framework.

## 47f: MCP account ownership from analysis

Make `mcp_server.tools.list_accounts` load through `analysis.listings.account_listing`.
Preserve every JSON key, ordering rule, inactive-account option, and value:
unassigned is `owner: null, joint: false`; joint is `owner: null, joint: true`;
sole ownership is the person's name and `joint: false`.

`AccountListing.owner` currently carries display attribution. Extend the data
contract with `joint: bool = False`, computed from the ownership records in
analysis. Keep the current `owner` field's meaning for CLI/web callers. The MCP
serializer uses the explicit boolean to choose its owner value; it must not
infer jointness from a display string that could also be a person's name.
Do not duplicate ownership queries or attribution rules in the tool.

**Acceptance scenarios:** unassigned, sole, joint, inactive accounts; a person
whose name equals the joint display label; identical CLI/web listings and MCP
schema before/after. MCP still runs under its existing read-only session.

**Boundaries:** analysis listing data, the one MCP tool, focused tests. Transfer
ordering and spending-summary serialization are separate contracts, unchanged.

## 47g: shared reporting period selection

Put the common month-versus-range rules in `domain/periods.py`, with explicit
`today: date` input. The domain must not read a clock or know CLI option labels,
HTTP forms, or ToolError. Reuse `month_range` for accepted month syntax.

The implementation spec will fix a small typed result/error contract after
capturing the existing boundary behavior. Required shared decisions are: a month
cannot accompany endpoints; endpoints must be supplied together; no selection
means the month containing the supplied day; a valid month or explicit range
returns inclusive dates. Preserve current reversed-range refusal through report
validation and preserve the order of existing argument errors.

CLI continues converting Typer datetimes to dates; web continues parsing its
date text; MCP continues receiving typed dates. Adapters translate shared
selection errors to their existing messages and exception types. Empty CLI
month text and empty web fields must retain their established behavior rather
than being silently made equivalent. MCP `get_spending` gains no month argument.

Move the web spending-form adapter to a shared web helper module used by reports
and export. Do likewise for the CLI report/export adapter. Reuse a shared pure
first-day helper for callers with equivalent month/default behavior. Other
cross-route helpers, such as transaction search parsing, are not swept into this
phase.

**Acceptance scenarios:** month, endpoints, defaults, incomplete range, conflicting
selection, malformed month/day, reversed dates, leap February, December/January,
and a controlled local date. Pin CLI text/exit codes, web status/form text, and MCP
ToolError separately. Report and export select exactly the same dates and rows.

**Boundaries:** domain periods, shared front-end adapters, report/export callers,
MCP period callers, related tests. If the captured caller matrix exceeds phase
limits, split the domain/CLI/web and MCP integrations before writing given tests.

## 47h: split MCP tools by responsibility

**Owner decision (2026-11-16): four stages, with independent review and commit
between them.** 47h1 moves serialization only; 47h2 moves proposal/advice tools;
47h3 moves reporting tools; 47h4 moves account/balance and transaction/work-queue
tools, completes the supported facade and applies the final global size gate.
Each executable spec is issued against its approved predecessor. The
[47h1 spec](phases/phase-47h1-mcp-serialization.md) and
[guide](verification/phase-47h1-mcp-serialization.md) are approved. The
[47h2 spec](phases/phase-47h2-mcp-proposal-tools.md) and
[guide](verification/phase-47h2-mcp-proposal-tools.md) are approved, including
the shared month helper needed by proposal and reporting consumers. The
[47h3 spec](phases/phase-47h3-mcp-report-tools.md) and
[guide](verification/phase-47h3-mcp-report-tools.md) are approved. The
[47h4 spec](phases/phase-47h4-mcp-facade.md) and
[guide](verification/phase-47h4-mcp-facade.md) finalize accounts/queues and a
permanent recursive 400-line gate in the standard full synthetic check.
New modules meet 400 lines immediately; the shrinking tools.py has a temporary
monolith exception through 47h3. That exception expires at 47h4, when any remaining
facade exception is limited to imports alone. No arbitrary helper relocation.


Keep `finances.mcp_server.tools` as the supported facade. Move implementations
into cohesive modules under `mcp_server`: account/balance tools, reporting tools,
transaction/work-queue tools, proposal/advice tools, and proposal serialization.
Keep access policy in `access.py` and registration/descriptions in `server.py`.
Area modules must not import the facade; dependencies point toward shared helpers.

Capture the public tool inventory before moving code. Preserve names, signatures,
annotations, descriptions, field defaults, row caps, pagination, JSON shapes,
ordering, error translation, and registration. Move patch points in tests through
an explicit given diff; do not add compatibility shims for private helpers solely
to preserve accidental imports. Keep necessary public re-exports.

Introduce a 400-line source gate for MCP modules, with a documented facade
exception only if needed for imports alone. Do not replace large functions with
arbitrary helper relocation to pass the gate. Update the obsolete read-only
docstring to describe both read tools and proposal/advice writers.

**Acceptance scenarios:** inventory and generated schemas unchanged; whole JSON
examples for every proposal kind; each read tool rejects writes; writer tools
touch only allowed proposal/advice data; pagination/error cases unchanged;
registration has neither missing nor duplicate tools. Existing end-to-end tool
tests remain behavioral evidence after patch-path edits.

**Boundaries:** MCP modules and their tests. Keep current transfer ordering and
spending field conversion; serialization is an adapter responsibility. No ORM or
repository split in the same phase.

## 47i: test and documentation maintenance

Update `docs/testing.md`: new tests are named for the behavior and their layer;
the ten-second unit-suite statement is a historical aspiration, not a measured
gate. Existing `*_more.py` files remain valid. When one is deliberately reorganized,
give an exact move map and update section patterns and imports without losing
cases. A bug fix does not require unrelated test renames.

Narrow `STILL_LOADING` to actual permitted result-type dependencies. Preserve
the guard against database queries in views. Record that importing a service's
result dataclass is coupling, not evidence that a view performs IO. Move result
types only when their service/view contract next changes.

**Acceptance scenarios:** before/after collected node mapping accounts for every
renamed case; section assignments stay correct; a planted forbidden dependency
is detected; remaining result-type imports are permitted. Avoid suite-wide
deduplication: front-end regression tests remain useful even when core rules
also have direct tests.

**Boundaries:** testing docs, the stale view guard, exact test moves if justified,
section patterns. No source renaming campaign or release-version bump.

## 47j: a bounded SQLite lock wait

Add settings `db_busy_timeout_ms: int = 30000`, constrained to 0 through 120000,
from `get_settings()` (`FIN_DB_BUSY_TIMEOUT_MS`). Configure every SQLite connection
created by `get_engine` with that timeout using the driver's connection option
(milliseconds converted to seconds here are elapsed time, not money). Retain
foreign keys and read-only query enforcement. No operation-level retry loop and
no automatic replay of a transaction.

The timeout applies to file and in-memory engines, explicit URLs, and read-only
calls. Document that it bounds lock waiting, not the entire operation; SQLite
can still reject an upgrade/deadlock immediately. Exhaustion retains existing
rollback/error behavior. Keep engine creation/disposal lifetime unchanged.

**Acceptance scenarios:** settings validation and default; two independent file
connections with a held writer lock; a waiting writer succeeds after release;
an unreleased lock fails within a bounded test timeout and commits no partial
data; foreign keys and read-only refusals still hold. Coordinate workers using
events, assert database contents, and use generous deadlines rather than exact
elapsed-time assertions. Never sleep for the production thirty-second default
in a test. Include test-environment isolation for the new setting.

**Boundaries:** config, DB engine, engine tests, environment-isolation tests,
`.env.example`, relevant operations docs. No dialect-specific business queries;
connection configuration remains inside the existing SQLite engine boundary.

## Deferred work and explicit triggers

| Finding or observation | Disposition / trigger |
|---|---|
| WAL and overlapping writers | Separate design only when overlap warrants it. Must cover checkpointing, sidecar files, online backup, restore while CLI/sync run, and crash recovery before enabling WAL. Busy timeout does not solve cross-process restore safety. |
| `orm.py` size | Split by area when the next table needs a home. Preserve one metadata/Base and existing imports; tables/converters move together. No generic mapper. |
| Repository size pressure and long category deletion | Extract cohesive category-deletion or proposal modules when the next change reaches the cap. Never move unrelated helpers merely for line count. |
| Long health/import/feed functions | Keep tested behavior; split only for a concrete extension or an independently bounded refactor. |
| `to_account` UTC normalization | Use `_as_utc` when the converter is next changed; test naive and aware inputs then. |
| History URL builder in views | Move beside the History route when that route changes; preserve all kind links and query escaping. |
| `_reading` and cross-route private helpers | Rename/extract only when that module's session/helper API is changed. No broad mechanical rename in 47a. |
| Result types imported from services | Extract to a neutral contract module when the type changes, retaining behavior; no blanket move now. |
| CLI tag/import/sync/doctor tables | Move each to views when its output is next changed; pin complete displayed rows. |
| English detail in domain findings/health | Keep stable for CLI/web/MCP. A structured-finding redesign needs its own consumer/versioning plan. |
| Transfer row order differs in MCP | Preserve the existing MCP order. Aligning it is an explicit API behavior change, not necessary for code splitting. |
| MCP spending field names/summary conversion | Keep stable names and values during 47h; do not change financial totals in a file-move phase. |
| Per-call engines and pragma-based read-only protection | Retain current design. Pooling or URI read-only mode needs separate lifecycle/permissions tests. |
| Missing-password access and forwarded HTTPS header | Record as operational boundaries; no authentication-policy redesign in this remediation. Follow `remote-access.md` before exposing the service. |
| Parser section/date errors that reconcile; BoA ambiguity | Preserve fail-safe detection and synthetic layout regressions. Add a layout-specific fix when an actual supported layout requires it. |
| String widths, logging filter limits | Preserve explicit boundary validation and no-sensitive-logging tests; do not treat the regex filter as permission to log financial values. |
| Version `0.1.0`, long progress log | Release numbering belongs to release policy; keep progress append-only and roadmap as the index. |

The audit's “Leave alone” list remains out of scope: parser inheritance, a generic
section walker before a third matching layout, repository classes, merging ORM
and domain rows, putting every parser on the critical list, and a generic
exception hierarchy.

## Verification and release contract

See [the verification plan](verification/audit-remediation-design.md). Every
implementation part ships alone from a committed baseline, receives its own
review, and updates progress before the next part's executable spec is issued.
No real-data repair, migration, or background recategorization is scheduled by
this design. The first affected user action or explicit categorization run
applies the pairing repair using existing rules.
