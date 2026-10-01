# Statement formats

Layouts of the PDF statements the app must parse, as seen in `pypdf` **layout-mode** text (`page.extract_text(extraction_mode="layout")`). In the examples below, runs of 2+ spaces are shown as ` | ` for readability; in real text they are just spaces.

**All example values here are synthetic.** Names, numbers, merchants, and amounts are invented. Real samples are in `data/samples/` (gitignored, see AGENTS.md rule 6).

Notes that apply to every format:
- Plain `pdftotext` scrambles the columns on several of these statements. Use `pypdf` layout mode.
- Row regexes below are starting points. Confirm them with the real-sample tests; exact spacing may differ.
- Lines that do not match a row pattern are ignored unless the format notes say otherwise. In particular, **continuation lines** (no leading date) are **ignored**, not appended. They sometimes contain passenger names or masked account numbers.
- "Holder perspective" signs (AGENTS.md): purchases negative, payments/credits to a card positive, card debt negative.

---

## 1. Capital One credit card (`capital_one_card`)

Seen on: Quicksilver (Visa), Savor (Mastercard). One account can have several cards, each with its own cardholder section.

**Detect:** first page contains `Capital One` or `capitalone.com` **and** `days in Billing Cycle`.

**Header lines:**
```
Quicksilver Credit Card | Visa Signature ending in 1111
Dec 24, 2025 - Jan 23, 2026 | 31 days in Billing Cycle
```
- `account_last4` from `ending in (\d{4})`.
- Period from `([A-Z][a-z]{2} \d{1,2}, \d{4}) - ([A-Z][a-z]{2} \d{1,2}, \d{4})`.

**Account summary** (label then amount; may share a line with other text):
```
Previous Balance | $25.60
Payments | - $25.60
Other Credits | - $15.65
Transactions | + $4,139.73
Cash Advances | + $0.00
Fees Charged | + $0.00
Interest Charged | + $0.13
New Balance | = $4,124.21
```
Opening balance = `-Previous Balance`, closing = `-New Balance` (holder perspective; a credit balance would be shown with a minus and flips the other way).

**Sections**, one pair per card:
```
JANE DOE #1111: Payments, Credits and Adjustments
Trans Date | Post Date | Description | Amount
Jan 11 | Jan 12 | CAPITAL ONE MOBILE PYMT | - $500.00
JANE DOE #1111: Transactions
Trans Date | Post Date | Description | Amount
Dec 27 | Dec 29 | ACME VENDING DallasGrapevineTX | $3.00
Jan 5 | Jan 6 | FOOBAR CHICKEN #123TUCKERGA | $38.96
Apr 12 | Apr 13 | EXAMPLE AIR0012345678FORT WORTHTX
                     TK#: 0012345678 PSGR: DOE/JANE          <- continuation: ignore
JANE DOE #1111: Total Transactions
JOHN DOE #2222: Transactions
...
Total Transactions for This Period | $1,514.46
```
- Section header regex: `^(.+?) #(\d{4}): (Payments, Credits and Adjustments|Transactions|Total Transactions)`. Sets current `cardholder`, `card_last4`, and section (`payments_credits` / `purchases`).
- Row regex: `^([A-Z][a-z]{2} \d{1,2})\s+([A-Z][a-z]{2} \d{1,2})\s+(.+?)\s+(- )?\$([\d,]+\.\d\d)$`.
- Amount sign: `- $X` → `+X` (credit to you). `$X` → `-X` (purchase).
- Descriptions have merchant, city, and state run together (`FOOBAR CHICKEN #123TUCKERGA`). Keep as-is; Phase 11 normalizes.
- Pages repeat the header and say `Transactions (Continued)`; current section/cardholder carries over pages.

**Fees and interest** are summary lines without dates:
```
Total Fees for This Period | $0.00
Interest Charge on Purchases | $0.13
Interest Charge on Cash Advances | $0.00
Interest Charge on Other Balances | $0.00
```
For each nonzero `Interest Charge on ...` line, emit a line dated `period_end`, section `interest`, description e.g. `INTEREST CHARGE ON PURCHASES`, amount negative. Same for nonzero total fees (section `fees`) if no dated fee rows were found.

