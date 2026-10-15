# JHive

JHive is a Python-first trading intelligence project for historical research, explainable forecasts, deterministic risk controls, backtesting, and paper trading. All execution remains simulated or demo-only during development. Forecasts are uncertain and are not guarantees of profit.

## Status

The local dashboard foundation and first offline forex research slice are in place. See [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md) for verified progress and limitations, and [docs/DATA_AND_RESEARCH.md](docs/DATA_AND_RESEARCH.md) for the data format and simulation assumptions.

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

The app opens at a local sign-in page. Members can create an account using an email address and password (12 or more characters), then sign in with those credentials. Google OpenID Connect, GitHub OAuth, and Microsoft OpenID Connect can be enabled in the local, ignored `.env` file (copy `.env.example` first). Set the provider client ID and secret, and register the matching callback URL (`http://127.0.0.1:8765/auth/google/callback`, `/auth/github/callback`, or `/auth/microsoft/callback`) with each provider. Email one-time codes require SMTP host, sender, and any required login credentials. Restart JHive after editing `.env`; unconfigured options remain unavailable on the sign-in page. GitHub sign-in requires a verified primary email. Apple sign-in and phone registration are shown as unavailable until Apple identity verification and an SMS provider are configured.

The designated super-administrator is `jeffhanns.cilzikmusic@gmail.com`; administrator sign-in supports a configured password and a one-time code shown in the local JHive server terminal. Codes expire after five minutes and are limited to five attempts. The server binds to `127.0.0.1` by default. Legacy member accounts and salted password hashes remain stored locally in `~/.jhive/accounts.sqlite3`. Login sessions expire after 12 hours and when the server stops.

The dashboard is currently a paper-account interface preview. Its portfolio, watchlist, chart, and strategy figures are sample values and are not loaded from recorded paper trades. No broker integration, live quotes, or order placement is implemented. The offline research module can read manually downloaded HistData generic ASCII M1 CSV files and run a basic long-only SMA crossover simulation. The simulation has configurable flat per-side costs, but lacks a realistic pair-specific spread/slippage model and out-of-sample validation. Treat it as a pipeline prototype, not as a trading recommendation. See [data and research notes](docs/DATA_AND_RESEARCH.md).

Run the current automated checks from the project root:

```bash
python -m pytest
```
