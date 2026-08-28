---
paths:
  - "src/ventilsteuerung/core/**"
  - "src/ventilsteuerung/data/**"
  - "src/ventilsteuerung/migrations/**"
  - "alembic.ini"
---

# Domain & Data Rules (SQLAlchemy 2.0 / SQLite / Alembic)

## Framework independence (MANDATORY)
`core/` and `data/` must never import Qt. Both layers have to be importable and
fully testable without a `QApplication`. If a function needs a widget, it is in the
wrong layer.

## Where data lives
- The SQLite file lives in the **user data directory**, resolved by
  `ventilsteuerung.config.database_path()` — never next to the executable, never
  in the project directory. The install directory is read-only for a normal user.
- Same for logs (`config.log_dir()`) and any exported files the user did not choose.

## SQLAlchemy 2.0 style
- Declarative models with `Mapped[...]` / `mapped_column(...)` — not the legacy
  `Column(...)` form
- Use `select()` + `session.execute(...)`, not the legacy `session.query(...)`
- Type every model attribute; `mypy --strict` must pass

```python
class Evaluation(TimestampMixin, Base):
    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
```

## Sessions
- Every write goes through `session_scope()` from `data/db.py` — it commits on success
  and rolls back on any exception
- NEVER keep a single long-lived session for the lifetime of the app; a stale session
  holds locks and serves stale data
- One session per use case / user action

## Repositories
- All queries live in `data/repositories/` — one repository per aggregate
- A repository takes a `Session` as a parameter; it never creates one itself
- Repositories return domain objects or plain data, never SQLAlchemy `Row` proxies
  leaked upward

## Services
- `core/services/` orchestrates: validate input → call repositories → apply rules →
  return a result
- Validation uses Pydantic models or explicit checks — never trust widget state
- Raise domain exceptions (`EvaluationNotFoundError`), not `sqlalchemy.exc.*`, upward

## SQLite specifics
- `PRAGMA foreign_keys=ON` and WAL mode are set in `data/db.py` — SQLite has foreign
  keys **off** by default, so never assume constraints are enforced without it
- SQLite has no real `ALTER TABLE`: Alembic must run with `render_as_batch=True`
  (already configured in `migrations/env.py`)
- SQLite has a single writer. Long write transactions block the whole app — keep them
  short, and run them off the GUI thread
- Datetimes are stored without timezone awareness unless you say otherwise — always
  store UTC (`datetime.now(UTC)`) and convert for display in the UI layer

## Indexes & constraints
- Add an index on every column used in `WHERE`, `ORDER BY`, or a join
- Use `ForeignKey(..., ondelete="CASCADE")` where a child cannot outlive its parent
- Add `UniqueConstraint` for real-world uniqueness rules — do not enforce them only in
  Python, concurrent writes will slip through

## Migrations (Alembic)
- **Every schema change gets a migration.** Never edit a model without one
- Generate: `alembic revision --autogenerate -m "add evaluations table"`
- **Always review the generated file** — autogenerate misses renames, server defaults,
  and data changes, and will happily emit a destructive drop
- Every revision implements a working `downgrade()`
- Data migrations (backfills) go in the same revision as the schema change they need
- Apply on startup or via `alembic upgrade head`; the packaged app must migrate an
  existing user database **without losing data**

## Backups before destructive migrations
Any migration that drops or rewrites a column must copy the SQLite file to
`<name>.pre-<revision>.bak` in the user data directory first. Users cannot restore
from a server backup — this file is their only copy.

## What NOT to do here
- No Qt imports
- No `print()` — use `logging.getLogger(__name__)`
- No raw string-interpolated SQL — always bind parameters
- No network calls; this application works offline
