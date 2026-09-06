# Third-party software and references

Dependencies are installed through `backend/uv.lock` and `frontend/package-lock.json`; upstream source is not vendored. No existing SIH26027 solution was copied. This inventory covers the important direct dependencies, tools and reference repositories, not a replacement for a full transitive SBOM.

| Dependency / repository | Role | License |
|---|---|---|
| [google/or-tools](https://github.com/google/or-tools) | CP-SAT scheduling | Apache-2.0 |
| [fastapi/fastapi](https://github.com/fastapi/fastapi) | API | MIT |
| [encode/uvicorn](https://github.com/encode/uvicorn) | ASGI server | BSD-3-Clause |
| [pydantic/pydantic](https://github.com/pydantic/pydantic), pydantic-settings | Validated contracts/configuration | MIT |
| [sqlalchemy/sqlalchemy](https://github.com/sqlalchemy/sqlalchemy), Alembic | Persistence and migrations | MIT |
| [psycopg/psycopg](https://github.com/psycopg/psycopg) | PostgreSQL driver | LGPL-3.0; binary distributions include additional notices |
| [facebook/react](https://github.com/facebook/react) | Frontend | MIT |
| [vitejs/vite](https://github.com/vitejs/vite) | Build/dev tooling | MIT |
| [TanStack/query](https://github.com/TanStack/query) | Server state and polling | MIT |
| [cytoscape/cytoscape.js](https://github.com/cytoscape/cytoscape.js) | Topology visualization | MIT |
| [lucide-icons/lucide](https://github.com/lucide-icons/lucide) | Icons | ISC |
| [HypothesisWorks/hypothesis](https://github.com/HypothesisWorks/hypothesis) | Property-based tests | MPL-2.0 |
| [pytest-dev/pytest](https://github.com/pytest-dev/pytest), httpx | Tests | MIT / BSD-3-Clause |
| [dequelabs/axe-core](https://github.com/dequelabs/axe-core) | Local browser accessibility checks | MPL-2.0 |
| [microsoft/playwright](https://github.com/microsoft/playwright) | Browser tests | Apache-2.0 |
| [astral-sh/uv](https://github.com/astral-sh/uv), Ruff | Python tooling | MIT OR Apache-2.0 |
| [python/mypy](https://github.com/python/mypy) | Python type checking | MIT |
| TypeScript, ESLint, typescript-eslint, Prettier | Frontend checks | Apache-2.0 / MIT |
| [fontsource/fontsource](https://github.com/fontsource/fontsource) | Locally bundled DM Sans and Manrope fonts | Fonts: SIL OFL-1.1; packaging: MIT |
| [postgres/postgres](https://github.com/postgres/postgres) | Production database | PostgreSQL License |
| Nginx | Static serving / API proxy | BSD-2-Clause |

## Architectural references

- [Official OR-Tools job shop guide](https://developers.google.com/optimization/scheduling/job_shop): precedence and no-overlap scheduling primitives.
- [Official flexible job shop example](https://github.com/google/or-tools/blob/stable/examples/python/flexible_job_shop_sat.py): alternative task/presence modeling reference.
- [FastAPI full-stack template](https://github.com/fastapi/full-stack-fastapi-template): MIT-licensed reference for FastAPI/React/PostgreSQL/Docker/CI architecture; not copied wholesale.
- [Frappe Gantt](https://github.com/frappe/gantt): MIT-licensed evaluated option, not installed.
- [21st Dashboard Sidebar catalog](https://21st.dev/@arunjdass/components/dashboard-sidebar): metadata inspiration only; no component source copied.

The original SIH government page was not retrievable during initial research. Requirements are grounded in the user's linked conversation and explicitly preserved design goals, not represented as a verified verbatim SIH specification.

Before distributing a release, generate a transitive SBOM, preserve package-provided LICENSE/NOTICE files, and review container image notices (including Python, Node.js, OS packages and psycopg binary dependencies). Lockfiles record exact dependency resolutions; container tags should be replaced with reviewed digests for release.
