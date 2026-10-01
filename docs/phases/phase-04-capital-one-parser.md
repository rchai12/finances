# Phase 4: Capital One credit card parser

## Goal

The first real bank parser: Capital One credit card statements (Quicksilver, Savor, and any other Capital One card using the same layout), including multiple cardholders and year wrap. This phase also sets the pattern later parsers copy.

## Read first

- `AGENTS.md` (rule 6: real samples)
- `docs/statement-formats.md`, section 1 (Capital One)
- `docs/progress.md`
- `src/finances/ingest/parsers/`, `src/finances/ingest/statement.py`, `src/finances/ingest/reconcile.py`

## In scope

- `src/finances/ingest/parsers/capital_one.py` implementing `StatementParser` with `name = "capital_one_card"`
- Registration in the parser registry
- Synthetic text fixtures and tests

## Out of scope

Other banks. Changes to the import service, unless a genuine bug is found (record it in `docs/progress.md`).

## Dependencies

None new.

## Requirements

Follow `docs/statement-formats.md` section 1. In particular:

1. **Detection**: as specified; must not match the other formats' synthetic fixtures once they exist (add negative tests then).
2. **Header**: `account_last4`, period start/end with years from the period line.
3. **Balances**: opening = `-(Previous Balance)`, closing = `-(New Balance)`. `account_type = credit_card`, `institution = "Capital One"`.
4. **Sections and cardholders**: section headers set `cardholder`, `card_last4`, and `section` (`payments_credits` or `purchases`). State persists across page breaks.
5. **Rows**: transaction date and post date both parsed with `parse_month_day` against the statement period. Amount sign flipped to holder perspective.
6. **Continuation lines** ignored.
7. **Interest and fees**: nonzero summary lines become dated lines at `period_end`, as described.
8. **Declared totals**: if `Total Transactions for This Period` is present, record it as the declared total of the `purchases` section (holder perspective, negative).
9. Structure the parser as small functions (`_parse_header`, `_parse_summary`, `_iter_rows`, ...) operating on lines, so it is readable and testable in isolation.

## Fixtures (`tests/fixtures/statements/capital_one/`)

Hand-written `.txt` files that mimic layout-mode text (pages separated by a form-feed `\f` or a clear marker your loader splits on). Synthetic values only. Create at least:

- `single_card.txt`: one cardholder, 2 payments/credits, ~8 purchases, nonzero interest, over 2 pages with a `Transactions (Continued)` page break.
- `multi_card.txt`: three cardholder sections (different names and last4s), one with no payments section.
- `year_wrap.txt`: period Dec 24, 2025 to Jan 23, 2026 with a transaction dated Dec 23 and others in January.
- `continuation.txt`: an airline-style row followed by two continuation lines.
- `credit_balance.txt`: statement where the new balance is a credit (balance shown negative), to confirm sign handling.

All fixtures must reconcile exactly (compute the summary numbers from the rows when writing them).

## Tests (`tests/test_parser_capital_one.py`)

- Detection true for each fixture.
- Header, period, and balances correct for `single_card`.
- Line count, sum, and sections correct; interest line present with `period_end` date.
- `multi_card`: each line carries the right cardholder and card last4.
- `year_wrap`: Dec 23 line has year 2025, January lines 2026.
- `continuation`: continuation text does not appear in any description, and line count is unaffected.
- `reconcile()` ok for every fixture.
- End-to-end through `import_statement` with monkeypatched `extract_pages` for one fixture: inserted count, balance snapshot written.

## Acceptance criteria

```powershell
ruff check . ; ruff format --check . ; pytest
$env:FIN_REAL_SAMPLES=1; pytest -m real_samples; Remove-Item Env:FIN_REAL_SAMPLES
```
- Both Capital One samples in `data/samples/` **pass** (detected, parsed, reconciled). Other samples remain xfail.
- `fin import folder data/samples --dry-run` shows the Capital One files as reconciled (they will fail account matching until the accounts are added; that is expected and the hint must show the right last4).

If a real sample does not reconcile, follow AGENTS.md rule 6: report the cent difference and line counts, adjust using the format doc, and record any format discoveries (in synthetic form) in `docs/statement-formats.md`.

Append your entry to `docs/progress.md`.
