# Review: Phase 47h1: extract MCP serialization

- Verdict: PASS
- Passed: 4687
- Findings: 0
- Approved deviations: None
- For the architect: None

## Findings

None.

Parts that needed a repair: None.

Built beyond the spec: None.

## Baseline and scope

Reviewed delivery `54194974b459cbedc8ed66c7d5f96f68a7c221c3` against planning baseline `a8795b5961492d91046099168b6536f8725445a5`. Phase 47g's committed PASS at d09bcde records 4639 passes. Finalized spec/guide are unchanged. Read project instructions, architecture, conventions, handoff, spec/guide, progress, production changes and both new test files.

The diff contains exactly five Scope paths. Existing tests, configuration, dependencies, server.py and access.py are unchanged. Given test bytes equal the embedded spec block. Independent AST comparison against the actual planning source confirms all five helpers retain their bodies modulo internal names, and every remaining tools.py function differs only by the permitted module-qualified serializer references. No stale helper definitions or aliases remain. The corrected module docstring describes read tools and permitted writers.

Fresh clean clone `/tmp/47h1-independent` uses the existing linked venv and explicit clone/src PYTHONPATH. Import provenance resolves inside that clone. All tracked files were compared byte-for-byte with the delivered workspace before and after gates; identical. Original unrelated untracked `.vscode/settings.json` was preserved. Only this report was written in the original repository.

## Fresh acceptance

All required acceptance steps ran sequentially. Existing synthetic localhost fixtures received execution permission; no failed sandbox attempt or test weakening occurred. No real data, Keychain or aggregator access. Python 3.12.16, pytest 9.1.1, four workers, one coverage job. Coder progress receipts remain historical and were not reused as independent acceptance.

| Gate | Fresh result |
|---|---|
| `scripts/check.py --first mcp --workers 4` | exit 0; 258 selected passed in 7.24s; 4687 full passed in 95.35s; lint/format/critical gates passed; no failures/skips/xfails/warnings summary; All checks passed. |
| Immediate coverage report, serializer include and fail-under=100 | exit 0; module/TOTAL 24 statements, zero missed, zero measured branches/partials, 100%; expression alternatives additionally have behavioral assertions |
| Given-only pytest, --no-cov | exit 0; exactly 16 passed in 0.04s |
| Independent guide probe | exit 0; oracle sensitivity ok; inventory schemas signatures ok; FAILURES 0 |
| Scope/given/delivery comparison | clean clone; exact five paths, supplied bytes identical, all tracked delivery bytes identical |

Every Python command used `.venv/bin/python` with clone PYTHONPATH. Overall coverage 99.98%. Inventory probe saved outside repository and executed unchanged; schema/signature digest `b9dabd87018443723316328d4a2b4b4af5d808e4b8f080e9b5812cdef7932ad4` matched for all 31 tools, with planted-description sensitivity confirmed. Probe script deleted after use. Full check log: `/tmp/47h1-check.log`.

```text
Sections:
  migrations    184 passed    0 failed    0 skipped
  scripts       100 passed    0 failed    0 skipped
  web           888 passed    0 failed    0 skipped
  cli           460 passed    0 failed    0 skipped
  mcp           258 passed    0 failed    0 skipped
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

## Requirements and assertions

| Requirement | Deciding evidence |
|---|---|
| R1 | Actual predecessor AST comparison of transaction_item, brief, named, iso and proposal_item; test_brief_named_and_absent pins complete row, lookup/session/id and absent AssertionError. |
| R2 | Twelve literal given proposal dictionaries, inventory equality and three iso cases; test_complete_transaction_rows covers assigned/uncategorized, refunds/purchases, pending/card and differing dates with full dictionaries. test_proposal_variants covers group flags, fallback/null fields, timestamps with microseconds, dependencies/staleness and unknown kind. test_read_errors_propagate_without_writes pins original exceptions and no session writes. |
| R3 | test_all_writer_serializer_wiring checks all ten writers and exact serializer arguments; test_listing_and_queue_wiring checks proposal/uncategorized envelopes; test_read_tool_helper_markers checks transactions, transfers, suggestions, coverage and advice. Independent AST comparison confirms only permitted substitutions throughout tool bodies. |
| R4 | Fresh whole inventory probe, unchanged server/access, full public in-memory MCP/capability tests, source docstring inspection. Public functions and metadata unchanged. |
| R5 | test_source_structure_and_limits and independent source inspection: serialization.py 153 lines, tools.py 716 lines; all registered functions remain in tools.py; no facade/server imports from serialization. test_tool_bodies_match_planning_baseline also passes. |

Sixteen given plus 32 coder cases explain 4639 -> 4687. Complete dictionary assertions and marker wiring validate observable behavior; the existing public MCP suite supplies actual integration coverage. Progress accurately limits delivery to 47h1 and records the temporary tools.py size exception through 47h3, expiring at 47h4. No final global 400-line cap was imposed early.

## Scratch-only mutations

Each mutation ran in a separate disposable clone with confirmed import provenance, unchanged given inputs and --no-cov. Each designated test exited 1 at its intended value assertion; scratch directories were removed. Reviewed source was never mutated.

| Mutation | Given case | Actual failure |
|---|---|---|
| Expose RULE_EDIT target | test_proposal_json_is_preserved[rule_edit] | transaction_id 7 instead of None |
| Suppress alias dictionary | test_proposal_json_is_preserved[alias] | alias None instead of complete source/target |
| Remove finding month truncation | test_proposal_json_is_preserved[finding_status] | 2026-01-01 instead of 2026-01 |
| Truncate iso timestamp | test_iso_preserves_value[timestamp] | date only instead of complete aware timestamp |

Logs: `/tmp/47h1-mutation-{rule_edit,alias,month,timestamp}.log`. No unrelated validation masked these mutations. No baseline, environment, specification/test or implementation blocker remains. PASS applies to the exact reviewed bytes. No implementation repair, commit, push or later-stage work performed.
