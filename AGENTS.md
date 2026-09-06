# RailShield repository guidance

- Preserve the pure domain/optimization boundary: no HTTP or database imports in optimization.
- Never mark a plan verified without the independent checker. Required constraints and locks must not be silently relaxed.
- Keep dataset and plan snapshots immutable. Recovery and stress must use the effective parent dataset.
- Use half-open 15-minute slots with an aware epoch. Document any new railway assumptions explicitly.
- Do not copy other SIH26027 submissions. Install dependencies and record major licenses in THIRD_PARTY.md.
- Keep synthetic examples clearly labeled; report measured metrics and solver status, never invented improvements.
- Run `make check`, relevant pytest tests and the real browser workflow for UI/API integration changes. Stop local dev services before E2E to avoid multiple SQLite workers.
- PostgreSQL production migrations use Alembic. SQLite schema creation is development-only.
