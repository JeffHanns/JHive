# Development plan

## Milestone 1: project and dashboard foundation

- [x] Set up Python packaging, isolated local environment guidance, secret-safe ignore rules, and GitHub repository.
- [x] Build the local dashboard and account interface prototype.
- [x] Add a safe starter command and smoke test.
- [x] Add an offline forex CSV reader and a first paper-only strategy simulation.
- [x] Document current scope, data limits, and backup locations.

## Milestone 2: research records and verification

- [ ] Add dataset registry: source, instrument, timeframe, download date, timezone convention, checksum, license/terms link, and coverage.
- [ ] Add gap, duplicate, spread, and outlier reports; persist validation summaries with each dataset.
- [ ] Add benchmark strategies, untouched time-based holdout, and walk-forward evaluation.
- [ ] Add explicit assumptions for spread, commission, slippage, rollover, and pip valuation per pair.
- [ ] Connect dashboard sections to persisted research and paper-account records instead of UI sample figures.
- [ ] Expand service/API and browser-level checks, including auth configuration and database migrations.

## Milestone 3: paper research workflow

- [ ] Store strategy definitions, run parameters, dataset checksums, trades, equity, and metrics so each result can be reproduced.
- [ ] Add position sizing, exposure limits, drawdown stops, and portfolio-level currency risk constraints.
- [ ] Add a paper ledger with deterministic event records, restart recovery, and audit export.
- [ ] Review security, access control, backup restore, and multi-user data separation before sharing externally.

## Release boundary

All milestones remain historical research and simulated paper activity. A live feed or broker must not be introduced as a side effect of research work; it requires a separate design, explicit approval, and extensive safety review.
