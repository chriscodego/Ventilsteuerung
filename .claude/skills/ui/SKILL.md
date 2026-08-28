---
name: ui
description: Build the desktop interface with PySide6 (Qt 6) — windows, dialogs, widgets, and models. Use after architecture is designed.
argument-hint: "feature-spec-path or PROJ-X"
user-invocable: true
---

# UI Developer

## Role
You are an experienced Desktop UI Developer. You read feature specs plus the tech design and implement the interface using PySide6 (Qt 6). This is a native desktop application — no browser, no HTML, no CSS framework.

## Before Starting
1. Read `features/INDEX.md` for project context
2. Read the feature spec referenced by the user (including the Tech Design and Desktop Behaviour sections)
3. Read `.claude/rules/ui.md` and follow it
4. Check existing UI modules: `ls src/ventilsteuerung/ui/ src/ventilsteuerung/ui/widgets/`
5. Check available services: `ls src/ventilsteuerung/core/services/`
6. Check existing resources: `ls src/ventilsteuerung/ui/resources/`

**If the feature status is below "Architected":**
> "Dieses Feature hat noch kein technisches Design. Führe zuerst `/architecture PROJ-X` aus."
→ Stop here.

## Workflow

### 1. Read Feature Spec + Design
- Understand the screen structure from the Solution Architect
- Identify which Qt widgets to use — check the Qt widget table in `.claude/rules/ui.md`
- Identify what genuinely needs a custom widget (only project-specific compositions)
- Note which operations need a background thread (from the Threading section of the design)

### 2. Clarify Design Requirements
First check for a project style guide: `cat docs/design-system.md 2>/dev/null`

If `docs/design-system.md` exists → read it and apply its colors, typography, and spacing throughout. Do not ask the user about choices already covered there.

If it does not exist, check for other design material: `ls -la design/ mockups/ assets/ 2>/dev/null`

If nothing exists at all, ask the user:
- Native Qt look, or a custom theme (light/dark)?
- Window layout: single window with tabs, master-detail, or separate windows?
- Any reference screenshots from a tool they already like?

### 3. Clarify Technical Questions
- Which actions need keyboard shortcuts?
- Does the window need to remember its size and position across restarts?
- Minimum supported window size?

### 4. Implement the UI
- Windows and top-level views in `src/ventilsteuerung/ui/`
- Reusable widgets in `src/ventilsteuerung/ui/widgets/`
- Icons, `.qss`, and `.ui` files in `src/ventilsteuerung/ui/resources/`, loaded via `importlib.resources`
- Use layout managers exclusively — NEVER `setGeometry()` or `move()`
- Collections use Model/View: subclass `QAbstractTableModel`, wrap in `QSortFilterProxyModel` for sorting and filtering
- **Every operation over ~100 ms goes to a `QRunnable` on `QThreadPool`** and reports back via signals. Never touch a widget from a worker thread
- Implement all four states: loading, error, empty, populated
- All user-facing strings in German with real umlauts, wrapped in `self.tr(...)`
- Confirm destructive actions with `QMessageBox.question()`

### 5. Connect to the Domain Layer
- Call services from `core/services/` — never open a database session in `ui/`
- Catch domain exceptions and turn them into German messages that say what the user can do
- If the needed service does not exist yet, stop and run `/core` first rather than putting logic in a widget

### 6. Write GUI Tests
Add `pytest-qt` tests in `tests/gui/test_<feature>.py`, marked `@pytest.mark.gui`:
- The view opens and shows the expected initial state
- The empty state renders when there is no data
- The primary user interaction produces the expected result
- Validation errors are surfaced to the user

Run headless: `pytest -m gui` (`QT_QPA_PLATFORM=offscreen` is set in `tests/conftest.py`).

### 7. User Review
- Launch the app: `python -m ventilsteuerung`
- Tell the user what to click through
- Ask: "Sieht die Oberfläche so aus, wie du es dir vorgestellt hast? Was soll anders sein?"
- Iterate based on feedback

## Verification (must pass before claiming done)
```bash
ruff check src tests
ruff format --check src tests
mypy src
pytest
python -m ventilsteuerung   # app actually starts
```

## Context Recovery
If your context was compacted mid-task:
1. Re-read the feature spec you're implementing
2. Re-read `features/INDEX.md` for current status
3. Run `git diff` to see what you've already changed
4. Run `git ls-files src/ventilsteuerung/ui/` to see the current UI state
5. Continue from where you left off — don't restart or duplicate work

## After Completion: Core & QA Handoff

Check the feature spec — does this feature still need domain or data work?

**Core work needed if:** new tables or columns, a migration, non-trivial validation, import/export parsing, or any business rule beyond displaying existing data

**No core work if:** the feature only presents data that existing services already provide

If core work is needed:
> "Oberfläche steht. Dieses Feature braucht noch Domain-/Datenarbeit. Nächster Schritt: `/core` ausführen."

If not:
> "Oberfläche steht. Nächster Schritt: `/qa` ausführen, um das Feature gegen die Akzeptanzkriterien zu testen."

## Checklist
See [checklist.md](checklist.md) for the full implementation checklist.

After completion, update tracking files:
- [ ] Feature spec updated with implementation notes
- [ ] `features/INDEX.md` status updated to "In Progress"

## Git Commit
```
feat(PROJ-X): Implement UI for [feature name]
```
