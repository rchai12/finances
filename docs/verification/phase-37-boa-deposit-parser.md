# Verify Phase 37: Bank of America checking and savings

Spec: `docs/phases/phase-37-boa-deposit-parser.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder added a sixth statement parser, `boa_deposit`, for Bank of America checking and savings statements. Three fixtures and one test file were given.

These are correct and must not be reported: private helpers and patterns of the coder's own; the order of the patterns tried on a line, as long as the given and listed cases hold; a period or balance matched with `search` rather than at the line start.

Do not open, print, or quote anything under `data/samples/` (AGENTS.md rule 6). The real-sample check is the owner's to run.

## 1. Gates

N is `3952` when Phase 20d was the last phase built.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py` | last line `All checks passed.`; at least N + 26 passed, 0 failed, 0 skipped, 0 xfailed |
| `.venv/bin/python -m pytest tests/unit/test_boa_deposit_parser.py --no-cov` | exactly `26 passed` |
| `.venv/bin/python -m pytest tests/unit -o addopts="" --import-mode=importlib --cov=finances.ingest.parsers.boa_deposit --cov-branch --cov-report=term-missing --cov-fail-under=100` | `Required test coverage of 100% reached` |
| `git diff --stat HEAD -- tests` | no output |
| `git diff --stat HEAD -- src` | only `src/finances/ingest/parsers/__init__.py` |

## 2. Scope paths

`git status --short` lists `docs/progress.md`, `src/finances/ingest/parsers/__init__.py`, and as new: `src/finances/ingest/parsers/boa_deposit.py`, `tests/fixtures/statements/boa_deposit/`, `tests/unit/test_boa_deposit_parser.py`, `tests/unit/test_boa_deposit_parser_more.py`. The given test file equals the spec's. Each fixture equals the spec's with each `----- page break -----` line read as one form feed: check with `.venv/bin/python -c "import pathlib; print([p.name for p in sorted(pathlib.Path('tests/fixtures/statements/boa_deposit').glob('*.txt')) if p.read_text(encoding='utf-8').count(chr(12)) != (p.stem == 'checking')])"`, which must print `[]`, and compare the text by eye.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (`test_the_parser_is_registered_once_under_its_name`) | pass |
| R2 | gate 2 (`test_detects_its_own_fixtures`, `test_does_not_detect_another_statement`) | pass |
| R3 | gate 2 (`test_checking_header_balances_and_totals`, `test_savings`, `test_year_end`); the coder's product-line case | pass |
| R4 | gate 2 (the same three); the coder's overdrawn case | pass |
| R5 | gate 2 (`test_checking_lines`, `test_the_page_breaks_do_not_matter`); the coder's summary-line case | pass |
| R6 | gate 2 (`test_checking_lines`); the coder's reversal and zero cases | pass |
| R7 | gate 2 (`test_checking_lines`, `test_year_end`); the coder's impossible-day case | pass |
| R8 | gate 2 (`test_checking_lines`); the coder's star-before case | pass |
| R9 | gate 2 (`test_checking_header_balances_and_totals`, `test_a_missing_part_is_refused`, `test_an_impossible_row_date_is_refused`); `tests/unit/test_parser_fuzz.py` in gate 1 | pass |

## 4. Probe

None. The fuzz test already feeds every registered parser damaged copies of every fixture.

## 5. The coder's tests and spot checks

For each item of the spec's "Tests to write", name the test that covers it; an item with no test is a finding. Each test asserts behaviour, uses synthetic data, and computes no expected value with the code under test.

Each row below is one change to the parser. The deciding test must fail under it.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. account type: `Savings` anywhere on the first page | given `test_checking_header_balances_and_totals` (the `Tip: … Savings account.` line after the account line) | `CHECKING` | `SAVINGS` |
| 2. `WITHDRAWALS` total: only one of the two labels | given `test_checking_header_balances_and_totals` | `-180640` | `-18640` or `-162000` |
| 3. checks: one check per line (`fullmatch`) | given `test_checking_lines` (`09/10/26 1041 … 09/14/26 1042* …`) | checks 1041 and 1042 | one or both missing |
| 4. checks: no `*` after the number | given `test_checking_lines` (`1042*`) | `CHECK 1042` | missing |
| 5. wrapped lines appended to the description | given `test_checking_lines` (`CO ID:XXXXX00002 PPD`) | the description without it | with it |
| 6. `account_last4` from the first group | given `test_checking_header_balances_and_totals` (`0000 1234 1111`) | `1111` | `0000` |
| 7. purchase date in the posted row's year | given `test_year_end` (`01/02/27 CHECKCARD 1231`) | `2026-12-31` | `2027-12-31` |

## 6. Out of scope

Each must be absent: changes to another parser, `describe_layout.py`, `check_real_samples.py`, or the import service; a `card_last4` or cardholder on these rows; a CSV profile.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation and design choice it lists is real, justified, and inside the spec's Scope.
