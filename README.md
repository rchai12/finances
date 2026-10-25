# Finances

Finances is a local personal-finance tool for one household. It imports bank and card statements as the record and pulls a daily feed from SimpleFIN, categorizes transactions with rules, reports spending, budgets, recurring bills, a forecast, the year's totals, and shared expenses, and gives a local AI agent typed tools through an MCP server on stdio. It runs on one Mac: its only outbound connection is to SimpleFIN, raw financial files stay on the machine, and the web UI listens on 127.0.0.1 only, behind a household password.

It works through the `fin` command, the web UI (`fin web serve`), and the agent's MCP server (`fin mcp serve`). The documents are in [docs/](docs/README.md): how it is built (`architecture.md`), what was built and what comes next (`roadmap.md`), and runbooks for the sync (`sync-setup.md`), backups (`backups.md`), and remote access (`remote-access.md`).

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

## First use (macOS, zsh)

```zsh
.venv/bin/fin db upgrade
.venv/bin/fin web password
.venv/bin/fin web serve
```

Then open http://127.0.0.1:8765 and log in. `fin --help` lists every command.

## Checks (macOS, zsh)

The one command that runs every check (lint, format, tests, coverage of the critical modules):

```zsh
.venv/bin/python scripts/check.py
```

Or one at a time:

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
