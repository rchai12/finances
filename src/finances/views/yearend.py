"""The year report as a heading."""

from finances.analysis.yearend import YearReport


def year_heading(report: YearReport) -> str:
    return f"Year {report.year}, from {report.start.isoformat()} to {report.end.isoformat()}."
