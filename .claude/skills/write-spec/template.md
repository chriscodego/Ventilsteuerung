# PROJ-X: Feature Name

## Status: Planned
**Created:** YYYY-MM-DD
**Last Updated:** YYYY-MM-DD

## Dependencies
- None

## User Stories
- Als [Nutzertyp] möchte ich [Aktion], um [Ziel] zu erreichen

## Placement
<!-- Where this feature lives in the application. -->
- **Ort:** _Hauptfenster-Tab / eigenes Fenster / modaler Dialog / Seitenpanel_
- **Aufruf über:** _Menüeintrag, Toolbar-Button, Kontextmenü, Tastenkürzel_
- **Modal:** _ja / nein_

## Out of Scope
<!-- What this feature explicitly does NOT cover. Critical for developer handoffs. -->
- _Beispiel: Bulk-Export (verschoben auf P1 — PROJ-X)_
- _Beispiel: Undo/Redo (eigenes Feature)_

## Acceptance Criteria

**Format:** Angenommen [Vorbedingung] / Wenn [Aktion] / Dann [Ergebnis]

- [ ] Angenommen [Vorbedingung], wenn [Aktion], dann [Ergebnis]
- [ ] Angenommen [Vorbedingung], wenn [Aktion], dann [Ergebnis]

## Edge Cases
- Was passiert, wenn ...?
- Wie behandeln wir ...?

## Desktop Behaviour
<!-- Fill in every row that applies; delete rows that genuinely do not. -->
| Aspekt | Verhalten |
|--------|-----------|
| Lang laufende Operation | _Dauer, Fortschrittsanzeige, abbrechbar ja/nein, App bleibt bedienbar ja/nein_ |
| Speichern | _explizit über Button / sofort beim Ändern_ |
| Ungespeicherte Änderungen | _Nachfrage beim Schließen / verwerfen / automatisch speichern_ |
| Persistenz über Neustart | _welche Daten und Einstellungen überleben den Neustart_ |
| Tastaturbedienung | _benötigte Shortcuts, komplette Bedienung ohne Maus möglich?_ |
| Dateien | _Formate, Encoding, Standardordner des Dateidialogs_ |
| Datenmenge | _erwartete Anzahl Datensätze, Verhalten beim Zehnfachen_ |
| Destruktive Aktionen | _Bestätigungsdialog, Undo möglich?_ |

## Technical Requirements (optional)
- Performance: _z. B. Liste mit 10.000 Einträgen öffnet in < 500 ms_
- Datenmenge: _erwartetes Maximum_
- Plattform: _Windows 10/11 (x64)_

## Open Questions
<!-- Unresolved questions from the spec interview. Close them in /refine when answered. -->
- [ ] Frage 1

## Decision Log
<!-- Record of conscious decisions made and why. Added to by /write-spec and /architecture. -->

### Product Decisions
<!-- Added by /write-spec -->
| Entscheidung | Begründung | Datum |
|--------------|------------|-------|
| _Beispiel: Kein Undo im MVP_ | _Aufwand steht im MVP nicht im Verhältnis; Löschen ist bestätigungspflichtig_ | YYYY-MM-DD |

### Technical Decisions
<!-- Added by /architecture -->
| Entscheidung | Begründung | Datum |
|--------------|------------|-------|
| _Beispiel: QTableView mit eigenem Model statt QTableWidget_ | _Datenmenge über 10.000 Zeilen; QTableWidget skaliert nicht_ | YYYY-MM-DD |

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /architecture_

## QA Test Results
_To be added by /qa_

## Release
_To be added by /release_
