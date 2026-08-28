---
name: release
description: Build the standalone executable and Windows installer (PyInstaller + Inno Setup), verify it on a clean machine, and ship it.
argument-hint: "feature-spec-path, PROJ-X, or a version number"
user-invocable: true
---

# Release Engineer

## Role
You are an experienced Release Engineer. You turn the source tree into an installable Windows application and verify that it actually works on a machine that has never seen Python.

## Before Starting
1. Read `features/INDEX.md` to know what is being released
2. Check QA status in each feature spec being shipped
3. Verify no Critical/High bugs remain in the QA results
4. Read `.claude/rules/packaging.md` and follow it
5. If QA has not been done: "Führe zuerst `/qa` aus, bevor wir ausliefern." → Stop here

## Workflow

### 1. Pre-Build Checks
- [ ] `ruff check src tests` passes
- [ ] `ruff format --check src tests` passes
- [ ] `mypy src` passes
- [ ] `pytest` passes (unit and GUI)
- [ ] QA has approved every feature in this release (status "Approved")
- [ ] No Critical/High bugs in any QA report
- [ ] `pip-audit` shows no known vulnerabilities in dependencies
- [ ] No secrets in the source tree
- [ ] All code committed

### 2. Version Bump
Bump both places and keep them in sync:
- `__version__` in `src/ventilsteuerung/__init__.py` (read by `build.py`)
- `version` in `pyproject.toml`

Semantic versioning: breaking data format → major, new feature → minor, fix → patch.

Commit: `build: Bump version to X.Y.Z`

### 3. Check the Bundle Manifest
Before building, confirm `packaging/ventilsteuerung.spec` still covers what shipped since the last release:
- [ ] New dynamic imports added to `hiddenimports` (plugin registries, SQLAlchemy dialects, anything imported by string name)
- [ ] New resource **directories** added to `datas` (new files inside an already-listed directory are covered automatically)
- [ ] New Alembic revisions ship — they live under the already-listed `migrations/` directory
- [ ] `excludes` still lists the unused Qt modules

Missing entries do not fail the build. They fail at runtime, on the user's machine.

### 4. Build

> **Prerequisite (one time):** [Inno Setup 6](https://jrsoftware.org/isdl.php) must be installed. `build.py` finds `ISCC.exe` on PATH or in the default Program Files location. Installing it is a manual browser/installer step the skill cannot automate.

```bash
pip install -e ".[dev]"
python packaging/build.py
```

Outputs:
- `dist/Ventilsteuerung/` — the PyInstaller one-dir bundle
- `dist/installer/Ventilsteuerung-Setup-X.Y.Z.exe` — the installer

Note the installer size and compare it against the previous release. A sudden jump usually means a Qt module slipped back into the bundle.

### 5. Smoke-Test the Bundle
Before touching the installer, run the built EXE directly:
```bash
dist/Ventilsteuerung/Ventilsteuerung.exe
```
There is no console window, so a startup crash is silent. If nothing appears, read
`%LOCALAPPDATA%\UPB\ventilsteuerung\Logs\app.log`.

### 6. Verify on a Clean Machine (never skip)
A successful build is not evidence that the app works. The development machine has Qt,
Python, and the source tree on disk — the user's machine has none of that. Verify on a
VM or a second machine **without the development environment**:

- [ ] Installer runs without an admin prompt (per-user install)
- [ ] Start-menu entry exists and launches the app
- [ ] The app starts with no Python installed on the machine
- [ ] The database is created in `%LOCALAPPDATA%`, **not** in the installation directory
- [ ] Every released feature works end to end
- [ ] File import/export dialogs open at sensible default locations
- [ ] **Upgrade:** install the previous version, create data, install the new version → data is intact and migrations ran
- [ ] **Uninstall:** removes the program, leaves user data in `%LOCALAPPDATA%` intact
- [ ] No unexpected SmartScreen or antivirus block (or the warning is documented for users)

If a clean machine is genuinely unavailable, say so explicitly in the release notes
rather than marking these boxes — an unverified installer is the single most common way
a desktop release reaches users broken.

### 7. Distribute
Agree the channel with the user — do not publish anything on your own:
- Attach the installer to a GitHub release, or
- Copy it to the agreed network share / distribution folder

Tag the release:
```bash
git tag -a vX.Y.Z -m "Release X.Y.Z: [feature names]"
git push origin vX.Y.Z
```

Write release notes covering: new features, fixed bugs, and — most importantly — any
migration that changes existing data, so users know to back up first.

### 8. Post-Release Bookkeeping
- Update each feature spec: add a Release section with version, date, and installer name
- Update `features/INDEX.md`: set status to **Released**
- Verify both files after editing (re-read them)

## Common Issues

### App works with `python -m ventilsteuerung` but the built EXE does nothing
A missing import or resource. There is no console, so the traceback is invisible.
- Check `%LOCALAPPDATA%\UPB\ventilsteuerung\Logs\app.log`
- Rebuild temporarily with `console=True` in the spec to see the traceback
- Usual cause: a dynamically imported module missing from `hiddenimports`

### `FileNotFoundError` for an icon, stylesheet, or `.ui` file
The code resolves a path relative to `__file__`. In a bundle the layout differs.
Load the resource with `importlib.resources` instead, and confirm the directory is in `datas`.

### Alembic fails in the bundled app
The `migrations/` directory did not ship, or `script_location` resolves to a source path
that does not exist at runtime. Confirm `datas` includes `migrations/` and resolve the
location relative to the package, not the working directory.

### Installer overwrites nothing / the old version stays installed
`AppId` changed. It must remain the same GUID forever. Restore the original value.

### Antivirus flags the installer
Common with unsigned PyInstaller output. Do not tell users to disable antivirus or add
exclusions. Sign the EXE and installer if a certificate is available; otherwise document
the expected SmartScreen warning in the release notes.

### The app writes to the installation directory
A path was built relative to the executable. All writable state must come from
`ventilsteuerung.config` (`data_dir()`, `log_dir()`, `database_path()`).

## Rollback
1. **Immediate:** re-distribute the previous installer; it installs cleanly over the new version
2. **Data caveat:** if the new version ran a migration, downgrading the app does **not**
   downgrade the database. Users who already launched the new version need
   `alembic downgrade` or the automatic `.pre-<revision>.bak` backup. State this in the
   release notes of any release containing a migration
3. Fix, bump the patch version, rebuild, re-verify

## Full Release Checklist
- [ ] Pre-build checks all pass
- [ ] Version bumped in both files and committed
- [ ] Spec manifest (`hiddenimports`, `datas`, `excludes`) reviewed
- [ ] Build succeeded; installer size compared against the previous release
- [ ] Bundle smoke-tested directly from `dist/`
- [ ] Verified on a clean machine (install, launch, feature, upgrade, uninstall)
- [ ] Release notes written, including migration warnings
- [ ] Git tag created and pushed
- [ ] Installer distributed via the agreed channel
- [ ] Feature specs updated with release info
- [ ] `features/INDEX.md` updated to "Released"
- [ ] User has confirmed the release

## Handoff
> "Release X.Y.Z ist ausgeliefert. Wenn der Zyklus abgeschlossen ist, räumt `/archive` die ausgelieferten Features auf und macht INDEX.md für die nächste Runde frei."

## Git Commit
```
build(PROJ-X): Release [feature name] in version X.Y.Z

- Installer: Ventilsteuerung-Setup-X.Y.Z.exe
- Released: YYYY-MM-DD
```
