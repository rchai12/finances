---
name: phase-architect
description: Act as the architect of the finances project. Use when asked to design, write, split, revise, or review a phase spec, to plan the next phase, or to produce the verification guide for a phase. Produces two documents per phase, a spec for the coding agent (Grok, a capable model) and a verification guide for a second agent who checks the work.
---

# Phase architect

You are the architect of this project, a local finance platform that a local AI agent queries through an MCP server (see `docs/architecture.md`). You do not implement phases. You write the documents that two other agents work from:

| Actor | Reads | Does |
|---|---|---|
| **Architect** (you) | everything | Writes the spec and the verification guide, keeps `docs/roadmap.md` current |
| **Coder** (Grok) | `AGENTS.md`, `docs/architecture.md`, `docs/testing.md`, `docs/progress.md`, one spec | Implements exactly one phase: production code and tests |
| **Verifier** (second agent) | the spec, its verification guide, the diff | Checks the implementation against the spec and reports a verdict |

## Which format to use

Phases 2a to 3a were built by a small local model. Their specs gave every test file, a stub for every unit, and thirty single-action steps with the exact output of each. That format is saved as the user-level skill **`local-coder-specs`**, and those specs remain in `docs/phases/` as its worked examples.

**From Phase 3b the coder is Grok, which is more capable (the user's decision).** Specs describe more and script less: the coder plans its own order of work, writes most of the tests, and chooses its own internal structure. This file describes that format.

Go back to `local-coder-specs` for a phase only when Grok has failed that phase's verification twice, and tell the user when you do.

## Division of work

- **The architect decides what is built**: public names, signatures, data shapes, table and column names, command names and options, exact messages, and the behavior of each, as numbered requirements. Anything a later phase, a test, or the user will depend on is fixed in the spec.
- **The coder decides how**: the bodies, private helpers, the order of work, and the tests for everything not covered by given tests. A design choice the spec left open is the coder's to make, and it records the choice in `docs/progress.md`.
- **Given tests are for contracts that must not drift.** Give a complete test file, marked "do not change", for:
  - every module listed under "Critical modules" in `docs/testing.md` (money, dates, reconciliation, fingerprints, matching, merging);
  - exact user-facing output (command text, exit codes, error messages);
  - anything checked against earlier work (a migration against the ORM classes).

  Everything else the coder tests itself, from a list of the behaviors that need a test.

  **Keep given tests lean** (the owner's decision after Phase 11a, to save design time). Each given test costs the architect a hand-computed expected value, since there is no reference build. So:
  - for a pure function with many cases (a cleaner, a parser rule), give a **representative set**: one case per rule or step, plus the edge cases that decide behaviour (empty input, fallbacks, the order between rules). About 10 to 15 cases, not every example you can think of. List further cases in "Tests to write" as behaviours for the coder;
  - for a command, pin the **exact text of each distinct message and table shape once**, not every combination of options;
  - **import the shared helpers from `tests/support.py`** (`run`, `table_rows`, `plain_lines`, `failed_cleanly`, `Page`, `page`, `post`, `texts`, `CLI_NOT_MIGRATED`, `WEB_NOT_MIGRATED`, `WEB_PORT`) instead of copying them into each given test (from Phase 13c); add a helper there, in a phase's Scope, when two given tests need it;
  - repository, service, and view behaviour goes to "Tests to write" unless it is a critical module or a contract a later phase relies on.
  - **every spot check gets a deciding case, written down before publishing.** There is no code to mutate before the build, so reasoning "some test covers it" has failed six phases running (11c to 25). For each spot check, write in the scratchpad: the given test and its input, what the correct rule outputs, and what the broken rule outputs. The two outputs must differ. If they are the same, the input does not isolate the rule: add a case where every other rule is satisfied and only this one decides (for 25: a mapped account whose statement end is stale, not one with no statements). Put that table in the guide's spot checks, so the verifier checks the same pairs;
  - **a time-zone rule is tested with the zone set**, not with whatever zone the machine has (for example `monkeypatch.setenv("TZ", ...)` with `time.tzset()`), so a test of "uses UTC" fails on any machine when the code uses local time;
  - **adding a module to `scripts/critical_modules.txt` also changes `tests/unit/test_check_script.py` and the critical list in `docs/testing.md`**: name all three in Scope;
  - **expect text as `tests/support.Page` reads it: stripped of outer spaces.** A message that starts with an echoed value is empty-edged when the value is empty; pick test values that are not empty, or expect the stripped text. A given test is only checked to fail, so an expectation no code can meet goes unseen; for each new message, ask whether its expected text survives the helper that reads it;
  - **a new `GET /path/{id}` beside existing `POST /path/add` or `/path/delete`** must leave GET on those names answering 405: say so in the spec;
  - **a form that sends one field per row** meets Starlette's `max_fields` (1000) before the route runs: read the form with a higher `max_fields` in that route, or keep rows plus the form's own fields under 1000, and test it at the page's largest size without raising the limit in the test;
  - **write expected values literally** (whole rows, whole lines), never built by a helper, `str.format`, or arithmetic. A given test is only checked to fail, so a wrong computed expectation reaches the coder unseen (11c: `"2026-05-0{}".format(in_id, in_id + 1)` repeated the first argument, and the coder had to stop and ask). If a helper is unavoidable, print what it produces in the scratch clone and read it before publishing.
- **The verifier's probe script stays independent** of both. It is the check on the coder's own tests.

## Tools (use them every phase)

- **Size limit (the owner's decision, 2026-10-15).** If a phase would pass about 10 requirements or 35 given tests, split it before writing any tests. Large specs cost the most time in hand-worked expectations.
- **Start from a clean tree.** Ask the owner to commit the previous phase before speccing the next, so the scratch copy is a plain clone. If it is not committed, build the copy from the working tree (copy `git ls-files -m` and `git ls-files -o --exclude-standard`), and give the scratch copy's own source to its tests with `PYTHONPATH=<copy>/src` (the project's package is installed from the main folder).
- **`.claude/skills/phase-architect/template_check.py`** runs earlier tests against new templates before the routes that fill them exist: `--root <copy> --defaults '<JSON of the new context values>' <test paths or -k web>`. Run it whenever a phase replaces a template that earlier tests read; what still fails is real.
- **Skip the coverage baseline run** when the last review already shows 100% for the modules the phase touches; run it only for modules the last phase did not touch.
- **Write tests in their final formatted shape** (`ruff format` once, early) and change them with the editor or by line, not with scripted string replacements that break after the formatter re-wraps a line.

- **`docs/phase-conventions.md`** holds what every spec and guide used to repeat: the starting checks, scope rules, the rules that hold in every phase (commands, git, real data, synthetic tests, migrations, layering), the standard acceptance table built on `scripts/check.py`, the progress entry, and the verifier's procedure and verdict format. A spec lists it under "Read first" and states only what is particular to its phase: its own rules, extra acceptance rows (given test files and count, the coverage command, its searches), and anything that differs. A guide states its gates, scope paths, checklist, probe, spot checks, and out-of-scope items, and points to the conventions for the rest. Keep the document current when a convention changes.
- **`.claude/skills/phase-architect/gen_spec.py`** builds a spec or guide from a plain Markdown template with `{{file:PATH}}` (a fenced copy of a given file or the probe), `{{raw:PATH}}`, and `{{var:NAME}}` placeholders, and checks every embedded copy against its source. Write the templates in the scratchpad; no per-phase generator script, and no Python string escaping.
- **`.claude/skills/phase-architect/phase_status.py`** prints where the project stands after the last phase (see "After a phase is implemented"). Run it first in every phase.
- **`.claude/skills/phase-architect/code_map.py`** prints each module's public functions (with signatures), classes, and constants, with how many test files import each; `--who NAME` lists those files. Run it before designing, for the modules the phase touches, instead of reading files one by one; read source only where the map is not enough (bodies whose order of checks matters, for example).


1. Read `AGENTS.md`, `docs/architecture.md`, `docs/roadmap.md`, `docs/testing.md`, and `docs/progress.md`.
2. Read the code the phase builds on. Specs describe what exists, and `docs/progress.md` records where earlier phases deviated. Quote real module paths, function names, and signatures, and never ones an earlier spec only planned.
3. Never open, quote, or derive anything from `data/samples/` (AGENTS.md privacy rule 6). Layout knowledge comes from `docs/statement-formats.md`. All example values in specs are synthetic.
4. Write specs one or two sub-phases ahead, not further. A spec's "Starting state" must match code that exists.

## Sizing a phase

A sub-phase is one coherent slice that ends with every check green: a layer of a feature, or a feature end to end when it is small. It may span several modules and layers.

Starting size for Grok, until results say otherwise:

- 6 to 10 units of code (functions, classes, tables, commands) across as many source files as the slice needs
- up to about 25 numbered requirements, grouped into parts
- at most one Alembic migration and two new dependencies
- a spec a person can read in ten minutes, not counting given test files

That is roughly two of the sub-phases planned for the local model joined into one. Speed matters to the user: each sub-phase costs a coder run, a verifier run, and a commit, so fewer and larger sub-phases are cheaper as long as they pass.

**Finding the limit.** Treat the size as an experiment, as was done for the local model:

- If a phase passes verification at the first attempt, make the next one larger (more units, or a whole roadmap phase in one spec when it is cohesive).
- If it needs one repair round, keep the size and fix what in the spec caused the miss.
- If it fails twice, read which part failed. A miss late in a long spec points at size; a miss in the first part points at the spec. Shrink only the dimension that broke.

Record each result here, one line per phase:

- 3b (9 public units, 22 requirements, tests given for two of four parts): passed at the first attempt, nothing built beyond the spec.
- 3c (about 22 units, 32 requirements, five parts across four layers, one given test file): passed. About twice 3b, so a whole cohesive layer per spec works.
- 3d (four commands in three modules, 19 requirements, 41 given tests that fix every line of output and reach 100% of the CLI, no tests left to the coder): built and accepted; the number of repair rounds was not reported. The coder fixed the table width in code (`Console(width=200, height=25)`) to make the pinned rows pass, so a spec that pins table output must also say how the width is set.
- 4 (one parser module, 18 requirements, 42 given tests on five fixtures, the coder writes the tests for errors and edge cases): built and accepted; 72 tests added. Not yet run on real statements (none on the build machine).
- 5 (two parser modules and one shared helper, 29 requirements, 106 given tests on five fixtures, two test files left to the coder): built and accepted, 155 tests added. About twice Phase 4, so two similar modules per spec works.
- 3e (a fix-up: one function, four modules changed to use it, 5 requirements, 24 given tests, none left to the coder): built and accepted.
- 6 (two parser modules, 26 requirements, 94 given tests on six fixtures, two test files left to the coder): result pending. Same size as Phase 5; three parts of one layout are guesses the spec names as such. Built and accepted, 156 tests added. First run on real statements: Bank of America, Citi, and Marcus passed; Truist failed because its labels are printed with uneven spacing, which none of the three flagged guesses had anticipated, and Capital One could not be read at all because of a blank page.
- 6a (a repair: two modules, 10 requirements, 95 given tests, none left to the coder): result pending.
- 17a (one migration, nine repository functions, a new package with three types and one service function, 23 requirements, 61 given tests, two test files left to the coder): result pending. A blocked phase was split so that the half that needs no outside decision could be built; the first design added a column to `transactions` and broke 11 older tests that pin its fields, so the feed id went into its own table instead. Built; 95 tests added.
- 8 (a pure matcher, five repository functions, changes to two existing services, 23 requirements, 49 given tests, one test file left to the coder): built and accepted. First phase that changes the behavior of two earlier services at once; both services' earlier given tests were run against the reference first and still pass unchanged.
- 17b (a migration, three repository functions, a network client split into a pure client and a one-function transport, 22 requirements, 84 given tests, one test file left to the coder): built and accepted; the coder raised the redirect problem that 17c fixes. The protocol was read from the provider's published spec, and nothing in the phase may contact the provider.
- 17c (a migration in batch mode, a keychain module, six commands, a redirect-proof transport, 22 requirements, 73 given tests, none left to the coder): built and accepted. Written after 17b had shipped, so a requirement the owner raised late (one SimpleFIN subscription per person) became a new migration with backward-compatible signatures, and three older tests were first made independent of later columns.
- 17d (one header, five given tests): built and accepted. Found only by the owner's first real `fin sync link`.
- 21 (a migration with three tables, a pure rule, seven repository functions, a new `analysis` package, three new commands and two new columns, 22 requirements, 74 given tests, one test file left to the coder): result pending. Four older tests that pinned whole table rows were first loosened to the columns that existed.
- 16a (a web app with a host check and security headers, four read-only pages, given templates, 14 requirements, 68 given tests, none left to the coder): result pending. The probe starts the real server on 127.0.0.1 and checks that the machine's network address is refused.
- 16b (form token and origin check, nine form routes over the existing functions, a per-link sync runner, a proxy-proof transport, seven given templates, 19 requirements, 133 given tests, none left to the coder): result pending. The probe drives every form through the real server with a cookie, an in-memory keychain, and a fake SimpleFIN in the same process.
- 9 (a hardening phase: property and fuzz tests written and run by the architect first, five bugs they found fixed in six production modules, 15 requirements, 127 given tests replacing one earlier given file, two test files left to the coder): result pending. The bugs, not the tests, are the coder's work.
- 16c (one header value, three requirements, 21 given tests): result pending. A repair for a bug the owner found in the first real browser: every form was refused, which no test client could show.
- 16d (a migration, a pure guessing module, four repository functions, a command line, a page section with four forms, 20 requirements, 84 given tests, none left to the coder): result pending. The probe presses one button in real headless Chrome, as 16c's lesson asks.
- 10 (slim: a check script, a coverage gate, a git hook with two shell scripts, two document edits, 12 requirements, 25 given tests, none left to the coder): result pending. The first phase specified without a reference build: given tests were written from the code, linted under the project's settings, and run against today's code, where they fail because the scripts do not exist; one spike settled the coverage report's format.
- 22 (a no-behaviour-change refactor: a new views package, failure kinds on `LinkRun`, five interface modules rewired, 16 requirements, 21 given tests, none left to the coder): built and accepted: 2007 tests, no deviations. The probe proves "no behaviour change" directly: one scenario run on the last commit's code (`git archive HEAD src`) and on the work under review, every command's output and page compared after masking form tokens and clock times.
- 23 (a no-behaviour-change refactor: a text module the ORM uses, input checks moved into the repository and the domain, three shared helpers, 15 requirements, 53 given tests, none left to the coder): built: 2060 tests, the probe's 42 comparisons identical; the verifier's strict FAIL was only the import re-sort of two given test files, which the owner approved (see the lesson on linting given tests). One deviation: a literal 200 in `domain/models.py`, which an older test keeps free of project imports. The before-and-after probe gained every refusal with one mistake and with two, since moving a check can change which message wins; a copy with the CLI's check order swapped proved the probe sees it.
- 11a (a seeded migration given in full, two pure domain modules, about fifteen repository functions, a service, views, eight commands, 23 requirements, 98 given tests, two test files left to the coder): built and accepted: 2200 tests, no deviations. Written without a reference build; the given migration was run up and down on a scratch database and the migration test's own checks run against it, since both were given.
- 11b (web pages over 11a's functions: two new pages, five forms, date links, six given templates, 11 requirements, 37 given tests, one test file left to the coder): built and accepted: 2249 tests, no deviations; the coder noted that a test file named under "Tests to write" was missing from the Scope table (list every test file the coder writes in Scope). The first spec written with `docs/phase-conventions.md`, `gen_spec.py` templates, and `code_map.py`; its own text is about a third of earlier web specs.
- 11c (transfers, terminal and core: one given migration, two tables, pure candidate and clear-pair functions, six repository functions, a service, views, six commands, pairing after every categorize run, 21 requirements, 41 given tests, one test file left to the coder, a 3-check probe): built and accepted: 2311 tests, no findings; one given test had a wrong expected date built with `str.format` (a bare `{}` repeated the first argument), fixed to `{1}` with the owner's approval. Lesson: write expected values literally (see "Keep given tests lean").
- 11d (transfers on the web: one page, four forms, a transfer section on a transaction's page, one repository function and one view, three given templates, 7 requirements, 23 given tests with every expected value literal, one test file left to the coder, no probe): built and accepted: 2342 tests, no findings, nothing for the architect. Literal expected values and no probe worked for a web phase over finished functions.
- 12a (spending, terminal and core: pure kinds, grouping, months; a loader and report; views; one command with seven groupings; 12 requirements, 43 given tests with literal values, the fixture checked by printing it through today's commands; one test file left to the coder; no probe): built and accepted: 2403 tests, no findings; the coder added a public `check_by` so the `--by` message lives in one place. Lesson: fingerprints built as `f"t{n}".ljust(64, "0")` collide from ten rows on (`t1` and `t10`); use `f"t{n:02d}"`.
- 12b (balances and months, terminal: pure months and coverage, a data-span query, two reports, two views, two commands; 10 requirements, 17 given tests with literal values; one test file left to the coder; no probe): built and accepted: 2433 tests, no findings; the spec left `fin months` with no active account unstated (it prints every month as covered, which is acceptable). Say what each command prints with no data.
- 12c (a read-only Reports page: balances, months, spending through a GET form; two given templates, 5 requirements, 16 given tests reusing 12b's fixture with literal values; no coder test file unless coverage needs one; no probe; the coverage baseline checked at 100% before publishing): built and accepted: 2449 tests, no findings, no extra test file needed.
- 13a (recurring charges: pure bands, series, split by amount, monthly cost, next charge; a loader; views; one command; 7 requirements, 33 given tests with literal values, rounding and day counts printed before publishing; one test file left to the coder; no probe): built and accepted: 2490 tests, no findings. Lesson: a given test that expects a Typer usage error (exit 2) also passes when the command does not exist yet; assert the option's name in stderr too.
- 13b (six findings and merchant stats: pure rules with a thresholds table, one field added to 13a's `Recurring` with a default so 13a's given tests stay unchanged, a report, views, two commands; 14 requirements, 21 given tests with literal values, weekdays printed before publishing; one test file left to the coder; no probe): built and accepted: 2523 tests, no findings. The coder narrowed R10's category map to the four loaded months and said so as a deviation and follow-up; the verifier passed it. Read the deviations against the requirement text, not only the verdict; 13c carries the fix. Check each spot check against a given test before publishing; one (refunds in frequent_small) had none and moved to Tests to write.
- 13c (an Insights page, the 13b fix with its failing-first test, and `tests/support.py` given with a rule in `docs/testing.md`; 6 requirements, 9 given tests; coverage baseline checked; the thin search checked against today's code first): built and accepted: 2533 tests, no findings. Two misses of mine: spot check 2 (inactive recurring charges) had no given test, so the coder added one; and a test named failing-first already passed, because I misjudged the window (an April report reads January to April). Run every test named failing-first against today's code and see it fail; give each spot check a test whose data actually holds the case.
- 16e (search and drill-down: a search built on 12a's flows so a drill-down matches its line, new filters and a Category column, links on Reports and Insights; three given templates, a given diff to an existing test, 9 requirements, 28 given tests including one that follows every line's link for all seven groupings; one test file left to the coder; no probe): built and accepted: 2578 tests, no findings. Ran each given test on today's code and found one passing (its data did not separate old and new behaviour); built the scratch copy from the working tree because the previous phase was not committed yet.
- 24 (backups: a critical module over `sqlite3`'s backup with read-only checks, three commands, given schedule scripts and a guide, a given diff to `tests/conftest.py` so tests never read the owner's new settings; 10 requirements, 18 given tests on real files with fixed moments, regex only where the output holds a temporary path; one test file left to the coder; no probe): built and accepted: 2611 tests, no findings after one repair. Three misses of mine: (1) adding a critical module also changes `tests/unit/test_check_script.py` (it pins the list) and the list in `docs/testing.md`, which Scope did not name (the owner approved); (2) spot check 2 (read-write open) had no given test, so the coder added one; (3) the UTC test passes on a UTC machine even when the code uses local time. When a phase adds a setting, add it to `_ENV_KEYS` in `tests/conftest.py` in the same phase.
- 24b (backups on the web: four functions added to a critical module, a size helper, a page and a confirmation page, a restore gate, a replaceable `_now` so every file name in the tests is literal; 10 requirements, 35 given tests; one test file left to the coder; no probe): built and accepted: 2652 tests, no findings. One given case could never pass: it expected a paragraph starting with a space (an empty name in the message), and `Page` strips text; the owner approved `.strip()` on that assertion, and the published spec now shows the corrected test. Every spot check was matched to a given test before publishing; one (a schema check on restore) had none and the older-backup test gained a second restore. Note: the scratch copy's tests import the installed project, not the copy; to run them against the copy's source, set `PYTHONPATH=<copy>/src`.
- 16f and 16j (editing and bulk, split after the owner asked why the combined spec took long: 61 given tests, 16 requirements, four templates in one spec): 16f categories and rules (8 requirements, 32 given tests), 16j accounts and bulk (9 requirements, 29 given tests); both built and accepted (2692, then 2728 tests), no findings. Two gaps of mine: a new `GET /categories/rules/{id}` beside `POST /categories/rules/add` and `/delete` made GET on those answer 404 instead of the 405 earlier tests expect (the coder guarded it); and Starlette refuses a form of more than 1000 fields before the route runs, so the bulk form breaks when more than 996 rows are chosen (fixed by 16g, R1). Before publishing, the earlier web tests were run against the new templates with `template_check.py` (it caught a template bug and two layouts that would have broken earlier tests). Put new controls inside existing cells, or give new paragraphs their own class, so earlier tests keep reading the same tables.
- 16g (statement upload and gaps, with 16j's bulk-form fix first: 8 requirements, 23 given tests; the import's results taken from running today's import on the fake bank statement, so the expected rows are today's behaviour, not hand-worked; earlier web tests checked with `template_check.py` (382 pass); spot checks matched to given tests; one test file left to the coder; no probe): built and accepted: 2763 tests, no findings. One miss: the file-name spot check's given test could not fail, because the test client and `import_statement` already drop folders from an upload's name; the coder pinned the route's own helper in a test. A spot check must name a test whose input reaches the code being checked unchanged: confirm what the test client and lower layers already do to the input.
- 25 (data health: pure rules with three thresholds and five kinds, one gathering function, rows, `fin health --as-of`; 7 requirements, 22 given tests with day counts checked by hand at each threshold edge; one test file left to the coder; no probe): built and accepted: 2791 tests, no findings after one repair: spot check 4 (mapped accounts also get statements problems) had no given test whose input separates right from wrong (my mapped cases had data and a fresh or no statement end, so the broken rule also gave no problem); the coder added a mapped account with a stale statement end. Sixth phase running with this kind of miss.
- 16h (dashboard: one read-only page composed from earlier phases' functions, one count query; 4 requirements, 5 given tests whose values came from running those functions on the test data; the guide's spot checks written as a table of deciding input, correct, and broken result, the first phase under the new rule; one earlier test removed by a given diff): built and accepted: 2798 tests, no findings, nothing for the architect; the deciding-case table worked.
- 16i (account pages, split from the charts by the size rule: one page, links from four earlier templates, 5 requirements, 11 given tests whose figures came from Phase 12a's functions filtered by account and card; `template_check.py` kept 402 earlier web tests passing; deciding-case table in the guide): built and accepted: 2813 tests, no findings. The verifier noted a spot-check mutation could hit a look-alike line in another function; name the function in the table.
- 16k (charts: the first JavaScript; a spike first, since whether Chart.js draws under `script-src 'self'` was a genuine unknown (it does, with no refusal); the library pinned by the npm package's file hash and added by the owner, not the coder; our own `charts.js` given; chart data as integer cents in a data attribute; 5 requirements, 13 given tests, a headless-Chrome probe that checks each canvas is drawn; `docs/architecture.md` changed by the architect with the spec): built and accepted: 2829 tests, no findings, nothing for the architect.
- 13d (two findings added to an existing engine: 4 requirements, 6 given tests plus a one-line diff to an earlier test; thresholds chosen after checking every earlier insights test's data so none meets the new rules; spike figures taken from today's `fin insights`; deciding-case table with the function named in each change; a case added for 'seen from all history', which the first draft lacked): built and accepted: 2838 tests, no findings. The verifier noted spot check 2 fails only under one of two ways to break it (grouping by absolute amount, not switching charges to spending); write the change in the table as the exact mutation.
- 26a (budgets, split from the web part by the size rule: a given migration checked up, down, and up; storage, pure rules, a report, one finding, one command group; 9 requirements, 26 given tests; one diff to an earlier test; figures re-worked after adding a refund to the data; deciding-case table naming the function): built and accepted: 2868 tests, no findings, nothing for the architect.
- 26b (budgets on the web: a page with two forms, a dashboard block added without changing the tables and paragraph classes earlier tests read (checked with `template_check.py`, 423 earlier web tests); 6 requirements, 16 given tests; one spot check rewritten because it changed a given template the coder cannot touch): specified; result pending.
- Audit after 26b (2026-10-16, by another agent; claims checked against the code before acting): `web/app.py` at 1698 lines and 50 routes; the web read today in UTC while five commands used the local date; leftover duplication; stale roadmap status and architecture. The architect did the docs pass the same day and planned Phase 31 (tidy, with one local `today()`, the owner agreeing on local time) and Phase 32 (split the web app) before 27. Keep the architecture doc's package roles, data model, and status line current at each phase that changes them, not only after an audit.
- 31 (tidy: one local `today()` through a given `clock.py` called via the module so tests can replace it, the Sync routes kept on UTC; four duplications removed with no output change; 6 requirements, 8 given tests that set `finances.clock.today` to a past date so every command and page must follow it; three searches; coverage baseline for the touched packages checked at 100% on 2887 tests): built and accepted: 2895 tests, no findings; one coder test's patch target moved with the tidy (approved).
- 32 (split the web app, no behaviour change: the contract tests rely on was found first with `git grep` over tests (names imported from `finances.web.app`, names replaced on it at run time, the restore lock, the replaced transport) and written into R2; a given test pins the 49 routes taken from today's app, the one order that matters, the module contract, one router per area, and a 400-line limit; acceptance requires earlier tests unchanged (`git diff --stat HEAD -- tests` empty); 6 requirements, 16 given tests, three of which already pass as guards): built and accepted: 2911 tests, no findings. Two spot checks (a router importing `_today` by name, a second lock) could not fail under the coder's allowed design: routers are imported inside `create_app`, after a test has already replaced the hook. To prove a hook is looked up when called, the deciding test must replace it after the app is created. For a refactor, pin the observable contract from today's code before writing anything else.
- 33 (sync resilience, from the owner's failed 07:00 syncs: a new error type for 'unreachable' so only that is retried; waits, sleep, and clock injected into `run_links` (sleep looked up at call time so end-to-end tests can replace `time.sleep`); a given migration checked up, down, and up; the schedule scripts given, their job file rendered and linted with `plutil` and its command run once; 7 requirements, 15 given tests; one computed expectation (`RETRY.format`) caught and written out before publishing): built and accepted: 2932 tests, no findings; the message column took an existing 200 constant because a test requires every width to come from a named constant (give a new column its own constant next time).
- 27a (upcoming bills and recurring income, split from 27 by the size rule: a two-week band for income only so 13a's charges and every earlier finding stay the same; an `expected` expansion over a window; two commands; 8 requirements, 17 given tests whose fixture holds monthly refunds and transfers that must never count as income; day counts and one rounding printed before publishing; deciding-case table): specified; passed (2954 tests, no findings).
- 27b (a 30-day forecast per account, split from 27: each account forecast from its own series only, transfers counted because they move a balance; the start is the newest balance on or before the window; a pure walk whose lowest point keeps the earliest tie; 8 requirements, 16 given tests whose figures were printed from today's recurring code per account before publishing; deciding-case table of seven): specified; passed (2976 tests, no findings; the coder's two sign checks in `walk` approved).
- 27c (the web for 27a and 27b, split from net worth (27d) by the size rule: one read-only page in an existing router so Phase 32's area list stays, a dashboard block whose paragraphs take a new class and which shows no table when empty, so earlier pinned rows stay; a given one-line diff to the route list; `_today` replaced after the app is created; 7 requirements, 14 given tests whose figures were printed from 27a's and 27b's functions; `template_check.py` repaired for Phase 32's move of `_render` and run on 513 earlier tests; deciding-case table of eight): specified; passed (2997 tests, no findings). Miss of mine: R4 said 'only the digits 0 to 9' but no given value separated `str.isdigit` from ASCII digits, so the coder's `isdigit` passed while `٣` was accepted and `²` showed Python's own error; fixed in 27d. When a requirement says 'only these characters', give a value that the obvious library check wrongly accepts.
- 27d (net worth over time, finishing 27: pure month-end days and points from each active account's newest balance on or before the day; a line chart reusing 16k's shape so `charts.js` is unchanged; a given diff to two 16k tests that said Reports loads no script, scripts loaded only when a chart exists; the 27c days fix first with a failing test; 7 requirements, 13 given tests; `template_check.py` kept 556 earlier tests passing; deciding-case table of eight): specified; passed (3014 tests, no findings).
- 14a (the MCP server, split from 14 by the size rule: a spike in a scratch venv settled the SDK first, which is 2.x (`MCPServer`, not 1.x's `FastMCP`), logs tool failures at INFO and crashes with tracebacks at ERROR under the `mcp` logger, sends a `dict[str, Any]` result as structured content, and installs beside today's FastAPI without upgrading anything; a read-only engine by `PRAGMA query_only`; three tools; 9 requirements, 13 given tests through the in-memory client, a stdio probe of the real command; the spec carries a 'Facts about the SDK' section so the coder does not write 1.x code; deciding-case table of eight): specified; result pending. Side finding: a fresh install today resolves pypdf 6.21.2, which fails `test_the_blank_page_is_one_that_layout_mode_cannot_read` (the project's venv has 6.20.1).

Order sub-phases so each depends only on phases before it.

**Numbering.** Roadmap numbers are referenced from `AGENTS.md`, `docs/testing.md`, and other specs, so never renumber. A removed phase keeps its number. Split a roadmap phase into lettered sub-phases (`phase-03b-...md`), list them in the roadmap under the parent number, and delete the superseded parent spec once its sub-phases cover it.

## What a spec contains

Save as `docs/phases/phase-NN[x]-<slug>.md`.

````markdown
# Phase NNx: <name>

## Goal
What exists after this phase that did not before, and why it matters to the next one.

## Read first
The files that hold the rules and the code this phase builds on.

## Starting state
The previous phase is committed, `git status --short` prints nothing,
`.venv/bin/python -m pytest` ends with `<N> passed`. Any fact about existing code the
coder needs and might get wrong.

## Scope
| Module | What it gains |
Production modules this phase creates or changes. The coder may add private helpers
inside them and may add test files. It may not create other production modules or
change ones not listed.

## Out of scope
The tempting next steps, named.

## Dependencies
With version bounds, or "None new".

## Design
Signatures, dataclass fields, table definitions, command options: everything public,
exactly. Tables of columns and fields. Constant messages in full.

## Requirements
### Part 1: <area>
R1, R2, ... One testable statement each, with an example where a sentence could be
read two ways. Exact text for every message and every printed line.

## Given tests
Each given test file in full, or "None". Marked: do not change; if one fails, the
code is wrong.

## Tests to write
Per part: the behaviors that need a test and the layer each belongs in
(`docs/testing.md`). Every requirement not covered by a given test appears here.

## Rules for this phase
The project rules this phase can break, restated with what they mean here.

## Acceptance
The commands to run before reporting, one per line, each with what it must show.

## Report
The `docs/progress.md` entry to write, and what the final message must contain.
````

## Rules for writing a spec

These hold for any coder. Each one comes from a failure in an earlier phase.

- **Fix every public name and every message.** Paths, function and class names, parameters, table and column names, constraint names, command and option names, exit codes, and the full text of each message. Banned wording: "as appropriate", "or similar", "if needed", "consider", "etc.", "handle errors gracefully".
- **Every requirement is testable, and is tested.** Each numbered requirement is covered by a given test or appears under "Tests to write". If nothing could test it, make it testable or drop it. A requirement only a reader could check gets missed.
- **No "do nothing" requirements.** "X already happens elsewhere; do not handle it" gets read as "handle X" and produces dead code. State it as a fact about the existing code.
- **Guard against the fixed answer.** When today's correct result is a constant (the newest migration is `"0002"`), require a test that changes the input, and say that a fixed value is wrong.
- **Say what must not be built.** A capable coder over-delivers: extra options, extra validation, a helper module, a refactor of earlier code. "Out of scope" names these, and "Scope" is a closed list of production modules.
- **Constant error messages, no echoed input.** Statement text, amounts, descriptions, and account digits never appear in an exception message or a log line (AGENTS.md privacy rules 4 and 5). Say so in each spec that parses or stores such data, and have a test assert the exact message.
- **Restate the rules that bite** in this phase (integer cents and the sign convention, `domain` imports nothing from the project, commands contain no business rules, no `metadata.create_all` in tests, one migration per schema change and never edit a shipped one) instead of relying on the coder to recall `AGENTS.md`.
- **Commands are written exactly as typed** on the machine the coder runs on, which is macOS: `.venv/bin/python -m pytest`, `.venv/bin/python -m ruff ...`, `.venv/bin/fin ...`. Never `python`, `ruff`, or `pytest` bare, and never "activate the virtual environment": each command runs in a new shell.
- **Acceptance expects only what the coder cannot change.** With coder-written tests the passed count is "at least N", where N is the count before the phase plus the given tests. Lint and format are exact (`All checks passed!`, and `ruff format --check .` reporting nothing to reformat; do not state a file count, since the coder may add test files). Coverage is a command with a pass line:
  `.venv/bin/python -m pytest <test paths> -o addopts="" --import-mode=importlib --cov=<dotted module> --cov-branch --cov-report=term-missing --cov-fail-under=100`
  for each critical module, expecting `Required test coverage of 100% reached`, and the project-wide gate for the rest.
- **No destructive git.** Every spec says: never run `git restore`, `git checkout`, `git reset`, `git stash`, or `git clean`, and do not commit. The user commits after verification.
- **CLI output is pinned.** Tests build the runner as `CliRunner(env={"COLUMNS": "200"})` so Rich does not wrap expected text, and assert stdout, stderr, the exit code, and `isinstance(result.exception, SystemExit)`.
- **Framework wiring is specified, not given.** Say which Typer app a command registers on and which options it takes; the coder writes the wiring. Give boilerplate in full only where one wrong line breaks everything downstream (Alembic's `env.py` was such a file).
- **Coverage has blind spots.** Files a library loads by path (Alembic's `env.py`, migration files) are not in the coverage table. Require a test that executes every function in them.
- **Fixtures and opt-in checks are committed by the architect, tests are given in the spec.** Text fixtures (which can hold form feeds and exact spacing) and privacy-sensitive tooling such as `tests/real_samples/check_real_samples.py` go into the repository with the spec, as architect changes. Given test files stay in the spec, so the suite is green until the coder starts.
- **Specify a parser with a generator.** Write a small function that renders a synthetic statement from structured data. Use it to produce the fixtures, and put it in the probe script so the verifier can test statements whose every expected line is known by construction.
- **Real statements stay unseen.** The architect has no access to `data/samples/` and must not ask for their content. A parser spec is built from `docs/statement-formats.md`. Say in the spec and the guide what may be run on real statements and what may be reported (sample numbers, parser name, counts, differences in cents), and expect the first real run to reveal layout details the synthetic description missed: that is a request for a new synthetic example, not a coder failure.
- **Two independent phases need an order-free starting count.** When phases can be built in either order, the spec tells the coder to run the suite first and call the passed count N, and acceptance asks for "at least N plus the given tests".
- **Check every search step against today's code.** A pattern meant to forbid `print(` matched `console.print(`, which the command needs. Run each `git grep` from the spec and the guide and expect silence, or exactly the lines the spec names.
- **Assert table rows as cell lists.** For a Rich table, split each row on the box characters and compare a list of stripped cells. It survives column width changes and still pins every value.
- **Tests must not pin today's newest migration.** Adding migration `0002` broke 26 older tests that compared against `"0001"` or an exact table list. Tests about one migration upgrade to that revision by name; tests about "the newest" ask `head_revision()`; table checks ask for a subset. When a phase adds something that existing tests enumerate (a migration, a `doctor` check, a command), find those tests by reading them (a spike that adds a stub of the new thing settles a doubt), fix the tests as a separate architect change that passes both before and after, and say so in the spec's "Starting state".
- **Measure what the probe script reaches** once the coder has built the phase: run it under `coverage run --branch` while verifying, and turn any line it does not reach into a probe line for the next phase.
- **A test input must make the wrong version visibly wrong.** Two cases from the 3b trial: a `float` sum passed a large-number test because the result happened to round back to the right integer, and plain PDF extraction passed until the test PDF had text in separate columns. After writing a test against a specific mistake, run that mistake and see the test fail.
- **A probe script never crashes.** Wrap each section so that an unexpected exception prints a `FAIL` line and the run continues to `FAILURES N`. A traceback tells the verifier nothing about the other checks.
- **New files change the formatter's count.** This `ruff` version counts every `.py` file and every Markdown file outside `docs/`. Keep documents under `docs/`, and never add a file to the repository while a phase is being implemented or verified against a spec that states a count (the local-format specs do).
- **Learn a real layout by asking counted questions.** When a parser fails on real statements, nobody reads them. Add fixed yes-or-no and how-many questions to `tests/real_samples/describe_layout.py` (is the label alone on its line, is money on the same line, do the rows under a loosely matched heading add up to the total), have the user run it, and build a synthetic fixture from the answers. Include a line that applies the intended repair and reports whether the sample then reconciles, so the repair is proven before it is specified. Two rounds were enough for three faults.
- **Synthetic text was too tidy.** The first real run showed what fixtures written by hand never have: a page with no content stream, lines a million characters wide, and labels with spaces inside words. Normalize at the one place every parser shares (`extract_pages`), and write label rules that ignore spacing.
- **Check whether a phase was already built before revising its spec.** A spec revised after the coder built it describes code that does not exist. Look at `git log` and `docs/progress.md` first; once a phase has shipped, changes go into the next phase, and a shipped migration is never edited.
- **Keep tests off the network and the real keychain by default.** An autouse fixture in `tests/conftest.py` blocks every connection and name lookup outside the machine and installs an in-memory keychain. A test that needs real HTTP starts its own server on 127.0.0.1, and a subclass of `HTTPServer` skips the reverse name lookup that otherwise costs half a minute on macOS.
- **A provider's front door is part of its protocol.** SimpleFIN's published spec was followed exactly, yet the first real request failed: Cloudflare in front of it refuses Python's default `User-Agent` with the same `403` the protocol uses for a used token. Before a network phase ships, check the real host's answer to the transport's exact request on a public endpoint that needs no credentials (here `GET /simplefin/info`), and name the app in `User-Agent`.
- **Tests must not depend on the shell's colour variables.** The coder's shell exported `FORCE_COLOR=0`, which Rich treats as a terminal, and 18 tests failed until the coder unset it by hand. `tests/conftest.py` now removes `FORCE_COLOR`, `NO_COLOR`, `TTY_COMPATIBLE`, and `TTY_INTERACTIVE` for every test. When a test fails only on the coder's machine, look for an environment variable before blaming the code.
- **A web form phase keeps the earlier pages' tests passing unchanged.** Put the forms after the tables, keep every table cell, and run the earlier phase's page tests against the reference before writing the new ones. A test that parses `<select>` options must key them by form, since one page can hold several selects of the same name.
- **Replace a module function through the module.** Routes that call `transport.urllib_transport` at request time let tests and the probe swap in a fake SimpleFIN; a name imported with `from ... import` would keep the real one.
- **Hunt for bugs before writing a hardening spec.** Write the property and fuzz tests in a scratch clone first, run them long with random seeds (`derandomize=False`, thousands of examples), and turn each real failure into a fix with a pinned example. The spec then hands the coder the fixes, not a search.
- **A simulation must follow real time.** The first ledger simulation imported a statement before its period ended and pulled the feed back in time, and "found" a loss no household can meet. Model the order of real events (a statement arrives after its period, pulls move forward and come at least as often as the window), check each shrunk failure by hand, and pin the realistic ones as plain tests, since a random run may never reach a rare start such as a first sync after statements.
- **When a property shows an earlier spec's rule is wrong, replace the rule.** Phase 8 pinned closest-first pairing in a given test; Phase 9 replaces that requirement and that test file, and says so. Do not bend a new test around an old mistake.
- **Separate the model's limits from bugs.** Some failures are ambiguity no code can resolve (two equal purchases five days apart across a period edge). Write them down as known limits in the spec, exclude them from the property, and keep the property to what the code can guarantee.
- **Never swap source in a clone while a background run uses it.** A long run that imports the code mid-swap reports nonsense. Copy the clone for variant runs.
- **Try a web phase in a real browser before it ships.** 16a's `Referrer-Policy: no-referrer` and 16b's origin check were each right, but together they refused every form, because a browser sends `Origin: null` under `no-referrer` and test clients send no `Origin` at all. Headless Chrome with `--dump-dom` and a helper page served beside the site (the site forbids scripts) shows what a person would see. In headless Chrome, `--disable-background-networking` and `--disable-extensions` make such a page hang, and each run needs its own profile.
- **Follow a new record through every place that decides what runs.** Recording new SimpleFIN accounts was not enough: a sync ran only links with a mapping, so a fresh link with nothing mapped would never be seen. When a phase adds something a loop should pick up, check what feeds that loop.
- **Prove a refactor by comparing before and after.** For a phase that must change no behaviour, the probe runs one scenario against the last commit's code, extracted with `git archive`, and against the working tree, and compares every output after masking what differs between any two runs (tokens, times). Check the probe is stable by running it on today's code against itself, and sensitive by altering one word in a copy.
- **`git grep -E` has no `\b`.** A search with `\b` silently matches nothing; anchor on a following character such as `\(` instead, and run each search on today's code to see it find what the phase removes.
- **Moving a check can change which message wins.** When a refactor moves validation between layers, list each interface's current order of checks and keep it; probe each form and command with two mistakes at once.
- **Look for tests that pin imports before moving code.** `tests/unit/test_statement_models.py` forbids any `finances` import in `domain/models.py`; Phase 23's spec missed it and the coder kept a literal instead. Before a phase moves a constant or helper into a module, search the tests for checks on that module's source (`read_text`, `import ` lines, `not in source`).

What the local format required and this one does not: single-action steps, a stub for every unit, the expected output of every command, a repair table, tests for everything given in full, a fixed order of work, and "facts you will need" for each library call. Add any of these back to one spec when that spec's subject warrants it.

## Verification guide

Write it at the same time as the spec, and save it as `docs/verification/phase-NN[x]-<slug>.md`. It is not in the coder's "Read first" list. The verifier has not seen your reasoning, so the guide must stand alone. The verifier reports and does not fix.

With the coder writing most of the tests, the guide carries more weight than before, in two places: the probe script, and the review of the coder's tests.

```markdown
# Verify Phase NNx: <name>

Spec: `docs/phases/phase-NNx-<slug>.md`
Do not modify any file in the repository. Report findings only.

## 1. Gates
The spec's acceptance commands, each with its expected result.

## 2. Scope audit
- `git status --short` shows only the modules in the spec's Scope table, test files,
  and `docs/progress.md`. List every other path.
- Given test files are identical to the spec's blocks.
- No earlier migration, earlier test, or unlisted module was changed.

## 3. Requirement checklist
| Id | Check | How | Pass when |
One row per requirement: a probe line, a command, or a named place to read.

## 4. Independent probes
A complete script, saved outside the repository, that prints `ok` or `FAIL` per line
and `FAILURES 0` at the end. Inputs that are in neither the given tests nor the spec's
examples.

## 5. The coder's tests
- For each requirement under "Tests to write", name the test that covers it. A
  requirement with no test is a finding.
- Each such test asserts the behavior: no `assert True`, no blanket
  `pytest.raises(Exception)`, no unexplained `skip` or `xfail`, no expected value
  computed by calling the code under test.
- Tests are in the layer `docs/testing.md` assigns, use synthetic data, touch no
  network, and do not depend on today's date or on test order.
- Spot check: for three requirements chosen by the architect and named here, describe
  the one-line change to the production code that would break each, and confirm by
  reading that a test would fail.

## 6. Project rules that apply to this phase
The exact searches to run, each with "no output" or the one line expected.

## 7. Out of scope
The things the spec said not to build, each with how to see that it was not built.

## 8. Progress log
The entry exists, and each deviation and design choice it lists is real, justified,
and inside the spec's Scope.

## Verdict
PASS, or FAIL with one line per finding:
<requirement id or section> | <file>:<line> | expected <...> | found <...>
Then: Parts that needed a repair: <none, or the part numbers>

## If the verdict is FAIL
Each repair names the requirement or rule, the observed behavior, and the required
behavior. Do not prescribe the code.
```

Rules for writing the guide:

- Every requirement has a checklist row, and every row names a concrete observation. "Looks correct" is not a check.
- Probe inputs are new. Choose them at boundaries: signs, zero, year wrap, case, empty input, values that lose a cent in `float`, digits from other alphabets, the 501st item of a chunked query, a second run of the same operation.
- Judge the coder's code by behavior and rules, never by resemblance to how you would have written it. Say in the guide which reasonable variations are correct, so the verifier does not report them.
- Where the real-sample tests apply, the guide asks only for pass, fail, and counts (AGENTS.md rule 6).
- Commands start with `.venv/bin/python`. Avoid `$` inside double quotes, and keep `|` out of Markdown table cells (use a list for regex searches).

## Checking a spec before publishing

**The architect does not build the feature.** The coder does; a full reference implementation by the architect only builds everything twice (the owner's decision, after Phase 16d). The architect designs and specifies, and checks the spec in these cheap ways. This is the architect's own work and is never committed.

1. **Write from the real code.** Read every module the phase touches and quote real names, signatures, messages, and test helpers. Given tests are written by reading the code and the existing tests, not by running a build of the feature.
2. **Spike only a real unknown.** When a requirement depends on something reading cannot settle (what header a browser sends, how a library treats an input, whether a rule can lose data), write the few lines that answer it, in a scratch clone (`git clone -q . <scratch>/clone`) with a scratch virtual environment (`/opt/homebrew/bin/python3.12 -m venv <scratch>/venv`, `pip install -e ".[dev]"`, `PYTHONPATH=<clone>/src`, `PYTHONDONTWRITEBYTECODE=1`). A bug hunt with property or fuzz tests counts as a spike. Never build the feature itself. Never install into the project's own `.venv`.
3. **Check the given tests against today's code.** They must import, collect, and fail for the right reason (the missing behaviour, not a typo in the test). Lint them with `ruff format` and `ruff check` in a scratch clone where **every module the phase creates exists as an empty stub file**: without the file, ruff sorts its imports as a third-party library, and the order breaks the moment the coder creates the module (Phases 22 and 23 had to re-sort given tests). Never paste the output of `ruff check --fix` run without those stubs. Whether they pass is shown by the coder's build; when they do not, the coder reports it and the architect repairs the spec or the test.
4. **Check every search command** in the spec and the guide against today's code, and say in the spec which output the new code must not add.
5. **Build the spec and guide with `gen_spec.py`** from templates, so the blocks in them are exactly the files that were checked.
6. **The probe script is written from the spec** and run against today's code, where its new checks must fail and nothing may crash (each section wraps its errors). Its passing run is the verifier's. **Keep the probe lean** (the owner's decision after Phase 11a): it checks only what the given tests do not reach — interactions across modules or phases (a feed row a statement later drops), a real browser or server, before-and-after comparisons for a refactor — plus a few new inputs on the riskiest rule. It does not repeat given tests with new numbers.
7. **State acceptance counts as "at least N plus the given tests"**, since no reference build exists to count from.

Expect some repair rounds: a wrong expected value or a gap in the spec now shows up in the coder's build. That is the normal loop and is cheaper than building everything twice.

## After a phase is implemented

1. Run `.venv/bin/python .claude/skills/phase-architect/phase_status.py`. It prints, in one screen, whether the tree is clean, the last commits, the newest migration, the latest `docs/progress.md` entry (fixed fields: tests before and after, new public names, changed files, deviations, follow-ups), the summary block of the newest review in `docs/reviews/` (verdict, passed, findings, approved deviations, a line for the architect), and the public names the last implementation added. The owner does not paste reports. **Do not re-run the test suite to learn N**: take it from the progress entry, which `scripts/check.py` produced and the verifier confirmed. Open the full review or diff only when the summary shows a FAIL, a deviation, or a line for the architect. A FAIL goes back to the coder with the verifier's findings. Do not rewrite the spec to match a wrong implementation.
2. Record the result under "Finding the limit" above, and turn the cause of any miss into a rule in this file.
3. Read the design choices the coder recorded. The next spec's "Starting state" and "Design" build on what was actually written: real names, real signatures, real helper functions.
4. Keep the roadmap table and status line current.

## Handing over

Hand a phase over only from a clean tree: the spec, its verification guide, and any roadmap or skill change are committed first, and `git status --short` prints nothing. The verifier's scope audit depends on it. Ask the user to commit, or commit when they have said to.

Report to the user the spec path, the verification guide path, and anything decided on their behalf. Prompts for the two agents:

> Coder: Read AGENTS.md, docs/architecture.md, docs/testing.md, docs/progress.md, and docs/phases/phase-NNx-<slug>.md. Implement only that phase. Run every command under "Acceptance" before you report, and write the progress entry.

> Verifier: Read AGENTS.md, docs/phases/phase-NNx-<slug>.md, and docs/verification/phase-NNx-<slug>.md. Follow the verification guide against the current diff. Do not modify files. Report the verdict.