**Ignore:** rewards summary, minimum payment warning table, `Total Interest charged` year-to-date lines.

---

## 2. Bank of America credit card (`boa_card`)

**Detect:** `bankofamerica.com` and `Account#`.

**Header:**
```
Account# 4400 0000 0000 1111
March 29 - April 28, 2026
```
- `account_last4` = last 4 digits of `Account#`.
- Period: `(\w+ \d{1,2}) - (\w+ \d{1,2}), (\d{4})`. Only the end has a year; the start year is the same, or one less if the start month is later than the end month (December to January).

**Summary** labels (values may appear on a different line in some extractions; search with a regex per label across the page text):
```
Previous Balance | $1,559.05
Payments and Other Credits | -$6,985.57
Purchases and Adjustments | $6,699.61
Fees Charged | $0.00
Interest Charged | $0.00
New Balance Total | $1,273.09
```

**Transactions:**
```
Transaction | Posting | Description | Reference Number | Account Number | Amount
Payments and Other Credits
04/03 | 04/06 | EXAMPLESOFT*STORE | REDMOND | WA | 3012 | 1111 | -43.19
04/07 | 04/07 | PAYMENT FROM CHK 9999 CONF#M00000000 | 4733 | 1111 | -902.05
TOTAL PAYMENTS AND OTHER CREDITS FOR THIS PERIOD | -$6,985.57
Purchases and Adjustments
03/28 | 03/30 | ACME GROCERY #123 DECATUR GA | 7838 | 2222 | 36.49
TOTAL PURCHASES AND ADJUSTMENTS FOR THIS PERIOD | $6,699.61
Fees Charged ...
Interest Charged
04/28 | 04/28 | INTEREST CHARGED ON PURCHASES | 0.00
```
- Row regex (with reference): `^(\d\d/\d\d)\s+(\d\d/\d\d)\s+(.+?)\s+(\d{4})\s+(\d{4})\s+(-?[\d,]+\.\d\d)$` → trans date, post date, description, reference (`external_id`), card last4, amount.
- Row regex (interest/fee rows, no reference): `^(\d\d/\d\d)\s+(\d\d/\d\d)\s+(.+?)\s+(-?[\d,]+\.\d\d)$`. Skip rows whose amount is `0.00`.
- File signs: purchases positive, credits negative. **Invert** to holder perspective.
- Section is tracked from the section header lines. Use the `TOTAL ... FOR THIS PERIOD` lines as declared section totals.
- Pages contain `continued on next page...` and repeat the column header.
- No cardholder names per card on this statement; leave `cardholder` empty.

---

## 3. Citi credit card (`citi_card`)

Seen on: Costco Anywhere Visa. Multiple cardholders.

**Detect:** `citicards.com` and `Billing Period:`.

**Header:**
```
Account number ending in: 1111
Billing Period: 08/13/26-09/10/26
```
Two-digit years.

**Summary:**
```
Previous balance | $0.00
Payments | -$0.00
Credits | -$43.28
Purchases | +$759.22
Cash advances | +$0.00
Fees | +$0.00
Interest | +$0.00
New balance | $715.94
```
(Values may be on lines separate from labels; search per label.)

**Cardholder summary** maps names to cards:
```
CARDHOLDER SUMMARY
JOHN DOE | Card ending in 1111 | New Charges | $759.22
JANE DOE | Card ending in 2222 | New Charges | $0.00
```

**Transactions:**
```
Sale | Post | Description | Amount
Date | Date
Payments, Credits and Adjustments
09/03 | 09/03 | ACME WHSE #1234 ALLEN TX | -$43.28
JOHN DOE
Standard Purchases
09/01 | 09/01 | ACME GAS #1234 ALLEN TX | $28.96
        09/06 | EXAMPLE CENTER DALLAS TX | $27.05        <- no sale date: use post date only
JANE DOE
No Activity
Fees Charged
TOTAL FEES FOR THIS PERIOD | $0.00
Interest Charged
TOTAL INTEREST FOR THIS PERIOD | $0.00
```
- Row regex: `^(?:(\d\d/\d\d)\s+)?(\d\d/\d\d)\s+(.+?)\s+(-)?\$([\d,]+\.\d\d)$`.
- File signs: purchases `$X` (→ `-X`), credits `-$X` (→ `+X`).
- A line consisting only of a cardholder name from the cardholder summary sets the current cardholder and card.
- Ignore the rewards summary pages.

