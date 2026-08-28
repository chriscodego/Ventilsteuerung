# QA Test Results Template

Add this section to the END of the feature spec `features/PROJ-X-*.md`:

```markdown
---

## QA Test Results

**Tested:** YYYY-MM-DD
**Build:** `python -m ventilsteuerung` (dev) / Installer X.Y.Z
**OS:** Windows 11 (x64)
**Tester:** QA Engineer (AI)

### Automated Suite
| Check | Result |
|-------|--------|
| `ruff check src tests` | Pass / Fail |
| `mypy src` | Pass / Fail |
| `pytest tests/unit` | X passed, Y failed |
| `pytest -m gui` | X passed, Y failed |

### Acceptance Criteria Status

#### AC-1: [Criterion]
- [x] Passed

#### AC-2: [Criterion]
- [ ] BUG: [what went wrong]

### Edge Cases Status

#### EC-1: [Edge Case]
- [x] Handled correctly

#### EC-2: [Edge Case]
- [ ] BUG: [expected vs. actual]

### Desktop Behaviour

| Dimension | Result | Note |
|-----------|--------|------|
| Fenstergröße (Minimum, Maximieren, Wiederherstellen) | Pass / Fail | |
| DPI-Skalierung 100% / 150% / 200% | Pass / Fail | |
| Keine GUI-Blockade bei langen Operationen | Pass / Fail | |
| Fortschrittsanzeige sichtbar | Pass / Fail / n/a | |
| Abbrechen funktioniert | Pass / Fail / n/a | |
| Persistenz über Neustart | Pass / Fail | |
| Frischer Start mit leerer Datenbank | Pass / Fail | |
| Upgrade von Vorversion (Daten erhalten) | Pass / Fail | |
| Bedienung nur mit Tastatur | Pass / Fail | |
| Abbruch mitten im Schreibvorgang | Pass / Fail | |

### Security Audit Results
- [x] Fehlerhafte Importdateien erzeugen eine verständliche Meldung, keinen Traceback
- [x] Kein `pickle` / `eval` / `exec` / `yaml.load` auf Nutzerdaten
- [x] Keine Pfad-Traversierung über Dateiinhalte möglich
- [x] Keine Secrets im Quellcode oder im Bundle
- [x] Keine personenbezogenen Daten im Log
- [x] Schreibzugriffe nur im Benutzerdatenordner und in vom Nutzer gewählten Pfaden
- [x] Kein `shell=True` in Subprozessen
- [ ] BUG: [Security-Befund]

### Bugs Found

#### BUG-1: [Titel]
- **Severity:** Critical | High | Medium | Low
- **Steps to Reproduce:**
  1. [Schritt]
  2. [Schritt]
  3. Erwartet: [was passieren sollte]
  4. Tatsächlich: [was passiert]
- **Log-Auszug:** [relevante Zeilen aus `%LOCALAPPDATA%\...\Logs\app.log`]
- **Screenshot:** [bei visuellen Bugs]
- **Priority:** Vor Release beheben | Nächster Zyklus | Nice to have

### Summary
- **Acceptance Criteria:** X/Y bestanden
- **Bugs Found:** N gesamt (C critical, H high, M medium, L low)
- **Security:** [Pass / Befunde vorhanden]
- **Release Ready:** YES / NO
- **Empfehlung:** [Ausliefern / Erst Bugs beheben]
```
