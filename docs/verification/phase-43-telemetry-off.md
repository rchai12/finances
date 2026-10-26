# Verify Phase 43: telemetry off

Spec: `docs/phases/phase-43-telemetry-off.md`. Follow `docs/phase-conventions.md` ("For the verifier") for the procedure and the verdict.

The coder created the web app with FastAPI's telemetry off. One test file was given; its guard checks that no OpenTelemetry SDK, exporter, or instrumentation package is installed.

## 1. Gates

N is `4160` when Phase 42 was the last phase built. Sections: web.

| Command | Expected |
|---|---|
| `.venv/bin/python scripts/check.py --first web` | last line `All checks passed.`; the summary lists `tests (web): passed`; at least N + 3 passed, 0 failed, 0 skipped, 0 xfailed; 0 failed on every line of the `Sections:` table |
| `.venv/bin/python -m pytest tests/unit/test_web_telemetry.py --no-cov` | exactly `3 passed` |
| `.venv/bin/python -m coverage report --include="*/finances/web/app.py" --fail-under=100` | exit 0, `TOTAL` at `100%` |
| `git diff --stat HEAD -- tests` | no output |
| `.venv/bin/python -m pip list` | no name starting `opentelemetry-sdk`, `opentelemetry-exporter`, or `opentelemetry-instrumentation` |

## 2. Scope paths

`git status --short` lists `docs/progress.md`, `src/finances/web/app.py`, and the new test file, which equals the spec's.

## 3. Requirement checklist

| Id | How | Pass when |
|---|---|---|
| R1 | gate 2 (`test_the_web_app_turns_fastapis_telemetry_off`, `test_the_environment_cannot_turn_it_on`); read `create_app` | `telemetry=TELEMETRY_OFF` |
| R2 | gate 2 (`test_no_telemetry_sdk_or_exporter_is_installed`); gate 5 | pass |

## 4. Probe

None.

## 5. The coder's tests and spot checks

The spec asks for no tests beyond the given file.

| Change | Deciding input | Correct | Broken |
|---|---|---|---|
| 1. `create_app`: `auto_configure` left to FastAPI's default | given `test_the_environment_cannot_turn_it_on` (`FASTAPI_OTEL_AUTO_CONFIGURE=true`) | false | true |
| 2. `create_app`: only `tracing` off | given `test_the_web_app_turns_fastapis_telemetry_off` | all four off | metrics and logs on |

## 6. Out of scope

Each must be absent: a package installed or removed; a change to the MCP server; a `fin doctor` check; a version pin.

## 7. Progress log

The entry exists in the form of `docs/phase-conventions.md`, and each deviation it lists is real and justified.
