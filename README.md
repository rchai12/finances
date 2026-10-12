# Finances

Finances is a local personal-finance tool for one household. It is structured to import bank and card statements, summarize spending, and expose the results to a local AI agent through an MCP server. Its only outbound connection is to the bank-data aggregator, and raw financial files stay on this machine. This version provides configuration, redacting logs, and the `fin` command.

## Setup (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Copy `.env.example` to `.env` if you want to override settings. Do not commit `.env` or anything under `data/`.

## Checks

```powershell
ruff check .
ruff format --check .
pytest
fin --version
fin doctor
```
