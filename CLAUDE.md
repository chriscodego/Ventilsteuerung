# Ventilsteuerung

> A standalone Python desktop application, built with an AI-powered development workflow
> using specialized skills for Requirements, Architecture, UI, Domain/Data, QA, and Release.

## What this is
A **standalone desktop program** — installed via a Windows installer, runs offline, no
browser and no server. Not a web app: never introduce React, Next.js, Tailwind, REST
route handlers, `localStorage`, Supabase, or Vercel into this project.

## Tech Stack

- **Language:** Python 3.11+
- **GUI:** PySide6 (Qt 6) — native desktop widgets
- **Persistence:** SQLite via SQLAlchemy 2.0, migrations with Alembic
- **Config/validation:** Pydantic + pydantic-settings
- **Paths:** platformdirs (user data directory, never next to the executable)
- **Packaging:** PyInstaller (one-dir bundle) + Inno Setup (Windows installer)
- **Tests:** pytest, pytest-qt
- **Quality:** ruff (lint + format), mypy (strict)

## Project Structure

```
src/ventilsteuerung/
  __main__.py       Entry point (python -m ventilsteuerung)
  app.py            QApplication bootstrap
  config.py         Settings and user data/log/database paths
  logging_setup.py  Rotating file log
  ui/               PySide6 windows, dialogs, widgets   → calls core/services
    widgets/        Reusable composed widgets
    resources/      Icons, .qss stylesheets, .ui files
  core/             Domain models, services, rules      → imports NO Qt
    services/       Use-case orchestration
  data/             Engine, session, repositories       → imports NO Qt
    repositories/   All queries live here
  migrations/       Alembic revisions
packaging/          PyInstaller spec, Inno Setup script, build.py
tests/
  unit/             Fast, Qt-free tests of core/ and data/
  gui/              pytest-qt tests, marked @pytest.mark.gui
features/           Feature specifications (PROJ-X-name.md)
  INDEX.md          Feature status overview
  archive/          Specs of released features
firmware/           MicroPython firmware (e.g. Raspberry Pi Pico), if the project uses one
docs/
  PRD.md            Product Requirements Document
  configuration.md  Environment variables and file locations
  migration-history.md  What each shipped migration did to user data
  hardware/         Wiring diagram and hardware documentation, if the project uses hardware
```

## Layer Architecture (MANDATORY)
`core/` and `data/` must stay importable and testable **without a QApplication**. The UI
never opens a database session or builds SQL — it calls a service. A service never
touches a widget. If you are writing `from PySide6...` inside `core/` or `data/`, the
logic is in the wrong layer.

## Development Workflow

1. `/init` — Initialize the project: PRD + feature map (run once at the start)
2. `/write-spec` — Create a full feature spec for one feature
3. `/architecture` — Design the technical approach (PM-friendly, no code)
4. `/core` — Build models, migrations, repositories, services
5. `/ui` — Build the PySide6 interface
6. `/qa` — Test against acceptance criteria + security audit
7. `/release` — Build bundle and installer, verify on a clean machine
8. `/archive` — Archive released specs, reset INDEX.md for the next cycle

`/autonom` runs steps 3–6 for all planned features autonomously, asking only about
material decisions. `/refine PROJ-X` revisits an existing spec at any point.

**Ordering rule for steps 4 and 5:** if the feature introduces new tables or non-trivial
domain logic, run `/core` first so the UI builds against a real service. If it only
presents existing data, `/ui` first is fine.

## Feature Tracking

All features tracked in `features/INDEX.md`. Every skill reads it at start and updates it
when done. Feature specs live in `features/PROJ-X-name.md`; released specs move to
`features/archive/`.

## Key Conventions

- **Feature IDs:** PROJ-1, PROJ-2, ... (sequential)
- **Commits:** `feat(PROJ-X): description`, `fix(PROJ-X): description`, `build(PROJ-X): ...`
- **Single Responsibility:** One feature per spec file
- **Qt widgets first:** never hand-roll a button, table, dialog, or file picker
- **Never block the GUI thread:** anything over ~100 ms goes to `QThreadPool`
- **Every schema change gets an Alembic revision** with a working `downgrade()`
- **User data lives in the user data directory**, never next to the executable
- **Human-in-the-loop:** all workflows have user approval checkpoints
- **Language:** code, docstrings, and commits in English; UI strings and acceptance
  criteria in German with real umlauts (ä/ö/ü/ß)
- **Tests:** unit tests in `tests/unit/`, GUI tests in `tests/gui/`

## Build & Test Commands

```bash
pip install -e ".[dev]"            # Install with dev dependencies
python -m ventilsteuerung      # Run the app

ruff check src tests               # Lint
ruff format src tests              # Format
mypy src                           # Type check (strict)
pytest                             # All tests
pytest tests/unit                  # Fast, Qt-free tests
pytest -m gui                      # GUI tests (headless)

alembic revision --autogenerate -m "..."   # New migration
alembic upgrade head                       # Apply migrations

python packaging/build.py          # Bundle + Windows installer
```

All four quality gates (ruff check, ruff format --check, mypy, pytest) must pass before
any feature counts as done.

## Product Context

@docs/PRD.md

## Feature Overview

@features/INDEX.md
