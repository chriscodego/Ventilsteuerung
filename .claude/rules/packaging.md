---
paths:
  - "packaging/**"
  - "pyproject.toml"
  - "*.spec"
---

# Packaging & Distribution Rules (PyInstaller + Inno Setup)

## Shape of a release
1. `pyinstaller packaging/ventilsteuerung.spec` → `dist/Ventilsteuerung/`
2. `iscc packaging/installer.iss` → `dist/installer/Ventilsteuerung-Setup-X.Y.Z.exe`

`python packaging/build.py` runs both.

## One-dir, not one-file
Keep `COLLECT` (one-dir). One-file bundles unpack into a temp directory on every
launch — slow startup, antivirus false positives, and broken relative paths. The
installer hides the directory from the user anyway.

## Frozen-app pitfalls (check every one before shipping)
- **`__file__` is not the source path.** In a bundle, resources live under
  `sys._MEIPASS`. Load bundled files with `importlib.resources`, never by walking up
  from `__file__`.
- **Dynamic imports are invisible to PyInstaller.** Anything imported via
  `importlib.import_module`, a plugin registry, or a string name must be listed in
  `hiddenimports` in the spec — including SQLAlchemy dialects.
- **Data files must be declared.** New `ui/resources/` content and new Alembic
  revisions only ship if the `datas` list covers them. Adding a directory once covers
  new files inside it; adding a new top-level directory does not.
- **`multiprocessing` needs `freeze_support()`** as the first statement in the entry
  point, or the app spawns copies of itself.
- **No console window** (`console=False`), so `print()` and unhandled tracebacks go
  nowhere. Log to file, and install a global exception hook that shows a `QMessageBox`.

## Size discipline
Keep the `excludes` list in the spec current — unused Qt modules (QtWebEngine, Quick,
Qml, Multimedia, 3D) are the bulk of the download. Do not add UPX; it saves little and
raises antivirus flags.

## Installer rules
- **Per-user install by default** (`PrivilegesRequired=lowest`) — no admin prompt
- `AppId` is a stable GUID. **Never change it** — a new GUID makes Windows treat the
  next release as a separate product and leaves the old one installed
- Provide Start-menu entry and uninstaller; desktop icon is opt-in
- **Uninstall keeps user data.** `%LOCALAPPDATA%` is out of the `[Files]` scope by
  design; removing the database must be an explicit opt-in choice, never the default
- German and English language files stay available

## Upgrades
- Installing over an existing version must not lose the user's database
- The app runs migrations on startup, so a new version must be able to migrate the
  **oldest supported** database schema, not just the previous one
- Test upgrade explicitly: install old version → create data → install new → verify

## Versioning
Bump in two places, kept in sync:
- `__version__` in `src/ventilsteuerung/__init__.py` (read by `build.py`)
- `version` in `pyproject.toml`

Semantic versioning: breaking data format → major, new feature → minor, fix → patch.

## Release verification (never skip)
The build succeeding is not evidence the app works. On a machine or VM **without the
development environment**:
- [ ] Installer runs without an admin prompt
- [ ] App launches from the Start menu
- [ ] The database is created in `%LOCALAPPDATA%`, not in the install directory
- [ ] The released feature works end to end
- [ ] Upgrade over the previous version preserves existing data
- [ ] Uninstall removes the program and leaves user data intact
