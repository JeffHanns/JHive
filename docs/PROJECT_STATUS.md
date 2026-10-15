# Project status

Last verified: 2026-10-15

## Current release scope

JHive is a local research-interface prototype. The first engine slice is forex, free historical files, and simulated paper research only. There is no live quote feed, broker connection, or order-submission code.

## Built and checked

- Python package and dashboard server, with local account creation, password sign-in, administrator password/code sign-in, and optional OAuth/email integrations that require local provider configuration.
- Dark/light dashboard, profile settings and paper-account presentation. Existing portfolio figures and chart ranges are presentation samples; they are not generated from a live account or verified performance.
- An offline reader for HistData generic ASCII minute bars, including timestamp order, positive-price, finite-number, and OHLC-range validation.
- A deterministic long-only simple moving-average crossover simulation. Signals are based on completed bars, entries and exits fill at the next bar open, costs are configurable in basis points per side, and an open position is marked out at end of data.
- Automated checks for the starter command, research data/simulation, and HTTP account/auth routes. The app supports `JHIVE_DATA_DIR` as an explicit local database-path override for isolated tests and local setups.

## Not built yet

- Reliable market-data download/synchronization, data-source provenance stored alongside datasets, and coverage/gap diagnostics.
- Walk-forward or holdout evaluation, benchmark comparisons, strategy search controls, and robust uncertainty reporting.
- Portfolio-level allocation, currency conversion, leverage/margin, realistic spread/slippage models, and durable paper-account trade records.
- Production deployment, centralized authentication, account recovery, phone/SMS sign-in, configured identity providers, and multi-user data isolation review.
- Live trading. It is outside this release scope.

## Data notes

The initial reader accepts manually downloaded HistData generic ASCII M1 files. The provider says these are free historical files and documents timestamps as EST without daylight-saving adjustment; the reader preserves these as naive source timestamps and does not relabel them UTC. The provider also says it does not warrant the free data. Inspect source and coverage before relying on a result. See [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) and [DATA_AND_RESEARCH.md](DATA_AND_RESEARCH.md).

## Backup and repository status

GitHub `JeffHanns/JHive` is the shared source history. A separate local working copy and dated pre-reconciliation backups are kept under `~/Documents/Codex/JHive-work` and `~/Documents/Codex/JHive-Backups`. GitHub contains only committed and successfully pushed work; local `.env`, account database, virtual environment, and downloaded data are excluded. Keep at least one backup on a different physical device from the project drive.

The project was created on an external volume. If that volume is not mounted or refuses writes, do not assume local edits reached it. Check `git status`, `git log`, and the repository's GitHub commit before continuing.

## Verification

Run the suite from the project root with `python -m pytest`. The last run in this restricted desktop environment reported 10 passed and 6 skipped: local HTTP auth tests are included but skipped because the sandbox denied binding a loopback test server. Run them in a normal local/CI environment to verify those routes. Targeted Ruff checks for the new research module and tests passed; full-project Ruff still reports older findings in `web.py` and `main.py`. Passing code tests does not validate a vendor's prices or establish profitability.
