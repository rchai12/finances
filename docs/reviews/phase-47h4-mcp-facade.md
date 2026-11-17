# Review: Phase 47h4

- Verdict: PASS
- Passed: 4790
- Findings: 0
- Approved deviations: None
- For the architect: None

## Findings

None.

Parts that needed a repair: None.

Built beyond the spec: None.

## Phase 47h4: finalize the MCP tool facade (2026-11-17)

Reviewed committed delivery `98188a81ef929b3953dc3e6d3842fcd09a328aca` against finalized planning baseline `4305141add46a5d7f95e0e0c25662cebc6cbc4dc`. The separately committed 47h3 implementation is `67260e754e3dc41a7fd2d3eba0bd1319b4d3d4f2`, with PASS review 1dd738f and 4761 successful tests recorded in progress. The planning baseline contains reports.py and the corrected period tests. Spec and guide match their committed planning bytes. Predecessor delivery is excluded from the phase diff.

Independent verification used clean local clone `/tmp/47h4-independent`, the existing linked venv and clone/src PYTHONPATH. `finances.__file__` resolved inside that clone. All tracked clone and delivered workspace files matched byte-for-byte before and after gates. The original workspace had only unrelated untracked `.vscode/settings.json`, preserved throughout. Only this review report is written in the workspace.

The baseline-to-delivery diff is exactly nine scoped paths. The given contract file is byte-identical to the spec; added/removed lines in all three earlier-test migrations match the supplied patch. Other tests and server/access/helpers/proposals/reports/serialization are unchanged. An independent AST comparison against the actual planning source confirms all eleven moved function bodies, annotations and defaults unchanged. Tools.py has only its docstring and explicit imports; no wrapper, assignment or private alias. Facade identities and By are covered by given and coder assertions. Source inspection and structural tests show no reverse facade/server imports or dynamic dispatch in the new modules.

## Fresh independent acceptance

All five guide acceptance steps ran sequentially using `.venv/bin/python`, Python 3.12.16, pytest 9.1.1 and four workers. The existing synthetic localhost fixtures received execution permission; no failed sandbox attempt, dependency installation or test weakening. No real data, Keychain or aggregator access. Coder receipts in progress are historical and were not reused.

| Gate | Fresh observation |
|---|---|
| `scripts/check.py --first mcp --workers 4` | exit 0; selected mcp 361 passed in 7.42s; full 4790 passed in 95.08s; all sections zero failures/skips, no xfails/warnings summary; lint, format, overall and critical gates passed; final `All checks passed.` |
| Immediate specified accounts/queues coverage report | exit 0; accounts 22 statements/2 branches, queues 67/6; zero missed or partial; both and TOTAL 100% |
| Given-only `pytest tests/unit/test_mcp_facade_contract.py --no-cov` | exit 0; exactly 14 passed in 0.22s |
| Independent guide inventory probe | exit 0; oracle sensitivity ok; inventory schemas signatures ok; FAILURES 0 |
| Scope, given and source audit | nine paths; three migrations and given bytes match; unchanged source and moved ASTs match; all tracked delivery bytes match |

Overall coverage was 99.98%. The external probe was saved outside the repository, executed unchanged and deleted; its planted description change confirmed sensitivity and its digest `b9dabd87018443723316328d4a2b4b4af5d808e4b8f080e9b5812cdef7932ad4` matched all 31 tools' generated metadata and facade signatures. Full synthetic acceptance output: `/tmp/47h4-independent-check.log`.

```text
Sections:
  migrations    184 passed    0 failed    0 skipped
  scripts       100 passed    0 failed    0 skipped
  web           888 passed    0 failed    0 skipped
  cli           460 passed    0 failed    0 skipped
  mcp           361 passed    0 failed    0 skipped
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

## Requirements and deciding evidence

| Requirement | Evidence |
|---|---|
| R1 | Eleven given `test_facade_identity` cases, `test_facade_contains_only_docstring_and_imports`, `test_facade_and_no_reverse_imports`, retained AST hash pin and independent baseline AST comparison establish exact moves and object identity. |
| R2 | Given `test_transfer_order_and_limit` pins reverse order and pre-limit total. Coder `test_balances_and_net_worth`, `test_transactions_filters_and_paging`, `test_categories_rules_uncategorized`, `test_coverage_full_json` and `test_suggestions_order` assert full literal outputs, paging, nulls, dates, totals and order. |
| R3 | `test_reversed_dates_before_reading`, `test_transaction_error_context`, `test_merchant_invalid_before_session`, `test_merchant_lookup` and context/session assertions pin forwarding, read-only context exit, validation precedence and exception propagation. Existing public MCP and account ownership integration tests pass unchanged except the exact given mock-seam migration. |
| R4 | Fresh complete inventory probe and unchanged public MCP integration/capability/repository inventory tests establish the public schema, descriptions, annotations, signatures and permitted capabilities. |
| R5 | Given `test_all_mcp_sources_fit` recursively checks every current and future `.py` under MCP in the normal full pytest run. `test_recursive_size_gate_rejects_401` tests 400-line acceptance and nested 401-line refusal in a temporary copy. Scope/migration audit and source inspection confirm layering and no exemptions. |

There are 14 given and 15 coder cases, accounting for 4761 -> 4790. Current sizes include accounts 69, queues 204, tools 34, reports 244, proposals 222 and server 280 lines; every MCP source is <=400. The temporary facade/monolith exception has ended. Behavior tests assert complete results and calls rather than merely executing lines.

## Scratch-only spot checks

Each mutation used a separate disposable clone with confirmed clone import provenance and unchanged given tests. All four deciding tests failed with exit 1 for the intended assertion; reviewed bytes were not changed.

| Mutation | Given case | Broken observation |
|---|---|---|
| Remove reverse transfer sorting | `test_transfer_order_and_limit` | order begins with id 1 instead of 3 |
| Count transfers after limiting | `test_transfer_order_and_limit` | total 2 instead of 3 |
| Wrap facade get_balances | `test_facade_identity[accounts-get_balances]` | facade object differs from area function |
| Add a 401-line MCP source | `test_all_mcp_sources_fit` | oversize planted source appears in failure |

Logs: `/tmp/47h4-spot-{order,total,wrapper,cap}.log`. Scratch clones were removed. No unrelated validation masked these direct cases. No baseline, environment, specification/test or implementation blocker remains. PASS applies to the exact reviewed delivery commit. No implementation, progress or phase documents were edited; no commit or push performed.
