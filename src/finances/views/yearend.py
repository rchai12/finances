"""The year report as a heading and a page."""

from finances.analysis.yearend import YearReport
from finances.views.spending import line_rows, summary_lines


def year_heading(report: YearReport) -> str:
    return f"Year {report.year}, from {report.start.isoformat()} to {report.end.isoformat()}."


def year_page(report: YearReport) -> dict[str, object]:
    return {
        "heading": year_heading(report),
        "start": report.start.isoformat(),
        "end": report.end.isoformat(),
        "previous": None if report.year == 1 else report.year - 1,
        "next": None if report.year == 9999 else report.year + 1,
        "sections": [
            ("By group", "group", line_rows(report.groups), "No spending."),
            ("By category", "category", line_rows(report.categories), "No spending."),
            (
                "Tax-relevant",
                "category",
                line_rows(report.tax),
                "No tax-relevant categories.",
            ),
        ],
        "summary": summary_lines(report.summary),
    }
