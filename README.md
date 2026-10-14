# JHive

JHive is a Python-first trading intelligence project for historical research, explainable forecasts, deterministic risk controls, backtesting, and paper trading. All execution remains simulated or demo-only during development. Forecasts are uncertain and are not guarantees of profit.

## Status

Milestone 1 foundation is in progress. See [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md) for verified progress and limitations.

## Requirements

Python 3.10 or newer is required. This Mac now has a project-compatible Python 3.10.22 build at `~/.local/opt/python-3.10.22/bin/python3.10`. Python 3.10.22 is the final 3.10 release and is end of life; plan to move to a supported Python series after validating dependency compatibility. Git is required for version control.

## Setup

From this inner project directory:

```bash
~/.local/opt/python-3.10.22/bin/python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,data,api,database]'
```

The virtual environment is ignored by Git and must be recreated on another machine. The local Python build is not part of the repository. The default configuration has no broker credentials and cannot submit live-money orders. Keep real secrets in a local `.env` file, which Git ignores. `.env.example` contains placeholders only.

## Layout

- `src/jhive/`: application package
- `tests/`: automated tests
- `data/`: local datasets, excluded from Git by default
- `models/`: local trained artifacts, excluded from Git by default
- `docs/`: development and status documentation

## Git workflow

Review changes with `git status` and `git diff`. Stage only the files you intend to include, run relevant tests, then commit a coherent milestone. Push only after reviewing and approving the commit. GitHub stores committed changes only after a successful push; unsaved and uncommitted local changes are not backed up.

```bash
git status
git diff
git add <reviewed-files>
git commit -m "chore: initialize JHive project"
git push -u origin main
```

Never commit `.env`, credentials, account identifiers, private keys, local databases, or sensitive logs. Do not use force-push or destructive history rewriting.

## Reconnecting the external drive

Reconnect and mount the `Untitled` drive before opening this workspace. Open the inner `JHive` folder, not the outer container. GitHub can restore pushed commits, but uncommitted work may be lost if the drive fails.

## Current runnable entry point

After installing with a supported Python interpreter, run:

```bash
jhive
```

The development startup only logs that live market data and trading are disabled. Market features will be added in later milestones.
