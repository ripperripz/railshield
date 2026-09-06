# Build verification — 2026-09-06

## Executed successfully

- Backend: **27 tests passed** on Python 3.13.7. Includes 25 Hypothesis-generated examples within the property test, plus the stateless hosted planning flow and hosted resource limits. The opt-in PostgreSQL test skips without its explicit test URL.
- PostgreSQL 17: initial Alembic migration applied, `alembic check` reported no drift, and the separate concurrent-claim/expired-lease test passed (**1 test**).
- Ruff lint and formatting, mypy over all 15 application modules: passed.
- ESLint, strict TypeScript compilation and Vite production build: passed. Cytoscape is loaded as a separate chunk; fonts are local assets.
- Playwright Chromium: **2 tests passed**. The main test imports JSON, allocates monthly work, generates a verified plan, runs 20 stress scenarios, recovers, exports and opens history. The second tests mobile navigation and page width.
- The same two Playwright tests passed with `VITE_SERVERLESS=true`, exercising browser-local history and the stateless Vercel endpoints.
- Axe WCAG 2 A/AA automated scan on the populated desktop command center: **zero violations after contrast fixes**. This is an automated page scan, not a full accessibility certification.
- npm installation audit: zero reported vulnerabilities for the resolved dependency tree at build time.
- Compose and GitHub Actions YAML parsed successfully.
- Local 21st review completed with informational hardcoded-color findings; topology colors now read shared CSS tokens. A separate request for network-escalated review was denied because of possible private-source upload, and was not retried. Local browser, lint and accessibility checks were used.

## Measured benchmark

`datasets/benchmark-smoke.json` records a seed-42, 12-task, four-section, seven-day experiment, with a three-second CP-SAT budget per plan:

| Metric | Independent | Coordinated |
|---|---:|---:|
| Tasks scheduled | 12 | 12 |
| Possession minutes | 750 | 555 |
| Solver status | FEASIBLE | FEASIBLE |
| Independent verification | Passed | Passed |

This sample saved 195 possession minutes (26%). Both are feasible incumbents, not proven optima. Results and timings may vary under wall-clock limits. These values are not hardcoded into the UI and are not claims about real railway performance.

## Environment limits and follow-up

Docker is not installed on the build host, so the container images and full Compose boot were **not executed locally**. PostgreSQL was verified directly in an isolated temporary instance. The CI Compose job is configured to build, migrate, start and health-check the full stack, but hosted CI has not run because this repository has not been pushed.

The current FastAPI/Starlette test stack emits two upstream deprecation warnings concerning its HTTPX test client and AnyIO portal alias. Tests pass; no warnings are suppressed.

Real railway connectors, approved operational rules, multi-user authorization, signed approval/publishing, multi-track and multi-section modeling, and large-scale load testing remain pilot/deployment work. Their absence is documented in the model and runbook rather than represented as implemented behavior.

## Visual artifacts

- [Desktop command center](screenshots/command-center.png)
- [Mobile data sources](screenshots/mobile.png)

Browser test artifacts and traces are generated under `frontend/test-results` and `frontend/playwright-report` (ignored by Git). Screenshot copies above are retained for review.
