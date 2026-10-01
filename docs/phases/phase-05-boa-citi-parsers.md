# Phase 5: Bank of America and Citi credit card parsers

## Goal

Two more credit card parsers, following the pattern established in Phase 4.

## Read first

- `AGENTS.md` (rule 6)
- `docs/statement-formats.md`, sections 2 (BoA) and 3 (Citi)
- `docs/progress.md`
- `src/finances/ingest/parsers/capital_one.py` and its tests (the pattern to follow)

## In scope

- `parsers/boa.py` (`name = "boa_card"`, institution `"Bank of America"`)
- `parsers/citi.py` (`name = "citi_card"`, institution `"Citi"`)
- Registration, fixtures, tests
- If you find code duplicated across three parsers (e.g. summary label lookup), move it into `parsers/helpers.py`. Keep that refactor small and covered by the existing tests.

## Out of scope

Bank deposit accounts (Phase 6), changes to the import service.

## BoA requirements

- Period start year inference (only the end date carries a year).
- Row regexes for both the referenced rows and the reference-less interest/fee rows; skip zero-amount rows.
- `external_ref` = reference number; `card_last4` = account-number column.
- Invert file signs.
- Declared section totals from `TOTAL PAYMENTS AND OTHER CREDITS FOR THIS PERIOD` (`payments_credits`) and `TOTAL PURCHASES AND ADJUSTMENTS FOR THIS PERIOD` (`purchases`), converted to holder perspective.
- Summary values can be separated from their labels in extraction. If `find_labeled_amount` is not reliable for BoA, derive opening and closing from the labeled values that *are* reliable and let reconciliation prove correctness. Document what you did in `docs/progress.md`.

## Citi requirements

- Two-digit-year billing period.
- Optional sale date (use post date only when missing; `transaction_date = None`).
- Cardholder summary maps names to card last4; a bare cardholder-name line switches the current cardholder.
- `No Activity` lines ignored.
- Invert file signs.

## Fixtures (`tests/fixtures/statements/boa/`, `.../citi/`)

Synthetic only, all reconciling exactly.
- BoA: `basic.txt` (credits + purchases across a page break, `continued on next page...`, zero interest rows), `two_cards.txt` (rows with two different account-number last4 values), `dec_jan.txt` (period December to January).
- Citi: `basic.txt` (one cardholder with purchases, one with `No Activity`, one credit), `missing_sale_date.txt`, `two_cardholders.txt`.

## Tests

Same shape as Phase 4: detection (plus **negative detection**: every parser must return false for every other bank's fixtures, including Capital One's), header, balances, lines, signs, cardholder/card attribution, zero-row skipping, reconcile ok, one end-to-end import per parser.

## Acceptance criteria

```powershell
ruff check . ; ruff format --check . ; pytest
$env:FIN_REAL_SAMPLES=1; pytest -m real_samples; Remove-Item Env:FIN_REAL_SAMPLES
```
- BoA and Citi samples pass, as well as Capital One. Remaining samples (Truist, Marcus) xfail.

Append your entry to `docs/progress.md`.
