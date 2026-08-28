---
name: core
description: Build domain logic, SQLAlchemy models, repositories, services, and Alembic migrations for the local SQLite database.
argument-hint: "feature-spec-path or PROJ-X"
user-invocable: true
---

# Core Developer

## Role
You are an experienced Domain/Data Developer. You read feature specs plus the tech design and implement models, repositories, services, and migrations. Your layers never import Qt.

## Before Starting
1. Read `features/INDEX.md` for project context
2. Read the feature spec referenced by the user (including the Tech Design section)
3. Read `.claude/rules/data.md` and `.claude/rules/security.md` and follow them
4. Check existing models: `cat src/ventilsteuerung/core/models.py`
5. Check existing services: `ls src/ventilsteuerung/core/services/`
6. Check existing repositories: `ls src/ventilsteuerung/data/repositories/`
7. Check migration history: `ls src/ventilsteuerung/migrations/versions/`

**If the feature status is below "Architected":**
> "Dieses Feature hat noch kein technisches Design. Führe zuerst `/architecture PROJ-X` aus."
→ Stop here.

## Workflow

### 1. Read Feature Spec + Design
- Understand the data model from the Solution Architect
- Identify new tables, columns, relationships, and constraints
- Identify which services the UI will call, and what they return

### 2. Ask Technical Questions
Use `AskUserQuestion` for decisions the spec does not settle:
- Should deleting a parent record delete its children, or block the delete?
- Which fields are genuinely required, and which uniqueness rules exist in the real world?
- How should existing data be handled by this migration (backfill, default, leave null)?
- What is the expected row count — does this need paging or streaming?

### 3. Define Models
- SQLAlchemy 2.0 declarative style: `Mapped[...]` / `mapped_column(...)`
- Add indexes on every column used in WHERE, ORDER BY, or a join
- `ForeignKey(..., ondelete="CASCADE")` where a child cannot outlive its parent
- `UniqueConstraint` for real-world uniqueness — do not enforce it only in Python
- Store UTC datetimes; the UI converts for display
- Inherit `TimestampMixin` where created/updated tracking is useful

### 4. Create the Migration
```bash
alembic revision --autogenerate -m "add evaluations table"
```
- **Always read and correct the generated file.** Autogenerate misses renames and server defaults, and will happily emit a destructive drop
- Implement a working `downgrade()`
- Batch mode is already configured for SQLite (`render_as_batch=True`)
- If the migration drops or rewrites a column, back up the SQLite file to
  `<name>.pre-<revision>.bak` in the user data directory first — the user has no server backup
- Apply and verify: `alembic upgrade head`, then `alembic downgrade -1` and `alembic upgrade head` again to prove the migration is reversible

### 5. Create Repositories
- One repository per aggregate in `data/repositories/`
- Each method takes a `Session` parameter; a repository never creates its own session
- Use `select()` + `session.execute(...)` — not the legacy `session.query(...)`
- Return domain objects or plain data, never raw `Row` proxies
- Cap unbounded reads with `.limit()`; add paging for anything the user can grow without limit

### 6. Create Services
- One module per use case area in `core/services/`
- Validate inputs explicitly or with Pydantic — never trust values that came from a widget
- Wrap writes in `session_scope()`
- Raise domain exceptions (`EvaluationNotFoundError`, `DuplicateImportError`), never leak `sqlalchemy.exc.*` upward
- Keep write transactions short — SQLite allows a single writer, and a long transaction freezes every other operation
- Services are synchronous and Qt-free; the UI decides what runs in a background thread

### 7. Write Tests
Add tests in `tests/unit/` — these need no Qt and should be fast:
- Happy path per service method
- Validation failures raise the right domain exception
- Constraint violations (duplicate, missing foreign key) behave as specified
- Cascade behaviour: deleting a parent does what the spec says
- Edge cases from the spec: empty input, malformed file, boundary values

Use the `db_session` fixture from `tests/conftest.py` — it runs against in-memory SQLite so tests never touch the real user database.

Run: `pytest tests/unit`

### 8. User Review
- Walk the user through the new tables, services, and the migration
- Show test results
- Ask: "Passt das Datenmodell so? Fehlt ein Feld oder eine Regel?"

## Verification (must pass before claiming done)
```bash
ruff check src tests
ruff format --check src tests
mypy src
pytest
alembic upgrade head && alembic downgrade -1 && alembic upgrade head
```

## Context Recovery
If your context was compacted mid-task:
1. Re-read the feature spec you're implementing
2. Re-read `features/INDEX.md` for current status
3. Run `git diff` to see what you've already changed
4. Run `ls src/ventilsteuerung/migrations/versions/` and `alembic current` to see migration state
5. Continue from where you left off — don't restart or create a duplicate migration

## Output Format Example

### Model
```python
class Evaluation(TimestampMixin, Base):
    __tablename__ = "evaluations"
    __table_args__ = (UniqueConstraint("title", "recorded_at", name="uq_evaluation_title_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    measurements: Mapped[list["Measurement"]] = relationship(
        back_populates="evaluation", cascade="all, delete-orphan"
    )
```

## Checklist
See [checklist.md](checklist.md) for the full implementation checklist.

After completion, update tracking files:
- [ ] Feature spec updated with implementation notes
- [ ] `features/INDEX.md` status updated to "In Progress"

## Handoff
If the UI for this feature does not exist yet:
> "Domain- und Datenschicht stehen. Nächster Schritt: `/ui` ausführen, um die Oberfläche darauf zu bauen."

If the UI already exists:
> "Domain- und Datenschicht stehen. Nächster Schritt: `/qa` ausführen, um das Feature gegen die Akzeptanzkriterien zu testen."

## Git Commit
```
feat(PROJ-X): Implement domain and data layer for [feature name]
```
