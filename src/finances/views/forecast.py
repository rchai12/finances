"""A per-account forecast as plain text."""

from dataclasses import dataclass

from finances.analysis.forecast import AccountForecast, ForecastReport
from finances.domain.money import format_cents


@dataclass(frozen=True)
class ForecastRow:
    account: str
    balance: str
    as_of: str
    expected_in: str
    expected_out: str
    end: str
    lowest: str
    lowest_on: str


@dataclass(frozen=True)
class StepRow:
    date: str
    merchant: str
    amount: str
    balance: str


def forecast_rows(report: ForecastReport) -> list[ForecastRow]:
    return [
        ForecastRow(
            account=item.account,
            balance=format_cents(item.balance_cents),
            as_of=item.balance_day.isoformat(),
            expected_in=format_cents(item.walk.in_cents),
            expected_out=format_cents(item.walk.out_cents),
            end=format_cents(item.walk.end_cents),
            lowest=format_cents(item.walk.lowest_cents),
            lowest_on=item.walk.lowest_day.isoformat(),
        )
        for item in report.accounts
    ]


def forecast_heading(report: ForecastReport) -> str:
    return f"Forecast from {report.start.isoformat()} to {report.end.isoformat()}."


def no_balance_line(report: ForecastReport) -> str | None:
    if not report.no_balance:
        return None
    return f"No balance yet: {', '.join(report.no_balance)}."


def account_heading(report: ForecastReport) -> str:
    name = report.accounts[0].account
    return f"Forecast for {name} from {report.start.isoformat()} to {report.end.isoformat()}."


def starting_line(forecast: AccountForecast) -> str:
    return (
        f"Starting balance: {format_cents(forecast.balance_cents)} "
        f"(as of {forecast.balance_day.isoformat()})."
    )


def step_rows(forecast: AccountForecast) -> list[StepRow]:
    return [
        StepRow(
            date=step.item.day.isoformat(),
            merchant=step.item.merchant,
            amount=format_cents(step.item.amount_cents),
            balance=format_cents(step.balance_cents),
        )
        for step in forecast.walk.steps
    ]


def lowest_line(forecast: AccountForecast) -> str:
    return (
        f"Lowest: {format_cents(forecast.walk.lowest_cents)} "
        f"on {forecast.walk.lowest_day.isoformat()}."
    )
