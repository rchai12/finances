# Phase 6: Truist and Marcus deposit account parsers

## Goal

Parsers for checking and savings statements, completing coverage of every sample statement. After this phase, `fin import folder data/samples` imports everything.

## Read first

- `AGENTS.md` (rule 6)
- `docs/statement-formats.md`, sections 4 (Truist) and 5 (Marcus)
- `docs/progress.md`
- Existing parsers and `parsers/helpers.py`

## In scope

- `parsers/truist.py` (`name = "truist_deposit"`, institution `"Truist"`, type checking or savings from the product name)
- `parsers/marcus.py` (`name = "marcus_savings"`, institution `"Marcus by Goldman Sachs"`, type savings)
- Registration, fixtures, tests

## Out of scope

Transfer detection between accounts (Phase 9), even though these statements are full of transfers.

## Truist requirements

- Period from previous-balance and new-balance dates.
- Section-driven sign: withdrawals and checks negative, deposits positive.
- Embedded `MM-DD` purchase date → `transaction_date`; trailing debit card last4 → `card_last4`.
- Declared section totals from the `Total ...` lines.
- No-activity statements (savings, possibly quarterly) parse to zero lines and reconcile.
- **Checks section**: the row format has not been seen yet. Implement the most likely shape (`MM/DD`, check number, amount) and rely on reconciliation. If the `Checks` summary total is nonzero and no check rows were parsed, reconciliation must fail (it will, naturally). Note this as a known gap in `docs/progress.md`.

## Marcus requirements

- Full-year dates; skip `Beginning Balance` / `Ending Balance` rows but use them as opening/closing.
- Sign from the running balance delta, cross-checked against the printed amount (mismatch → `StatementError` naming the row number, not its contents).
- Continuation lines ignored.
- Descriptions without spaces are accepted as-is.

## Fixtures (`tests/fixtures/statements/truist/`, `.../marcus/`)

Synthetic only, all reconciling.
- Truist: `checking_basic.txt` (withdrawals incl. debit card purchases with embedded dates, deposits), `savings_no_activity.txt`, `letter_spaced_header.txt` (includes the letter-spaced garbage header line, which must be ignored).
- Marcus: `basic.txt` (deposit, two withdrawals, interest, continuation lines), `interest_only.txt`, `amount_mismatch.txt` (printed amount disagrees with balance delta, must raise).

## Tests

Same shape as earlier parsers, plus negative detection across all fixtures from Phases 4 to 6, section-driven signs, embedded-date extraction, running-balance sign logic, and the mismatch error.

## Acceptance criteria

```powershell
ruff check . ; ruff format --check . ; pytest
$env:FIN_REAL_SAMPLES=1; pytest -m real_samples; Remove-Item Env:FIN_REAL_SAMPLES
```
- **All** samples in `data/samples/` pass.
- After adding the accounts (`fin accounts add ... --last4 ...` for each), `fin import folder data/samples` imports every file with status `imported`, and running it again reports every file as `already_imported`.

Append your entry to `docs/progress.md`.
