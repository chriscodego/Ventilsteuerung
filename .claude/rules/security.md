---
paths:
  - "src/ventilsteuerung/**"
  - "packaging/**"
---

# Security Rules (Desktop Application)

The threat model is a desktop app, not a web service. There is no server to attack,
but the app runs with the user's full privileges on their machine and holds their data.

## Secrets
- NEVER commit secrets, API keys, tokens, or credentials
- NEVER embed a secret in the source — a PyInstaller bundle is trivially unpackable
  (`pyinstxtractor`), so anything shipped in the EXE is public
- If credentials are ever needed, store them in the OS credential store via `keyring`,
  never in the SQLite file or a plaintext config
- Runtime configuration comes from `VENTIL_*` environment variables (see
  `ventilsteuerung.config`), documented in `docs/configuration.md`

## Input validation
- Validate every value that crosses a layer boundary, including values from widgets —
  a spin box range is a UX affordance, not a guarantee
- Validate in `core/services/`, not only in the UI
- Bind SQL parameters; never build queries by string interpolation

## Untrusted files
Imported files (CSV, XLSX, JSON, project files) are untrusted input:
- NEVER `pickle.load()`, `eval()`, `exec()`, or `yaml.load()` untrusted data — use
  `yaml.safe_load()` and explicit parsers
- Guard against zip-slip when extracting archives: reject entries whose resolved path
  escapes the target directory
- Cap sizes and row counts before parsing so a malformed file cannot exhaust memory
- Wrap parsing in error handling that shows a German message, not a traceback

## Filesystem
- Write only to the user data directory, the log directory, and paths the user picked
  in a `QFileDialog`
- NEVER write into the installation directory — it is read-only for standard users
- Use `pathlib`, resolve paths, and check that user-supplied paths stay inside the
  intended directory
- Set restrictive permissions on files containing personal data

## Subprocesses
- `subprocess` with a list of arguments, never `shell=True`
- Never pass user-supplied text into a shell string

## Personal data
- Only store what the feature actually needs
- Never log personal data, file contents, or credentials — log IDs and counts
- Uninstall must not silently delete user data; deletion is an explicit opt-in
- If the app exports data, tell the user in the UI what the file will contain

## Dependencies & supply chain
- Pin direct dependencies in `pyproject.toml` with a lower bound and review upgrades
- Run `pip-audit` before a release and fix anything with a known CVE
- Adding a new runtime dependency is an architecture decision — ask the user first

## Distribution
- Do not ship debug builds: `debug=False`, `console=False` in the PyInstaller spec
- Unsigned installers trigger SmartScreen warnings; if the user has a code-signing
  certificate, sign both the EXE and the installer
- Never disable antivirus or advise the user to add exclusions as a "fix"

## Review triggers (require explicit user approval)
- Any change that deletes or rewrites user data
- Any new runtime dependency
- Any migration with a destructive `upgrade()`
- Any code that reaches the network
