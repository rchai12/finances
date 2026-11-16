# Verify Phase 47f: MCP account ownership from analysis

Spec: docs/phases/phase-47f-mcp-account-ownership.md.
Read AGENTS.md and docs/phase-conventions.md; independently verify and write only
`docs/reviews/phase-47f-mcp-account-ownership.md`.

One data field and one thin tool adapter; given seven cases and an exact removal
of three obsolete import-inventory names. No new MCP field, permission or tool.

## Starting baseline

Confirm 47e PASS at 4564 and approved commit f689774. Confirm finalized planning
spec/guide match committed HEAD, actual implementation/progress exist, and isolated
source import provenance. Read status/diff before writing report. Missing build
is a baseline blocker, not a functional FAIL. Preserve unrelated editor settings;
compare reviewed source/tests with delivered bytes before transporting verdict.

## 1. Gates

Run all four spec acceptance steps exactly in order, beginning
`.venv/bin/python scripts/check.py --first core,mcp,web,cli --workers 4`.
Require at least 4571 full-suite passes plus coder cases, clean section table,
mandatory critical gates and All checks passed. Immediately require listings.py
100% line/branch coverage before any other coverage producer; then seven given
passes and scope/given equality. A serial override needs a recorded resource
reason. Resolve known localhost restrictions through execution permission; report
actual outcomes and never weaken tests. No real samples or account access.

## 2. Scope

Only six spec paths plus this report. Earlier tests change only by the exact given
inventory diff. No critical analysis.people edits, person-validation relaxation,
repository, view, template, schema, dependency or other-tool changes. Tool's three
obsolete repository imports disappear; existing capability inventories remain.

## 3. Requirement checklist

| Id | Deciding evidence |
|---|---|
| R1 | test_existing_two_argument_listing_defaults_to_nonjoint; field appended with default False, frozen dataclass and original fields retained. |
| R2 | Four test_analysis_keeps_display_and_joint_distinct cases plus real migrated matrix: presence/None/id decide joint, collision stays sole, repository loaders once each, no alias query. |
| R3 | Two test_mcp_serializes_shared_listing_only cases assert entire literal JSON and loader/session/flag arguments; old loaders unused. Public in-memory MCP matrix verifies actual tool execution. |
| R4 | Complete active/closed/empty results, CLI/web display assertions, schema/signature/description pins and read-only session evidence. No inferred jointness from text. |
| R5 | Given bytes and exact earlier-test diff; full regression and source inspection preserve boundaries and no duplicated ownership loading. |

Require a named test for every Tests to write bullet. Public MCP integration must
exercise real DB ownership data; mocked unit serialization alone is insufficient.
The collision is intentionally a synthetic loader seam because Joint is reserved;
never demand changing validation to create that name through normal APIs.

## 4. Probe

None. Literal JSON unit matrix, real migrated ownership and public MCP/display
compatibility add independent evidence. No search gate is specified.

## 5. Scratch-only spot checks

Mutate only a disposable copy of reviewed source/tests, verify import provenance
and discard each mutation afterward. Never edit reviewed code. Given ids below
start tests/unit/test_account_listing_ownership.py::.

| Exact mutation | Given test/input | Correct | Broken |
|---|---|---|---|
| account_listing: derive joint from owner == JOINT | test_analysis_keeps_display_and_joint_distinct[name-collision], person id points to name Joint | joint False | True |
| account_listing: derive joint from owners.get(id) is None without membership | test_analysis_keeps_display_and_joint_distinct[unassigned], missing key | False | True |
| tool list_accounts: output item.owner even for a joint row | test_mcp_serializes_shared_listing_only[active], explicit joint True and display Joint | JSON owner null | Joint |
| tool list_accounts: omit include_inactive forwarding | test_mcp_serializes_shared_listing_only[all], loader spy and True | keyword True forwarded | spy call assertion fails |

Trace each through actual final code. Collision row has a real person id so no
other ownership rule can make it joint; unassigned lacks the key altogether.
The joint serializer row deliberately carries its display string, isolating
serialization from loader correctness. The flag test asserts arguments even
though its mocked rows are the same under both flag values.

## 6. Reasonable variations and exclusions

Private names and local comprehensions are coder-owned. Computing display
attribution from the one raw ownership map in analysis is intentional: retaining
load_attribution and querying owners again violates the single-load contract.
Keep analysis.people unchanged. Module-local account_listing lookup is required
for the given tool seam. Do not request spending/transfer cleanup or MCP splitting.

## 7. Progress and verdict

Use standard header/finding format. Distinguish baseline, environment, spec/test
and implementation defects. Record fresh gates, section table/final ten lines,
scope/diff equality, matrix coverage, spot outcomes and accurate progress entry.
On FAIL send requirement, observation and required result; do not repair code.
No commit, push or next-phase implementation.
