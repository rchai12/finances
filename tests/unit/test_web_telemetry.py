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
