# Review: Phase 47h2

- Verdict: PASS
- Passed: 4725
- Findings: 0
- Approved deviations: None
- For the architect: None

## Findings

None.

Parts that needed a repair: None.

Built beyond the spec: None.

## Phase 47h2: extract MCP proposal and advice tools (2026-11-16)

Reviewed delivery `ac9cacc8a0e7d80f11e6d438bf4b2512a53c0dba` against finalized planning baseline `03d41e3dbdcef16ef704e03efdb23f7b18aa2d13`. Predecessor 47h1 PASS is committed at 1a7056e, N=4687. Spec and guide match the committed baseline. Read project instructions, architecture, conventions, testing strategy, handoff, spec/guide, progress, affected production and test sources.

Verification used clean isolated clone `/tmp/47h2-independent`, linked existing venv and explicit clone/src PYTHONPATH. Import provenance resolved `/private/tmp/47h2-independent/src/finances/__init__.py`. All tracked files were compared byte-for-byte against the original delivery before and after gates; identical. Original untracked `.vscode/settings.json` was preserved. Only this review was written in the original repository.

The baseline diff contains exactly seven Scope paths. No other earlier tests changed. Given file equals the spec Python block. The earlier-test patch's added/removed lines exactly match the supplied patch; raw Git diff formatting additionally supplies hunk function labels and blank context markers. AST hashes and assertions are preserved. Independent comparison against actual planning source confirms all thirteen adapters and _as_tool are unchanged ASTs, month_start differs only in its definition name, and all eighteen remaining read tools are unchanged ASTs. Server/access/serialization and planning docs are byte-identical to baseline. Explicit facade re-exports preserve identity; no dynamic compatibility machinery or reverse facade dependency appears.

## Fresh independent gates

All five acceptance steps ran sequentially with `.venv/bin/python`, clone PYTHONPATH, Python 3.12.16, pytest 9.1.1 and four workers. One coverage-producing job. Existing synthetic localhost fixtures received execution permission; no failed sandbox attempt or test weakening occurred. No real data, Keychain, aggregator or dependency installation. Coder progress receipts remain historical and do not substitute for these fresh results.

| Gate | Fresh result |
|---|---|
| scripts/check.py --first mcp --workers 4 | exit 0; selected 296 passed in 7.79s; full 4725 passed in 95.75s; all sections clean, no xfails/warnings summary; lint/format/critical gates passed; All checks passed. |
| Immediate specified coverage report --fail-under=100 | exit 0; helpers 9 statements, proposals 107, TOTAL 116; zero missed lines, measured branches and partials; both modules and TOTAL 100% |
| Given-only pytest --no-cov | exit 0; exactly 17 passed in 0.23s |
| Unchanged external guide probe | exit 0; oracle sensitivity ok; inventory schemas signatures ok; FAILURES 0 |
| Scope/given/byte audit | exact seven paths; given file and patch content identical; all tracked delivery bytes identical; clean isolated status |

Coverage measured 99.98% overall; expression alternatives and exceptions also have meaningful behavior assertions. Probe digest `b9dabd87018443723316328d4a2b4b4af5d808e4b8f080e9b5812cdef7932ad4` matches complete metadata and facade signatures for all 31 tools. Probe lists registration in memory and self-checks a planted description change. Script was saved outside repository, executed unchanged and deleted after use. Full acceptance output: `/tmp/47h2-check.log`.

```text
Sections:
  migrations    184 passed    0 failed    0 skipped
  scripts       100 passed    0 failed    0 skipped
  web           888 passed    0 failed    0 skipped
  cli           460 passed    0 failed    0 skipped
  mcp           296 passed    0 failed    0 skipped
  parsers       903 passed    0 failed    0 skipped
  sync          284 passed    0 failed    0 skipped
  core         1610 passed    0 failed    0 skipped
```

Final ten check lines:

```text
  core         1610 passed    0 failed    0 skipped
== critical coverage

Summary:
  lint: passed
  format: passed
  tests (mcp): passed
  tests: passed
  critical coverage: passed
All checks passed.
```

## Requirements and deciding tests

| Requirement | Evidence |
|---|---|
| R1 | Thirteen given test_facade_identity cases; independent full function AST comparison; earlier-test test_tool_bodies_match_planning_baseline; explicit imports preserve identical objects. |
| R2 | test_month_helper_clock_errors_and_aliases pins explicit/no clock, fixed default/one clock, malformed ToolError and shared aliases. test_adapter_arguments_and_context pins finding lookup date/type/about. test_finding_failure_aborts_store proves lookup is inside context, exact arguments and no store on failure. |
| R3 | Fresh inventory probe, unchanged public MCP integration/capability and repository inventories, unchanged server/access/serialization and eighteen read-function ASTs. |
| R4 | test_adapter_arguments_and_context covers all ten nondefault repository calls, same session/returned row, marker envelopes and normal exits. test_error_exits_context_before_translation proves original exceptions reach context exit, translation suppression and unchanged LookupError identity. test_read_lists_order_and_limits pins accepted/declined limits, ordered full envelopes and both dismissed timestamp forms while forbidding writing. test_advice_default_and_explicit_subject pins full advice rows and exact store arguments. Given error/advice tests and unchanged public write-boundary integration supply complementary evidence. |
| R5 | test_structure_and_size plus source inspection, exact supplied earlier-test changes and preserved AST hashes. Proposals 222 lines, helpers 15, tools 512; new modules meet 400 caps, tools meets 716 interim cap. No area imports facade/server or new exemptions. |

Seventeen given and twenty-one coder cases account for 4687 -> 4725. Tests assert behavior and arguments, not merely executed lines. Public in-memory integration remains the real persistence/permission baseline. Progress accurately records this stage and its evidence; tools retains only the approved temporary size exception ending at 47h4. No later-stage move was included.

## Fresh scratch-only mutations

Each mutation ran independently in a disposable clone with confirmed clone import provenance; reviewed source was never modified. Each designated given test failed with exit 1 for the intended reason:

| Mutation | Deciding case | Observed broken result |
|---|---|---|
| Stop catching ValueError | test_error_translation[value] | original ValueError escapes instead of ToolError |
| Also catch LookupError | test_error_translation[unexpected] | ToolError replaces required LookupError |
| Forward empty advice subject | test_advice_json | exact store-call subject assertion fails |
| Wrap facade log_advice | test_facade_identity[log_advice] | facade and owning function objects differ |

Logs retained at `/tmp/47h2-spot-{value,unexpected,subject,identity}.log`; scratch clones removed. The subject mutation reaches the repository call; its mocked row still preserves output subject, so the exact call assertion is the deciding check. No unrelated validation masks the mutations.

No remaining baseline, environment, specification/test or implementation blocker. PASS applies to the exact reviewed delivery bytes. No implementation repair, progress/phase-document change, commit, push or later-phase work performed.
