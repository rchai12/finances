# Verify Phase 2b: Money helpers

Spec: `docs/phases/phase-02b-money-helpers.md`

Do not modify any file in the repository. Report findings only. The work under review is normally uncommitted, so "the diff" means `git status --short` plus `git diff HEAD`.

## 1. Gates

Run each command on its own line.

| Command | Expected |
|---|---|
| `ruff check .` | no problems |
| `ruff format --check .` | no files would be reformatted |
| `pytest` | exit code 0, at least 72 tests passed, 0 skipped, 0 xfailed, `TOTAL` at least 85% |

In the coverage table, the row for `src/finances/domain/money.py` must show 100% and an empty `Missing` column. Anything less is a FAIL, because this is a critical module (`docs/testing.md`).

## 2. Scope audit

- `git status --short` lists only: `src/finances/domain/__init__.py`, `src/finances/domain/money.py`, `tests/unit/test_money.py`, `docs/progress.md`. Report every other path.
- `src/finances/domain/__init__.py` is empty.
- `git diff HEAD -- pyproject.toml` is empty (no new dependency).
- `git diff HEAD -- tests/conftest.py tests/unit/test_config.py tests/unit/test_diagnostics.py tests/unit/test_log.py tests/e2e` is empty.
- `src/finances/domain/` contains no file other than `__init__.py` and `money.py`.

## 3. Requirement checklist

Read `src/finances/domain/money.py` for the "read" rows.

| Id | Check | How | Pass when |
|---|---|---|---|
| R1 | signatures | read | `def parse_money(text: str) -> int` and `def format_cents(cents: int) -> str`, both with these exact names and type hints |
| R1 | step order | read | outer `strip()` first; then one negative marker chosen by `if / elif / elif` in the order parentheses, trailing `-`, leading `-`; then one optional `$`; then `fullmatch`; no second `strip()` anywhere |
| R1 | pattern | read | the compiled pattern equals the one in the spec (R1, step 4) character for character, and it is applied with `fullmatch`, not `match` or `search` |
| R1 | conversion | read | cents come from `Decimal`, multiplied by 100, converted with `int(...)` |
| R2 | valid inputs | probe script, section 4 | all `valid` lines print `ok` |
| R3 | invalid inputs | probe script | all `invalid` lines print `ok` |
| R4 | message | probe script | all `message` lines print `ok` |
| R5 | ASCII only | `git grep -n -F "\d" -- src/finances/domain/money.py` | no matches; probe script `ascii` lines print `ok` |
| R6 | return type | probe script | `type` line prints `ok` |
| R7 | formatting | read and probe script | uses `divmod(abs(cents), 100)`; all `format` lines print `ok` |
| R8 | round trip | probe script | `roundtrip` line prints `ok` |

## 4. Independent probes

Most of these inputs are **not** in the spec's tables. They catch an implementation that special-cases the listed examples or uses `float` (`0.29`, `4.35`, and `1.15` each come out one cent low when multiplied as floats).

Save the script below in a temporary directory **outside the repository**, run it with `python <path>`, and delete it afterwards. Every line must end in `ok`; the last line must be `FAILURES 0`.

```python
from finances.domain.money import format_cents, parse_money

D = "$"
failures = 0


def check(label, ok):
    global failures
    failures += 0 if ok else 1
    print(label, "ok" if ok else "FAIL")


VALID = {
    "0.29": 29, "4.35": 435, "1.15": 115, D + "0.07": 7, "(1,000)": -100000,
    "999,999.99-": -99999999, "0012.30": 1230, " \t" + D + "3\n": 300,
    D + "1,234,567,890.12": 123456789012, "-.05": -5, "(0)": 0, "1,234": 123400,
    "-" + D + "12.34": -1234, "(" + D + "1,234.56)": -123456, "-0.00": 0,
}
for text, want in VALID.items():
    try:
        got = parse_money(text)
    except Exception as exc:  # noqa: BLE001
        got = repr(exc)
    check(f"valid {text!r} -> {want}", got == want)

INVALID = [
    "", "   ", "(", ")", "()", "12,34", "1.2.3", "-(5)", "Infinity", "0x10", "1_000",
    "12.345", "1,23.45", "1234,567", "--5", "(-5)", "-5-", D + "-5", D + D + "5",
    "+5", "1 000", D + " 5", "- 5", "1e3", "NaN", "12.",
]
for text in INVALID:
    try:
        parse_money(text)
        check(f"invalid {text!r}", False)
    except ValueError as exc:
        check(f"invalid {text!r}", True)
        check(f"message {text!r}", str(exc) == "invalid money text")
    except Exception:  # noqa: BLE001
        check(f"invalid {text!r} (wrong exception type)", False)

for text in ["١٢", "５", "१.२३"]:
    try:
        parse_money(text)
        check(f"ascii {text!r}", False)
    except ValueError:
        check(f"ascii {text!r}", True)

check("type", type(parse_money("7")) is int and type(parse_money("(1.50)")) is int)

FORMAT = {
    -100000000: "-" + D + "1,000,000.00", 99: D + "0.99", -1: "-" + D + "0.01",
    123456789012: D + "1,234,567,890.12", 10: D + "0.10", -100: "-" + D + "1.00",
    0: D + "0.00", 123456: D + "1,234.56",
}
for cents, want in FORMAT.items():
    check(f"format {cents}", format_cents(cents) == want)

check("roundtrip", all(parse_money(format_cents(n)) == n for n in range(-25000, 25001, 7)))
print("FAILURES", failures)
```

## 5. Test quality

Read `tests/unit/test_money.py`.

- The seven tests named in the spec exist with exactly those names, and there are no others.
- `test_parse_money_valid` is parametrized over all 15 rows of the spec's R2 table, with the exact expected integers.
- `test_parse_money_invalid` is parametrized over all 22 inputs of R3 and uses `pytest.raises(ValueError)`, not `pytest.raises(Exception)`.
- `test_parse_money_error_does_not_echo_input` compares the message with `==`.
- `test_format_cents` covers all 7 rows of R7; `test_round_trip` covers the 9 values of R8.
- Expected values are written as integer literals. No expected value is computed by calling the function under test, and no test contains a float literal used as money (`12.34` appears only inside strings).
- No `skip`, `xfail`, `assert True`, or `# pragma: no cover` in the test file or in `money.py`.

## 6. Project rules that apply to this phase

- **No float for money.** `git grep -n -E "float|round\(| / |/ 100" -- src/finances/domain/money.py` returns no matches.
- **`domain` imports nothing from the project.** `git grep -n -E "^(from|import) " -- src/finances/domain` shows only `decimal` and `re`.
- **No logging of amounts.** `git grep -n -E "logging|print\(" -- src/finances/domain` returns no matches.
- **Input never echoed in errors.** Every `raise` in `money.py` is `ValueError("invalid money text")` with a constant string: no f-string, and no exception chaining that carries the input.
- **Synthetic data only.** The test file contains amounts only: no merchant names, account numbers, or personal names.

## 7. Progress log

`docs/progress.md` ends with an entry headed `## Phase 2b: Money helpers (YYYY-MM-DD)`. Any deviation it lists must not change a signature, the pattern, the error message, or the file list. Earlier entries are unchanged.

## Verdict

`PASS`, or `FAIL` followed by one line per finding in this form:

`<requirement id or section> | <file>:<line> | expected <...> | found <...>`
