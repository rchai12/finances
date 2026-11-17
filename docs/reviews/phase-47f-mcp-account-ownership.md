# Review: Phase 47f

- Verdict: PASS
- Passed: 4583
- Findings: 0
- Approved deviations: None
- For the architect: None

## Findings

None.

Parts that needed a repair: None.

Built beyond the spec: None.

## Baseline, scope and provenance (2026-11-16)

Reviewed delivery commit `c8f5011038d7a87248921d92b67e75c513832b95` against finalized planning baseline `fb0051452797d1aa1e5653609898ed62e10aa87d`. Predecessor Phase 47e implementation is committed at 0ee3a38 and its PASS review at `f6897745316c5052d4f16dd5ae8234d6d1c390fa`; N = 4564. Phase 47f spec and guide match their committed planning versions. Read project instructions, architecture, conventions, testing strategy, handoff procedure, remediation design section 47f, phase spec/guide, progress, production diff, all new tests and the named existing analysis/people/views/MCP contracts.

Original workspace `/Users/richardxiaohuachai/Desktop/Projects/finances` had empty tracked diff and only unrelated untracked `.vscode/settings.json`. Preserved it. Reviewed in fresh local clone `/var/folders/2d/386g2_8d69915k8_pvkhdq3c0000gn/T/finances-47f-review-_qxkqihz/checkout`, linking the existing venv and excluding only that symlink locally. The clone was clean before gates. Every isolated Python invocation selected clone src via explicit PYTHONPATH; pre-gate import check resolved finances.__file__ inside that clone.

The baseline-to-delivery changed-path set equals exactly the six Scope paths: two production files, two new tests, the supplied existing-test inventory edit and progress. Given file bytes equal the embedded Python block; the entire existing-test diff equals the embedded diff exactly. No other earlier test, fixture, critical attribution module, repository, view, template, person validation, schema, migration, dependency or configuration changed. Independent AST comparison confirms every other MCP tool definition and people_listing/PersonListing remain identical. The only data-contract addition is appended `AccountListing.joint: bool = False`, with frozen semantics and original fields retained.

Before transporting this verdict, all 1,019 tracked original-workspace files still matched the isolated reviewed bytes and their pre-gate SHA-256 manifest (`/tmp/phase47f-review-manifest.json`). Original tracked diff remained empty. This review applies to those exact bytes. Only this report is added to the original repository; unrelated editor work remains untouched.

## Fresh independent acceptance

Ran all four spec acceptance steps sequentially from the isolated root with its existing `.venv/bin/python` and clone PYTHONPATH. Python 3.12.16, pytest 9.1.1, pytest-xdist 3.8.0 and pytest-cov 7.1.0. Four local workers, one coordinated coverage-producing job in the checkout; no delegated agents or concurrent coverage jobs from this review.

Requested permission up front for the established localhost-binding restriction in synthetic transport fixtures. The permitted run succeeded; no failed sandbox attempt occurred in this review. Coder acceptance receipts in progress remain historical evidence, not substitutes for these independent results. No real accounts, database, samples, Keychain or aggregator were accessed; no dependency setup or weakened tests.

| Command | Fresh observation |
|---|---|
| `.venv/bin/python scripts/check.py --first core,mcp,web,cli --workers 4` | exit 0; selected-first `3112 passed in 58.94s`; full `4583 passed in 107.34s (0:01:47)`; no failures, skips, xfails or warnings summary; final `All checks passed.` |
| `.venv/bin/python -m coverage report --include="*/finances/analysis/listings.py" --fail-under=100` | immediately after successful check, exit 0; listings and `TOTAL 25 0 0 0 100%`; no missing locations |
| `.venv/bin/python -m pytest tests/unit/test_account_listing_ownership.py --no-cov` | exit 0; exactly `7 passed in 0.25s` |
| Status/diff/given audit | isolated status and tracked diff clean (delivery committed); exact six-path baseline diff, given bytes/diff identical, no other earlier tests changed |

Overall coverage is 99.98%, above configured 85%; every mandatory critical-module gate passes. No artificial whole-tools.py coverage target was imposed. No search gate or independent probe is specified. Full fresh output retained at `/tmp/phase47f-review-check.log`.

Full-run section table:

```text
Sections:
  migrations    184 passed    0 failed    0 skipped
  scripts       100 passed    0 failed    0 skipped
  web           888 passed    0 failed    0 skipped
  cli           460 passed    0 failed    0 skipped
  mcp           210 passed    0 failed    0 skipped
  parsers       903 passed    0 failed    0 skipped
  sync          284 passed    0 failed    0 skipped
  core         1554 passed    0 failed    0 skipped
```

Last ten check lines:

```text
  core         1554 passed    0 failed    0 skipped
== critical coverage

Summary:
  lint: passed
  format: passed
  tests (core,mcp,web,cli): passed
  tests: passed
  critical coverage: passed
All checks passed.
```

## Requirements and deciding evidence