---

## 4. Truist checking and savings (`truist_deposit`)

**Detect:** `Truist` and `Your account statement`.

**Header:**
```
Your account statement
For 09/11/2026
TRUIST ONE CHECKING - LEVEL 1 1000000001111
```
or `TRUIST ONE SAVINGS 4110000001111`. Account type from the product name (`CHECKING` / `SAVINGS`); `account_last4` = last 4 digits of the number on that line. Some header text extracts letter-spaced (`T | r u | i s | t .c | o | m`); ignore it.

**Summary:**
```
Your previous balance as of 08/12/2026 | $2,552.23
Checks | - 0.00
Other withdrawals, debits and service charges | - 14,423.64
Deposits, credits and interest | + 13,390.00
Your new balance as of 09/11/2026 | = $1,518.59
```
- `period_start` = previous-balance date + 1 day, `period_end` = new-balance date. Savings statements can be quarterly.
- Labels and values can be misaligned in extraction; search per label.

**Sections** (amounts are unsigned; the section decides the sign):
```
Checks                                                     -> negative (row format not yet seen; see Phase 6)
Other withdrawals, debits and service charges              -> negative
DATE | DESCRIPTION | AMOUNT($)
08/17 | DEBIT CARD PURCHASE ACME*Terminal3 08-15 Lisboa | 2979 | 200.00
08/17 | INTERNET PAYMENT TRANSFER | EXAMPLE SAVINGS BA 000300000001111 | 11,000.00
08/20 | DEBIT CARD RECURRING PYMT STREAMCO.COM 08-19 866-555-0100 | CA | 2979 | 9.99
Total other withdrawals, debits and service charges | = $14,423.64
Deposits, credits and interest                             -> positive
08/14 | INCOMING WIRE TRANSFER WIRE REF# 20260814-00000000 | ...
Total deposits, credits and interest | = $13,390.00
```
- Row regex: `^(\d\d/\d\d)\s+(.+?)\s+([\d,]+\.\d\d)$`. Year from `period_end` (use the year-inference helper).
- Debit card rows embed the purchase date as `MM-DD` after the merchant (`... 08-15 Lisboa`): if found, set `transaction_date` from it. A trailing 4-digit token before the amount is the debit card's last4 → `card_last4`.
- A statement with no activity has no sections; that is valid (zero lines, opening == closing).

---

## 5. Marcus by Goldman Sachs savings (`marcus_savings`)

**Detect:** `Goldman Sachs Bank USA` and `ONLINE SAVINGS ACCOUNT STATEMENT`.

**Header:**
```
Statement Period | 09/01/2026 to 09/30/2026
Account Number | 300100001111
```

**Activity:**
```
Date | Description | Credits | Debits | Balance
09/01/2026 | Beginning Balance | $14,646.12
09/01/2026 | ACHDepositInternettransferfromEXAMPLE BANKDDAaccount | $3,000.00 | $17,646.12
                ****************1111                         <- continuation: ignore
09/17/2026 | ACHWithdrawalInternettransfertoEXAMPLE BANK,N.A. | $5,000.00 | $12,646.12
09/30/2026 | InterestPaid | $40.13 | $12,686.25
09/30/2026 | EndingBalance | $12,686.25
```
- Full 4-digit years.
- Rows have one amount plus a running balance: `^(\d\d/\d\d/\d{4})\s+(.+?)\s+\$([\d,]+\.\d\d)\s+\$([\d,]+\.\d\d)$`.
- **Sign comes from the running balance**: `amount = balance_this_row - balance_previous_row`. Then check that `abs(amount)` equals the printed amount. This avoids depending on which column the amount sits in.
- Opening balance from `Beginning Balance`, closing from `Ending Balance`. Do not emit those as lines.
- This extraction drops spaces inside descriptions (`ACHDepositInternettransfer...`). Accept that for now; the Phase 11 normalizer handles matching.

