"""Shared MCP input translation."""

from datetime import date

from mcp.server.mcpserver.exceptions import ToolError

import finances.clock as clock
from finances.domain import periods


def month_start(month: str) -> date:
    try:
        return periods.first_day(month or None, today=clock.today() if not month else date.min)
    except ValueError as error:
        raise ToolError(str(error)) from error
