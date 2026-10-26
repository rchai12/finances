# Phase 43: telemetry off

## Goal

`AGENTS.md` privacy rule 1: no telemetry. FastAPI 0.143 builds OpenTelemetry into every app, and FastAPI and the MCP SDK both depend on the OpenTelemetry API. Today nothing can leave the Mac: the API alone records nothing, no OpenTelemetry SDK or exporter is installed, and FastAPI's automatic setup runs only when `FASTAPI_OTEL_AUTO_CONFIGURE=true` is set. A later dependency or a stray environment variable could change that. With the owner's choices (2026-10-25):

- the web app is created with FastAPI's tracing, metrics, logs, and automatic setup all off, so an SDK appearing later still exports nothing from it, whatever the environment says;
- a test fails the check if an OpenTelemetry SDK, exporter, or instrumentation package is ever installed.

## Read first

- `docs/phase-conventions.md` (everything this spec does not repeat)
- `AGENTS.md` (privacy rule 1), `src/finances/web/app.py` (`create_app`)

## Starting state

N is `4160` when Phase 42 is the last phase built. **Sections: web.** `create_app` builds `FastAPI(docs_url=None, redoc_url=None, openapi_url=None)`. Installed: `fastapi` 0.143.1 and `opentelemetry-api` (needed by `fastapi` and `mcp`); no `opentelemetry-sdk`, exporter, or instrumentation. No migration.

## Scope

| Path | What changes |
|---|---|
| `src/finances/web/app.py` | `create_app` passes the telemetry setting (R1) |
| `tests/unit/test_web_telemetry.py` | new: given |
| `docs/progress.md` | one new entry |

## Out of scope

- Removing `opentelemetry-api` (FastAPI and the MCP SDK need it); any change to the MCP server (its spans go to the API, which records nothing without an SDK, and the guard test covers an SDK appearing); a `fin doctor` check; pinning versions.

## Dependencies

None new.

## Design

```python
TELEMETRY_OFF = {"tracing": False, "metrics": False, "logs": False, "auto_configure": False}
api = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, telemetry=TELEMETRY_OFF)
```

`TELEMETRY_OFF` is a module constant of `web/app.py`. FastAPI merges an explicit setting over its defaults, so `auto_configure` stays false even when `FASTAPI_OTEL_AUTO_CONFIGURE=true` is set.

## Requirements

- **R1.** `create_app` creates its FastAPI app with `telemetry=TELEMETRY_OFF` as designed.
- **R2.** The given test passes: the guard (no SDK, exporter, or instrumentation installed) passes today and must keep passing.

## Given tests

3 tests in one file. Do not change them. One (`test_no_telemetry_sdk_or_exporter_is_installed`) is a guard that passes today.

`tests/unit/test_web_telemetry.py`

```python
import importlib.metadata
import importlib.util

import pytest
from fastapi import FastAPI

from finances.web import app as web_app

OFF = {"tracing": False, "metrics": False, "logs": False, "auto_configure": False}
FORBIDDEN = ("opentelemetry-sdk", "opentelemetry-exporter", "opentelemetry-instrumentation")


def inner_app() -> FastAPI:
    found = web_app.create_app(8765)
    while not isinstance(found, FastAPI):
        found = found.app
    return found


def test_the_web_app_turns_fastapis_telemetry_off() -> None:
    config = inner_app()._telemetry
    assert {key: config[key] for key in OFF} == OFF


def test_the_environment_cannot_turn_it_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FASTAPI_OTEL_AUTO_CONFIGURE", "true")
    config = inner_app()._telemetry
    assert {key: config[key] for key in OFF} == OFF


def test_no_telemetry_sdk_or_exporter_is_installed() -> None:
    names = sorted(
        {
            (distribution.metadata["Name"] or "").lower()
            for distribution in importlib.metadata.distributions()
        }
    )
    assert [name for name in names if name.startswith(FORBIDDEN)] == []
    assert importlib.util.find_spec("opentelemetry.sdk") is None
```

## Tests to write

None beyond the given file.

## Rules for this phase

- Install nothing; remove nothing.
- Earlier tests stay unchanged.

## Acceptance

The standard table of `docs/phase-conventions.md`, with:

- the check: `.venv/bin/python scripts/check.py --first web`;
- the given test file above, 3 tests; at least N + 3 passed in all;
- `git diff --stat HEAD -- tests` prints nothing (the new file is untracked);
- the coverage command: `.venv/bin/python -m coverage report --include="*/finances/web/app.py" --fail-under=100`.

## Report

As in `docs/phase-conventions.md`, headed `## Phase 43: telemetry off (YYYY-MM-DD)`.
