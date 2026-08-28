---
paths:
  - "src/ventilsteuerung/ui/**"
  - "src/ventilsteuerung/app.py"
---

# UI Development Rules (PySide6 / Qt 6)

## Qt Widgets First (MANDATORY)
Qt ships a large widget set. Before writing a custom widget, check whether Qt already
has it. NEVER hand-roll: buttons, text inputs, combo boxes, checkboxes, radio buttons,
sliders, spin boxes, progress bars, tables, trees, lists, tabs, splitters, toolbars,
menus, status bars, dialogs, file/color/font pickers, message boxes.

| Need | Use |
|------|-----|
| Button | `QPushButton`, `QToolButton` |
| Text input | `QLineEdit`, `QPlainTextEdit`, `QTextEdit` |
| Numbers | `QSpinBox`, `QDoubleSpinBox` |
| Choice | `QComboBox`, `QRadioButton`, `QCheckBox` |
| Tabular data | `QTableView` + `QAbstractTableModel` |
| Hierarchy | `QTreeView` + a model |
| Modal input | `QDialog`, `QDialogButtonBox` |
| Messages | `QMessageBox` |
| File choice | `QFileDialog` |
| Long task feedback | `QProgressDialog`, `QProgressBar` |

Custom widgets are ONLY for project-specific compositions built from Qt primitives.

## Import Pattern
```python
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import QMainWindow, QPushButton, QVBoxLayout, QWidget
```
Import from the specific submodule — never `from PySide6.QtWidgets import *`.

## Layouts, not fixed coordinates
- Always use `QVBoxLayout` / `QHBoxLayout` / `QGridLayout` / `QFormLayout`
- NEVER position widgets with `setGeometry()` or `move()` — it breaks on DPI scaling,
  font-size changes, and window resizing
- Use `addStretch()` and size policies to control how space is distributed
- Set `setMinimumSize()` on windows so layouts cannot be squeezed into nonsense

## Model/View for collections
Any list or table with more than a handful of rows uses Model/View:
- Subclass `QAbstractTableModel` / `QAbstractListModel`
- Never populate a `QTableWidget` row by row from a large dataset
- Sorting and filtering go through `QSortFilterProxyModel`, not manual re-population

## Never block the event loop (CRITICAL)
Any operation that can take more than ~100 ms — file I/O, large queries, parsing,
computation — must NOT run on the GUI thread. The window freezes and Windows shows
"Not responding".

Use `QThreadPool` + `QRunnable`, or a `QThread` with a worker object, and report
results back via signals:
```python
class Worker(QRunnable):
    class Signals(QObject):
        finished = Signal(object)
        failed = Signal(str)
```
- NEVER touch a widget from a worker thread — emit a signal, handle it in a slot
- NEVER use `time.sleep()` on the GUI thread; use `QTimer`

## Signals and Slots
- Declare signals as class attributes: `data_changed = Signal(int, str)`
- Decorate slots with `@Slot(...)` for correct cross-thread queuing
- Connect with the new-style syntax: `button.clicked.connect(self.on_clicked)`
- Disconnect long-lived connections when a widget is destroyed to avoid dangling calls

## Required states for every screen
Same discipline as any app — a view must handle all four:
- **Loading** — `QProgressBar` / busy cursor / disabled controls while work runs
- **Error** — a `QMessageBox` or inline error label with a message the user can act on
- **Empty** — a placeholder explaining what to do, not a blank table
- **Populated** — the normal case

## Styling
- Prefer Qt's native platform style — it makes the app look like a real desktop app
- For deviations use **QSS stylesheets** in `ui/resources/`, applied centrally
- NEVER scatter `setStyleSheet()` calls across individual widgets
- Use `QPalette` for theme-level colors so light/dark mode both work
- Do not hardcode pixel font sizes; derive from `QApplication.font()`

## Resources
- Icons, `.ui` files, and `.qss` live in `src/ventilsteuerung/ui/resources/`
- Load them via `importlib.resources`, not with paths relative to `__file__` — the
  PyInstaller bundle has a different layout at runtime

## Accessibility & usability
- Set `setAccessibleName()` on non-obvious controls
- Give every action a keyboard path: `setShortcut()`, mnemonics (`&Speichern`)
- Tab order must be sensible — `setTabOrder()` where the default is wrong
- Confirm destructive actions with `QMessageBox.question()` before executing

## User-facing text
- All strings the user sees are **German**, with real umlauts
- Wrap them in `self.tr("...")` so translation stays possible later
- Error messages say what happened AND what the user can do about it

## What NOT to do here
- No business logic in widget classes — call a service from `core/services/`
- No database sessions or SQL in `ui/` — repositories are reached through services
- No `print()` — use `logging.getLogger(__name__)`
