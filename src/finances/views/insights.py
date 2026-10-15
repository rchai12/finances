"""Findings and merchant stats as plain text."""

from dataclasses import dataclass

from finances.analysis.insights import InsightsReport
from finances.domain.money import format_cents


@dataclass(frozen=True)
class FindingRow:
    severity: str
    type: str
    about: str
    saves: str
    detail: str


@dataclass(frozen=True)
class MerchantRow:
    merchant: str
    visits: str
    spent: str
    average: str
    baseline: str
    change: str
    weekend: str


def _change(cents: int) -> str:
    text = format_cents(cents)
    return f"+{text}" if cents > 0 else text


def insights_heading(report: InsightsReport) -> str:
    return f"Insights for {report.month.isoformat()[:7]}."


def finding_rows(report: InsightsReport) -> list[FindingRow]:
    return [
        FindingRow(
            severity=finding.severity,
            type=finding.type,
            about=finding.subject,
            saves=format_cents(finding.savings_cents),
            detail=finding.detail,
        )
        for finding in report.findings
    ]


def findings_summary(report: InsightsReport) -> str:
    savings = sum(finding.savings_cents for finding in report.findings)
    return f"Findings: {len(report.findings)}. Could save up to {format_cents(savings)} a month."


def merchant_rows(report: InsightsReport) -> list[MerchantRow]:
    return [
        MerchantRow(
            merchant=stat.merchant,
            visits=str(stat.visits),
            spent=format_cents(stat.spent_cents),
            average=format_cents(stat.average_cents),
            baseline=format_cents(stat.baseline_cents),
            change=_change(stat.change_cents),
            weekend=str(stat.weekend_visits),
        )
        for stat in report.merchants
    ]
