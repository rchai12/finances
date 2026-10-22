# Review: Phase 14e

- Verdict: PASS
- Passed: 3259
- Findings: 0
- Approved deviations: none
- For the architect: none

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

## Gates

- `scripts/check.py`: `3259 passed`, `All checks passed.` (N + 28 = 3254; extra 5)
- Given tests: `28 passed`
- Earlier MCP tests plus `test_health_facts`: `80 passed`
- Coverage of `mcp_server`, `domain.periods`, `domain.merchants`, `analysis.coverage`, `analysis.names`: `Required test coverage of 100% reached`
- `git grep` of domain imports: no output
- `git grep` of mcp views/web/cli imports: no output
- `git grep` of log/print: no output
- `git diff --stat HEAD -- tests`: exactly the five files of the earlier-tests diff
- Given files match the spec blocks; the two descriptions match the spec's text

## Requirement checklist

- R1: `test_joined_periods`
- R2: `test_the_score`
- R3: `test_best_first_merchants_before_categories_on_a_tie`; `test_a_tie_of_the_same_kind_goes_by_name`; `test_the_limit_and_nothing_close`
- R4: `test_data_coverage`
- R5: `test_find_merchants`
- R6: `test_data_coverage`
- R7: `test_find_merchants`; `test_a_refused_phrase`; `test_a_limit_out_of_range`
- R8: `test_eighteen_read_only_tools`; `test_the_read_only_tools`; `test_each_tool_description_matches_the_table`
- R9: given earlier-test diffs applied; `git diff --stat HEAD -- tests` lists those five files
- R4 to R7 edges: `tests/integration/test_mcp_coverage_more.py` (no data; a closed account; a stale statement; empty-database categories; a pending merchant)

## Probe

None. Use the spot checks.

## Spot checks

Each change was made in the named place, the named tests run, and the file restored from a copy (not git checkout), with `__pycache__` cleared.

1. `closest_names` keeps scores above the threshold only (`>`): `test_best_first_merchants_before_categories_on_a_tie` (groceries) fails (FOOBAR GROCERY missing).
2. Categories before merchants on a tie: the same (cofee) fails (`Coffee & Dessert` first).
3. The similarity rounds down (`200 * M // T`): `test_the_score[that coffee place-ACME UTILITY-67]` fails (`66`).
4. `joined_periods` joins only overlapping periods: `test_joined_periods[next day joins]` fails (two runs).
5. `joined_periods` joins periods one day apart: `test_joined_periods[one day apart stays]` fails (one run).
6. `data_coverage` keeps an empty account as `""`: `test_data_coverage` (the backup problem) fails (`""`).

## Out of scope

Absent: a new dependency; an embedding or index; a page or command; a write.
