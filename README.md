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

## Local dashboard

Start the local dashboard from the project directory:

```bash
source .venv/bin/activate
jhive-dashboard
```

Then open [http://127.0.0.1:8765](http://127.0.0.1:8765). Stop the server with `Ctrl+C`. In VS Code, you can also run `python -m jhive.web` in the integrated terminal.

The app opens at a local sign-in page. Google and Microsoft OpenID Connect sign-in and email one-time codes can be enabled in the local, ignored `.env` file (copy `.env.example` first). Set the provider client ID and secret, and register `http://127.0.0.1:8765/auth/google/callback` or `http://127.0.0.1:8765/auth/microsoft/callback` with the corresponding identity provider. For email codes, set the SMTP host, sender, and any required login credentials. Restart JHive after editing `.env`; unconfigured options remain unavailable on the sign-in page. Each identity provider must return a verified email address.

The designated super-administrator is `jeffhanns.cilzikmusic@gmail.com`; use **Administrator sign-in** to request a one-time code, then read it in the terminal running JHive. Codes expire after five minutes and are limited to five attempts. Administrator access is passwordless but uses this local terminal code. The server binds to `127.0.0.1` by default. Legacy member accounts and salted password hashes remain stored locally in `~/.jhive/accounts.sqlite3`. Login sessions expire after 12 hours and when the server stops.

The dashboard is currently a paper-account interface preview. Replace its fixed portfolio, watchlist, chart, and strategy figures with account-specific data before using it to guide decisions. No broker integration or order placement is implemented.
