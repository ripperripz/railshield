# ADR 0001: bounded discrete model and operational UI

Accepted: 2026-09-06.

Use a fresh modular scaffold informed by the official FastAPI full-stack template, rather than copying the whole template's account/auth features and unrelated CRUD. Use SQLAlchemy/Alembic and a database-backed worker queue to keep the runtime small and inspectable. No existing SIH26027 solution is copied.

Choose a time-indexed CP-SAT model because exact multi-department occupation union and compatibility are directly expressible and independently verifiable. Bound input/model sizes and expose timeouts. Continuous interval scheduling with flexible possession grouping may scale better later, but requires a more complex union formulation. Preserve the pure domain boundary for that migration.

Use React/Vite/TanStack Query and Cytoscape. The custom timeline maps the domain's 15-minute half-open slots directly into task lanes, train exclusions and recovery locks, with an accessible register alongside it. Frappe Gantt was evaluated as an upstream option but is not installed: task dependencies alone do not supply these possession-specific lanes and semantics. No shadcn registry source is vendored.

21st catalog metadata searches surfaced Dashboard Sidebar, Advanced Stats and Chrono Board. They informed category selection only; component code was not retrieved or copied. The implemented direction is a light operational canvas, dark navigation, teal verified planning and distinct department colors. Fonts are bundled locally. Local 21st review reported informational color-token findings; local source owns the token definitions. Network colors should continue to follow CSS tokens.

Do not add a public deployment in this build: the requested deliverable is the repository. Container publishing and live infrastructure/data connections require explicit deployment context.
