# UI Implementation Checklist

Before marking the UI as complete:

## Qt Widgets
- [ ] Checked whether Qt already provides each widget before writing a custom one
- [ ] No hand-rolled duplicates of Qt primitives (buttons, inputs, tables, dialogs, ...)
- [ ] Collections use Model/View (`QAbstractTableModel` + `QTableView`), not `QTableWidget`
- [ ] Sorting and filtering go through `QSortFilterProxyModel`, not manual re-population

## Existing Code
- [ ] Checked existing UI modules via `git ls-files src/ventilsteuerung/ui/`
- [ ] Reused existing widgets and services where possible

## Layout
- [ ] All positioning done with layout managers — no `setGeometry()` or `move()`
- [ ] `setMinimumSize()` set on windows and dialogs
- [ ] Layout survives resizing to the minimum size and maximizing
- [ ] Tested at 100%, 150%, and 200% DPI scaling — no clipped text

## Responsiveness (CRITICAL)
- [ ] Every operation over ~100 ms runs on `QThreadPool`/`QRunnable`, not the GUI thread
- [ ] Progress is visible for every long operation
- [ ] Long operations can be cancelled where the spec requires it
- [ ] No widget is touched from a worker thread — results arrive via signals
- [ ] No `time.sleep()` on the GUI thread

## States
- [ ] Loading state (progress bar / busy cursor / disabled controls)
- [ ] Error state (actionable German message, not a traceback)
- [ ] Empty state (explains what to do, not a blank table)
- [ ] Populated state

## Layer Discipline
- [ ] No business logic in widget classes — services are called from `core/services/`
- [ ] No database sessions or SQL in `ui/`
- [ ] No `print()` — `logging.getLogger(__name__)` instead

## Styling & Resources
- [ ] Styling via a central QSS stylesheet, not scattered `setStyleSheet()` calls
- [ ] `docs/design-system.md` applied if it exists
- [ ] Resources loaded with `importlib.resources`, never paths relative to `__file__`
- [ ] No hardcoded pixel font sizes

## Usability
- [ ] Every action reachable by keyboard; shortcuts set where the spec asks for them
- [ ] Tab order is sensible
- [ ] `setAccessibleName()` on non-obvious controls
- [ ] Destructive actions confirmed via `QMessageBox.question()`
- [ ] All user-facing strings German with real umlauts, wrapped in `self.tr(...)`

## Verification (run before marking complete)
- [ ] `ruff check src tests` passes
- [ ] `ruff format --check src tests` passes
- [ ] `mypy src` passes
- [ ] `pytest` passes (including `pytest -m gui`)
- [ ] `python -m ventilsteuerung` starts and the feature is reachable
- [ ] All acceptance criteria from the feature spec are addressed in the UI
- [ ] `features/INDEX.md` status updated to "In Progress"

## Completion
- [ ] User has reviewed and approved the UI in the running app
- [ ] Code committed to git
