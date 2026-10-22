# Review: Phase 35b

- Verdict: PASS
- Passed: 3145
- Findings: 0
- Approved deviations: None
- For the architect: none

## Findings

None

Parts that needed a repair: none

Built beyond the spec: none

## Gates

- `scripts/check.py`: `3145 passed`, `All checks passed.` (N + 27 = 3138; extra 7)
- Given tests: `27 passed`
- Earlier search, account, cards, and style tests: `83 passed`
- Coverage of `domain.spending`, `domain.refunds`, `analysis.search`, `analysis.refunds`, `views.transactions`, `views.categories`, `web.routes.transactions`, `web.routes.categories`, `cli.categories`: `Required test coverage of 100% reached`
- `git grep` of domain imports: no output
- `git diff --stat HEAD -- tests`: exactly the three files of the earlier-tests diff
- Given files match the spec blocks; the template, CSS, and earlier-test diffs match the given diffs

## Requirement checklist

- R1: `test_a_refund_is_money_back_on_spending`; `test_refund_is_a_kind_to_search_by_but_not_a_flow_kind`
- R2: `test_the_likely_purchase`
- R3: `test_only_refunds`; `KIND_MESSAGE` / `KINDS` in the earlier-test diff
- R4: `test_refunds_carry_a_label`
- R5: `test_a_refund_names_its_likely_purchase`; `test_the_purchase_names_its_refund`; `test_a_refund_with_no_purchase`; `test_no_refund_section_where_none_applies`
- R6: `test_a_refund_names_its_likely_purchase`; `test_the_purchase_names_its_refund`
- R7: `test_money_in_on_a_card_without_a_category`; `test_uncategorized_money_in_on_a_card_is_flagged`; `test_no_flag_without_money_in_on_a_card`
- R8: given template and CSS diffs applied
- R9: given earlier-test diffs applied; `git diff --stat HEAD -- tests` lists those three files
- R5 edges: `tests/integration/test_refunds_found_more.py` (closed account, two refunds oldest first, other account, pending never a purchase, account badge, kind with category, missing id)

## Probe

None.

## Spot checks

Each change was made in the named place, the named tests run, and the file restored from a copy (not git checkout), with `__pycache__` cleared.

1. `likely_purchase` takes the earliest purchase (`min` of days): `test_the_likely_purchase[the latest that fits]` fails (1).
2. `likely_purchase` allows purchases after the refund (no `<= day`): `[after the refund]` fails (1).
3. The window stops one day short (`start < item.day`): `[90 days before]` fails (`None`).
4. A tie goes to the lowest id (`min` of ids): `[a tie goes to the newest]` fails (3).
5. `is_refund` also counts money in without a category: `test_refunds_carry_a_label` fails (QUUX CREDIT category cell `refund`).
6. `refund_facts` lists every refund of the merchant on a purchase: `test_no_refund_section_where_none_applies[1]` fails (a Refunds section).
7. `card_credits_note` counts every account's money in: `test_money_in_on_a_card_without_a_category` fails (`Money in on a card: 2`).
8. `kind=refund` keeps spending of either sign: `test_only_refunds` fails (five rows).

## Out of scope

Absent: a migration or a stored match; a kind option in the terminal; a Kind column on transactions; any change to totals, reports, budgets, insights, or transfers.