| Requirement | Tests and inspected behavior |
|---|---|
| R1 | Given `test_existing_two_argument_listing_defaults_to_nonjoint` verifies compatible default, including owner text Joint without joint ownership. `test_real_analysis_and_views_preserve_all_ownership_forms` verifies full dataclass values and frozen-field refusal. Source appends the boolean after owner and retains the frozen decorator. No extra response/view field was introduced. |
| R2 | Four given `test_analysis_keeps_display_and_joint_distinct[unassigned/sole/joint/name-collision]` cases assert exact display/joint values, account identity and each repository loader exactly once. `test_real_analysis_and_views_preserve_all_ownership_forms[False/True]` exercises real migrated records, alphabetical order and closed filtering. `test_empty_and_inactive_only_load_once_without_cardholder_aliases[False/True]` asserts accounts/owners/people once each and no alias/session calls. Source uses map membership and None/id, preserves exact person names/order/flag, removes load_attribution import and does not load aliases. |
| R3 | Both given `test_mcp_serializes_shared_listing_only[active/all]` cases assert entire literal JSON including all keys/types/order, shared loader once with the same session and exact inactive keyword, and zero old-loader/session calls. `test_public_mcp_complete_json_and_order` invokes the actual in-memory server/repositories with omitted/false/true flags. `test_adapter_enters_reading_and_forwards_same_session` checks enter/load/exit sequence and no session operations. Adapter retains reading(), account fields/envelope and only serializes shared rows. |
| R4 | `test_empty_public_mcp`, real analysis/view matrix, complete public MCP matrix and `test_cli_and_web_columns_and_owners_stay_unchanged[False/True]` cover empty results, ownership forms, active/closed filtering and exact established columns/labels. `test_predecessor_signature_and_tool_metadata` pins name, signature, description, full input/output schema and read-only annotations. Existing `test_the_tools_read_through_a_session_that_cannot_write` and tool inventories pass unchanged. |
| R5 | Exact supplied import-inventory diff and given bytes, unchanged other tools/people_listing ASTs, full suite and critical gates. No duplicate ownership loading, critical attribution changes, capability expansion or person-validation relaxation. |

Real integration setup creates valid invented people and unassigned/sole/joint/closed accounts out of alphabetical order using existing public APIs in migrated databases. Calls through the MCP server use the existing in-memory helper, not a socket. Exact expected JSON equality checks rows, key sets, values and ordering rather than counts alone. CLI table and web page assertions retain Joint display and empty unassigned display. Closed filtering is exercised in both modes.

The reserved-name collision deliberately uses a synthetic loader seam with a person id/name Joint, as specified; normal person validation remains unchanged. Jointness is determined from raw ownership membership and None, never by comparing a display name. Read-only enforcement still comes from unchanged reading() -> get_engine(read_only=True); the existing write-refusal test exercises the real protected session. The new seam test additionally proves loading occurs while that context is entered with its exact session.

There are twelve coder cases: two real-analysis/view, three public MCP flag, one empty MCP, two CLI/web, one metadata, one reading/session and two empty/inactive loader cases. Seven given plus twelve coder cases yield 4564 -> 4583. Core adds seven and MCP adds twelve; new files retain existing section assignments without config edits. Assertions validate behavior, exact contracts and query-call counts rather than merely covering lines.

## Fresh scratch-only spot checks

Copied reviewed source/tests/config to a fresh disposable directory outside both checkouts and confirmed finances import provenance inside scratch src. Applied each mutation independently, restored each scratch file before the next and discarded the scratch directory. Reviewed code was never modified. Each named given case ran with `--no-cov` and failed as required:

| Exact mutation | Deciding given case | Fresh broken observation |
|---|---|---|
| derive jointness from display owner == JOINT | `test_analysis_keeps_display_and_joint_distinct[name-collision]` | exit 1; sole id/name Joint incorrectly produces True |
| use owners.get(id) is None without membership | `test_analysis_keeps_display_and_joint_distinct[unassigned]` | exit 1; missing key incorrectly produces True |
| serialize item.owner even for joint row | `test_mcp_serializes_shared_listing_only[active]` | exit 1; literal JSON contains Joint where owner must be null |
| omit include_inactive forwarding | `test_mcp_serializes_shared_listing_only[all]` | exit 1; expected loader keyword True is absent |

Inputs reach the intended ownership/serialization rules without another defense masking the mutations. The forwarding test fails on arguments despite unchanged mocked row data, as intended. No given test or input was changed. Unmodified seven-case gate passes. Logs retained at `/tmp/phase47f-review-spot-{collision,unassigned,owner,forwarding}.log`.

## Progress and result

Progress accurately records appended AccountListing.joint, N/final/given counts, six paths, twelve coder cases, exact inventory migration, single-load behavior and compatibility evidence. Its 94.52s acceptance timing is coder history; this fresh independent full run took 107.34s. No baseline, environment, specification/test or implementation blocker remains.

PASS for the exact commit and reviewed bytes above. Only this report was written in the original repository. No implementation, progress, phase document or unrelated work was changed; no commit, push or later-phase work was performed.