---

# CSV exports

CSV exports are **provisional**: they fill the gap after the latest statement and are replaced by the statement once it is imported (Phase 8). Not every institution offers CSV (Marcus does not).

Both exports seen so far are plain UTF-8 with a header row and no preamble. Profiles are auto-detected by an exact header match.

## 6. Truist checking CSV (`truist_checking_csv`)

**Filename:** `acct_<last4>_<MM>_<DD>_<YYYY>_to_<MM>_<DD>_<YYYY>.csv`; the account last4 comes from the filename.

**Header (exact):**
```
Posted Date,Transaction Date,Transaction Type,Check/Serial #,Full description,Merchant name,Category name,Sub-category name,Amount,Daily Posted Balance
```

**Rows (synthetic):**
```
08/03/2026,08/01/2026,POS,,EXAMPLESTREAM.COM 08-01 SURREY BC 1234 DEBIT CARD PURCHASE,Examplestream.com,Business,Electronics & computers,($50.00),$5067.80
08/03/2026,08/03/2026,Debit,,EXAMPLESTREAM.COM 08-01 SURREY BC 1234 INT'L SERVICE ASSESSMENT FEE,,Taxes & Fees,Other fees and charges,($1.50),$5067.80
08/03/2026,08/03/2026,Deposit,,DEPOSIT,,Deposits,Other deposits,$2000.00,$5067.80
08/06/2026,08/06/2026,Debit,,Jane Doe PAYMENT ID ABC000000000 ZELLE PAYMENT TO,Zelle,Transfers & Payments,Digital wallet,($300.00),$4767.80
```
- Oldest first. Full 4-digit-year dates for both posted and transaction date.
- `Amount`: `($1.50)` negative, `$2000.00` positive. Already holder perspective. No thousands separators seen, but accept them.
- `Daily Posted Balance` is the **end-of-day balance**, repeated on every row of that day. For each day after the first: previous day's balance + that day's amounts = that day's balance. This must hold or the import is refused.
- `Merchant name` and `Category name` / `Sub-category name` are the bank's own cleanup. Store them as hints (`bank_merchant`, `bank_category` = `"Category / Sub-category"`); they are not authoritative (e.g. transfers to the user's own savings are labeled "Investments").
- `Transaction Type` values seen: `POS`, `Debit`, `Deposit`, `Credit`. Store nothing extra for now.
- Descriptions are ordered differently from the PDF statement for the same transaction (`... DEBIT CARD PURCHASE` at the end vs the start). Posted date and amount match the statement exactly.
- Zelle rows contain a person's name in the description. Fine locally; Phase 14 (privacy payload) must strip it.

## 7. Citi card CSV (`citi_card_csv`)

**Filename:** user-chosen / date-based (e.g. `Since Sep 11, 2026.CSV`). **No account identifier**: `--account` is required.

**Header (exact):**
```
Status,Date,Description,Debit,Credit,Member Name
```

**Rows (synthetic):**
```
Cleared,09/23/2026,"ACME*Terminal3 Lisboa PT",60.00,,JOHN DOE
Cleared,09/23/2026,"ONLINE PAYMENT, THANK YOU",,-500.00,JOHN DOE
Cleared,09/14/2026,"FOOBAR LEGACY 131-00000000 TX",8.04,,
Pending,09/25/2026,"ACME WHSE #0000 PLANO TX",12.00,,JOHN DOE
```
- Newest first. Single `Date` column (treated as posted date; it may be the sale date, which is why statement matching allows a few days of difference).
- `Debit` = purchase, positive in the file → negative. `Credit` = payment/refund, **negative** in the file → positive. Always use the absolute value and let the column decide the sign.
- `Status`: import only `Cleared`. Skip anything else (e.g. `Pending`) and report the count.
- `Member Name` → `cardholder`; may be blank → `None`.
- No balance column, so no balance check and no balance snapshot.

## Cross-source notes

- The checking account's payment to a card references a card number that does **not** match the card's last4 on the card statement. Transfer matching (Phase 11) must rely on amount and date, not on numbers inside descriptions.
