# General Project Rules

## What this project is
A **standalone desktop application** written in Python:
- **UI:** PySide6 (Qt 6) — native desktop windows, no browser, no web server
- **Domain/data:** SQLAlchemy 2.0 ORM + SQLite, migrations via Alembic
- **Distribution:** PyInstaller bundle wrapped in an Inno Setup installer (`.exe`)
- **Runs offline.** There is no server, no API to call, no cloud dependency.

Never introduce web-app patterns here: no React/Next.js, no Tailwind, no REST route
handlers, no `localStorage`, no Supabase, no Vercel. If a task seems to need one of
these, it is the wrong task for this project — ask the user.

## New Project Detection (MANDATORY)
Before starting ANY work, check if the project has been initialized:
1. Read `docs/PRD.md` — if it still contains placeholder text like "_Describe what you are building_", the project is NOT initialized
2. Read `features/INDEX.md` — if the features table is empty, no features have been defined

**If the project is not initialized:**
- Do NOT write any code or create any modules
- Do NOT skip ahead to implementation
- Instead, tell the user: "This project hasn't been set up yet. Let's start by defining what you want to build. Run `/init` with a description of your idea (e.g. `/init Ich will eine App zur Auswertung von Messreihen bauen`)."
- If the user already described their idea in the current message, run `/init` automatically with their description

**If the project is initialized but the user requests a feature not yet in INDEX.md:**
- Guide them to run `/write-spec` first to create the feature spec before any implementation

## Layer Architecture (MANDATORY)
```
src/ventilsteuerung/
  ui/       PySide6 windows, widgets, view models   → may import core, never data directly
  core/     domain models, services, business rules → imports NO Qt, ever
  data/     engine, session, repositories           → imports NO Qt, ever
```
- `core/` and `data/` must stay importable and testable without a `QApplication`.
- The UI never builds SQL or opens a session; it calls a service in `core/services/`.
- A service never touches a widget; it returns plain data or domain objects.
- If you find yourself writing `from PySide6...` inside `core/` or `data/`, stop — the
  logic belongs in `ui/`, or the dependency is inverted.

## Feature Tracking
- All features are tracked in `features/INDEX.md` — read it before starting any work
- Feature specs live in `features/PROJ-X-feature-name.md`
- Feature IDs are sequential: check INDEX.md for the next available number
- One feature per spec file (Single Responsibility)
- Never combine multiple independent functionalities in one spec

## Git Conventions
- Commit format: `type(PROJ-X): description`
- Types: feat, fix, refactor, test, docs, build, chore
- Check existing features before creating new ones: `ls features/ | grep PROJ-`
- Check existing UI modules before building: `git ls-files src/ventilsteuerung/ui/`
- Check existing services before building: `git ls-files src/ventilsteuerung/core/`

## Human-in-the-Loop
- Always ask for user approval before finalizing deliverables
- Present options using clear choices rather than open-ended questions
- Never proceed to the next workflow phase without user confirmation

## Status Updates (MANDATORY - Write-Then-Verify)
After completing work on any feature, you MUST update tracking files. Follow this exact sequence:

1. **Read** the feature spec (`features/PROJ-X-*.md`) and `features/INDEX.md` BEFORE editing
2. **Write** your changes using the Edit tool — do NOT just describe what you would write
3. **Re-read** the file AFTER editing to verify the changes are actually present
4. **If changes are missing**, repeat step 2 — never claim updates were made without verifying

**What to update in the feature spec:**
- Status field in the header (Planned → In Progress → In Review → Released)
- Implementation notes: what was built, what changed, any deviations from the original spec
- Bug fixes or design changes discovered during implementation

**What to update in `features/INDEX.md`:**
- Feature status column must match the feature spec header
- Valid statuses: Roadmap → Planned → Architected → In Progress → In Review → Approved → Released
  - **Roadmap**: after `/init` — feature identified, no spec file yet
  - **Planned**: after `/write-spec`
  - **Architected**: after `/architecture`
  - **In Progress**: after `/ui` or `/core` starts
  - **In Review**: after `/qa` starts
  - **Approved**: after `/qa` passes (no critical/high bugs)
  - **Released**: after `/release`

**NEVER do this:**
- Do NOT say "I've updated the feature spec" without actually calling the Edit tool
- Do NOT summarize changes in chat as a substitute for writing them to the file
- Do NOT skip updates because "it's obvious" or "minor"

## Quality Gates (run before claiming any implementation is done)
```bash
ruff check src tests          # lint
ruff format --check src tests # formatting
mypy src                      # type checking (strict)
pytest                        # tests
```
All four must pass. A feature is not "done" while any of them fails.

## File Handling
- ALWAYS read a file before modifying it — never assume contents from memory
- After context compaction, re-read files before continuing work
- When unsure about current project state, read `features/INDEX.md` first
- Run `git diff` to verify what has already been changed in this session
- Never guess at import paths, class names, or signal names — verify by reading

## Language
- Code, identifiers, docstrings, and commit messages: **English**
- User-facing UI strings and acceptance criteria: **German**
- Use real UTF-8 umlauts (ä/ö/ü/ß), never ae/oe/ue transliterations
- Talk to the user in German

## Handoffs Between Skills
- After completing a skill, suggest the next skill to the user
- Format: "Next step: Run `/skillname` to [action]"
- Handoffs are always user-initiated, never automatic
