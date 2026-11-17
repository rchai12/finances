# Review: Phase 47h3

- Verdict: PASS
- Passed: 4761
- Findings: 0
- Approved deviations: None
- For the architect: None

## Findings

None.

Parts that needed a repair: None.

Built beyond the spec: None.

## Phase 47h3: extract MCP reporting tools (2026-11-16)

Reviewed delivery from `/tmp/finances-47h3-work` against revision 2 planning commit `d823d07d39c9c4c509938af3df0637721d0171ed`, which follows original planning commit `327f62a0008cb755bbc454149143e5463489cc80`. Revision 2 spec and guide are committed and unchanged at that baseline. Predecessor 47h2 PASS is committed at 713c911, N=4725.

The target working tree retained implementation files from the stopped first attempt and had revision 2 planning/test corrections applied. It also contained unrelated `.claude/skills/phase-architect/history.md` changes, which were excluded. For isolation, cloned the revised committed baseline to `/tmp/finances-47h3-r2-review` and copied only the nine authorized paths: reports.py, tools.py, two new report tests, two existing MCP behavior tests, the two period-selection test corrections and progress.md. Clone `HEAD` is the revised planning SHA; status has only eight effective test/source changes because progress.md already matches the committed revised entry. Python imports resolve inside clone `src`. Every copied scoped file was compared byte-for-byte to the target delivery. No implementation files were edited.

The two newly supplied report test blocks match the spec. Both original earlier-test patches and both revision 2 correction patches match the authorized added/removed lines. No other earlier test changed in the isolated delivery. `server.py`, `access.py`, `helpers.py`, `proposals.py`, `serialization.py` and planning documents match the revised baseline. All remaining eleven tool ASTs retain baseline hashes; moved report functions preserve their baseline ASTs, and explicit tools facade exports retain object identity. `reports.py` is 244 lines (<=400); tools.py is 286 (<=512). No reverse area-to-facade/server import or dynamic wrapper was found. The only delivery tree exception was the unrelated history change in the target workspace; it was excluded from review and does not affect the nine authorized paths.

## Fresh gates

No evidence from the failed first attempt or coder receipts was reused. All five acceptance gates ran fresh, sequentially, in the isolated revision 2 clone using Python 3.12.16, pytest 9.1.1 and four workers. Existing synthetic localhost fixtures were permitted; no failed sandbox attempt or test weakening. No real DB, Keychain, samples, aggregator or network calls.

| Gate | Fresh observation |
|---|---|
| `scripts/check.py --first mcp --workers 4` | exit 0; selected mcp 332 passed in 7.89s; full 4761 passed in 95.04s; all sections zero failures/skips; no xfails or warnings summary; lint, format and critical coverage passed; final `All checks passed.` |
| Immediate reports coverage command | exit 0; reports.py and TOTAL 100%, 71 statements, 2 branches, none missing/partial |
| Given-only `pytest tests/unit/test_mcp_report_tools.py --no-cov` | exit 0; exactly 12 passed in 0.22s |
| Guide inventory probe | exit 0; oracle sensitivity ok; inventory schemas signatures ok; FAILURES 0; 31 tools and baseline digest `b9dabd87018443723316328d4a2b4b4af5d808e4b8f080e9b5812cdef7932ad4` |
| Scope and equality | revised clone baseline; nine authorized paths only; given patches match; unchanged source and AST checks passed |

Overall coverage is 99.98%. Full log: `/tmp/47h3-r2-check.log`.

```text
Sections:
  migrations    184 passed    0 failed    0 skipped
  scripts       100 passed    0 failed    0 skipped
  web           888 passed    0 failed    0 skipped
  cli           460 passed    0 failed    0 skipped
  mcp           332 passed    0 failed    0 skipped
  parsers       903 passed    0 failed    0 skipped
  sync          284 passed    0 failed    0 skipped
  core         1610 passed    0 failed    0 skipped
```

Final ten lines:

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

## Requirements and deciding evidence

| Requirement | Evidence |
|---|---|
| R1 | Seven `test_facade_identity` cases in given and behavior suites; By/helper identity cases; moved function AST comparison and given `test_tool_bodies_match_planning_baseline`; explicit imports preserve objects. |
| R2 | Given `test_spending_json`, four `test_recurring_json` variants and coder full literal report cases check totals, signs, nulls, order and filtering. |
| R3 | Coder argument, error/cause, clock and context cases plus unchanged baseline ASTs verify forwarding and read-only contexts. |
| R4 | Independent whole-inventory probe, existing public in-memory MCP suite, repository/capability inventory and unchanged source comparisons. |
| R5 | Exact nine-path audit, both original and correction patches, AST checks, dependency inspection and module size checks. |

Revision 2's four period-test call-site migrations passed in the fresh complete suite. They preserve their assertions and inputs while calling the shared `helpers.month_start`; no private compatibility alias was restored. The previous 4757-pass/four-fail result remains historical specification-failure evidence only. The progress entry retains that stop and correction history and records the revised outcome; it does not add a duplicate phase heading.

## Scratch-only mutations

Each ran in a separate disposable copy with confirmed import provenance; all designated cases failed on the intended output assertion:

| Mutation | Deciding case | Observation |
|---|---|---|
| Omit refund add-back in spending summary | `test_spending_json` | Expected 700, observed -200. |
| Force recurring sign to positive | `test_recurring_json[all-charges]` | Expected -300, observed 300. |
| Keep inactive recurring rows | `test_recurring_json[active-income]` | Expected empty list, received a row. |
| Wrap facade get_spending | `test_facade_identity[get_spending]` | Facade function object no longer identical. |

PASS applies to the reviewed revision 2 delivery bytes. No implementation, phase or progress file was modified by this review; only this review report was written. No commit or push.
