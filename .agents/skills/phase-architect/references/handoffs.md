# Handoff and correction procedure

Adapted from tasking's phase skills, phase_tools.py lint/stubcheck, and
accept.py, progress.py, check_reports.py, and spot_check.py (read 2026-11-15).
Use this reference for handoff preparation, blocked work, and review reruns.
Paths below are relative to the finances repository root.

## Ready means ready

A request to create a phase spec includes completing its given tests, validation,
scope, acceptance gates, guide, and handoff. Drafting is an intermediate step.
Continue through those steps in the same assignment. Stop only for a concrete
missing decision, contradictory requirement, unavailable resource, or permission
denial. Identify the exact blocker and finish independent work first.

Before declaring a spec ready, check:
- Every named file exists or is explicitly to be created within Scope.
- Each requirement has a given test or a deciding coder-test case.
- Given case counts come from collection; guide test ids actually collect.
- Spec and guide commands, counts, coverage paths, and searches agree.
- Embedded given files match the validated scratch files through gen_spec.py.
- No unfinished placeholders or draft status remain.
- Failures on the predecessor are missing behavior, not broken tests. With a
  names-only stub, a passing test is either a documented guard or weak evidence.
  A failure-injection test uses a distinct exception class: RuntimeError also
  catches NotImplementedError and can accidentally pass against a stub.
- There is a concrete working directory and committed baseline for the coder.

## Establish the baseline before implementation

Record the full baseline commit and run:
`git status --short --untracked-files=all`
`git diff HEAD -- docs/phases/<spec> docs/verification/<guide>`

A tracked spec is not necessarily the finalized spec: the second command must
be empty. Also account for required untracked references, including the audit
and local skills; a clone of HEAD does not contain them.

If unrelated work exists, prepare a fresh isolated clone from the intended
committed baseline before coding. Never stash, reset, delete, or commit unrelated
work to obtain an empty status. If finalized planning docs remain uncommitted,
prepare the concrete planning commit and request authorization only when it has
not already been granted. Do not hand off with a promise to sort it out later.

Link the existing venv, add the venv symlink to the clone's local
.git/info/exclude (a .venv/ ignore may not match a symlink), and set PYTHONPATH to
the clone's src for every Python command. Confirm finances.__file__ is inside
the clone. Do not modify tracked ignore rules for this temporary setup.

For an implementation already mixed with unrelated work:
1. Clone the committed spec baseline into a fresh temporary directory.
2. Copy only explicit phase paths and the authorized report; apply explicit
   deletions too. Reject unexpected paths rather than silently broadening Scope.
3. Compare copied bytes with the original, and record the complete changed-path
   inventory, including untracked files. Inspect overlapping edits in shared
   files such as progress.md; do not assume the whole file belongs to the phase.
4. Verify clone status equals the permitted implementation paths plus report.
   Missing files and extra files both matter.
5. Give the verifier the clone path, baseline, import-path instruction, and
   evidence location. Before copying a verdict back, confirm that the reviewed
   source/tests still equal the original workspace; a verdict on stale bytes
   cannot approve later edits.

Isolation establishes a current reviewable scope. It does not retroactively
claim that the original coder started clean. Describe that history honestly.

## Corrections and reruns

Classify findings as implementation, specification/test, environment, or
baseline/scope. Repair the cause. Do not rewrite functional requirements to
pass incorrect code, and do not turn an independent FAIL into PASS yourself.

A spec correction names exactly which gates are live again and why. A scope-only
reassessment may retain earlier functional evidence only when the owner/guide
allows that limited reassessment and source, tests, dependencies, configuration,
and relevant environment are unchanged. Record the evidence being reused and
its limits. Without that authorization, follow the existing guide's full gates.
An implementation change needs the affected checks and required acceptance.

Sandbox loopback refusal is an environment error. Request the required execution
permission, rerun the failed command, and report both outcomes accurately.
Never weaken a test to avoid an environment restriction.

## Evidence and progress

Capture each command's actual exit code and output. Show a short digest and the
required section table; retain full synthetic-test logs in temporary storage.
Do not pipe through tail without preserving the test command's exit status.
Run coverage-consuming commands immediately after their producer. Never run
coverage-producing test jobs concurrently.

When work is blocked, record a concise
`Stopped: <requirement/command> | <observation> | <what allows completion>`
as the first Follow-ups item in the current phase entry, using the existing
finances format. Preserve earlier entries and avoid duplicate phase headings.
If the current task/scope forbids changing progress, put this in the handoff
instead; do not modify code or progress during verification.

## Tooling compatibility

Tasking's scripts are examples, not installed finances capabilities:
- accept.py imports docket.acceptance and executes commands from Markdown;
  its completion/exit code is not itself a PASS verdict.
- progress.py and check_reports.py import docket.reports and assume tasking's
  exact report layout and committed given-file workflow.
- phase_tools.py lint expects tasking's sections and test catalog format.
- spot_check.py imports docket.spotcheck and mutates the selected working tree;
  finances permits executable mutation checks only in an isolated copy.
- check.py --quiet is a tasking feature; do not advertise it for finances.

Use finances' existing gen_spec.py, code_map.py, phase_status.py and check.py.
Perform the matching readiness checks above directly until a dedicated tooling
change supplies a tested finances equivalent. Port only a demonstrated need,
without importing docket or changing application behavior. Report/schema changes
must be reconciled with phase-conventions.md before making new tools mandatory.
