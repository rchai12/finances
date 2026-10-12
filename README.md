# Finances

Finances is a local personal-finance tool for one household. It is structured to import bank and card statements, summarize spending, and expose the results to a local AI agent through an MCP server. Its only outbound connection is to the bank-data aggregator, and raw financial files stay on this machine. This version provides configuration, redacting logs, and the `fin` command.

Run every command below as its own step. Do not rely on activating the virtual environment: a new shell does not keep that change, and `python` is not on `PATH` until the environment's interpreter is named explicitly.

## Setup (macOS, zsh)

```zsh
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

## Setup (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
```

Copy `.env.example` to `.env` if you want to override settings. Do not commit `.env` or anything under `data/`.

## Checks (macOS, zsh)

```zsh
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m pytest
.venv/bin/fin --version
.venv/bin/fin doctor
```

## Checks (Windows PowerShell)

```powershell
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m ruff format --check .
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\fin --version
.\.venv\Scripts\fin doctor
```
