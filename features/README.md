# Feature Specifications

Dieser Ordner enthält die detaillierten Feature-Specs. Ausgelieferte Specs wandern
über `/archive` nach `features/archive/`.

## Naming Convention
`PROJ-X-feature-name.md`

Beispiele:
- `PROJ-1-datenmodell-persistenz.md`
- `PROJ-2-messreihen-uebersicht.md`
- `PROJ-3-csv-import.md`

## Was gehört in eine Feature Spec?

Die vollständige Vorlage liegt in `.claude/skills/write-spec/template.md`. Kurzfassung:

### 1. User Stories
```markdown
Als [Nutzertyp] möchte ich [Aktion], um [Ziel] zu erreichen
```

### 2. Placement
Wo lebt das Feature — Tab im Hauptfenster, eigener Dialog, Seitenpanel? Modal oder nicht?
Worüber wird es aufgerufen (Menü, Toolbar, Kontextmenü, Tastenkürzel)?

### 3. Acceptance Criteria
Konkret und testbar, im Angenommen/Wenn/Dann-Format:
```markdown
- [ ] Angenommen die Liste ist leer, wenn der Nutzer das Fenster öffnet,
      dann wird ein Hinweistext mit dem Button „Erste Messreihe anlegen" angezeigt
- [ ] Angenommen der Import läuft, wenn der Nutzer auf „Abbrechen" klickt,
      dann wird der Import gestoppt und keine Teildaten bleiben zurück
```

### 4. Desktop Behaviour
Die Tabelle, an der Desktop-Specs sonst scheitern:
- Lang laufende Operationen: Fortschritt, abbrechbar, App bleibt bedienbar?
- Speichern: explizit oder sofort? Was passiert bei ungespeicherten Änderungen?
- Persistenz über Neustart: was überlebt das Schließen?
- Tastaturbedienung, Dateiformate, Datenmenge, destruktive Aktionen

### 5. Edge Cases
```markdown
- Was passiert, wenn die CSV-Datei eine unbekannte Spalte enthält?
- Was passiert, wenn die App mitten im Import abstürzt?
- Was passiert, wenn die Datenbankdatei schreibgeschützt ist?
```

### 6. Tech Design (vom Solution Architect)
Screen-Struktur, Datenmodell in Klartext, Schichtenzuordnung (ui/core/data),
Threading für lange Operationen, neue Abhängigkeiten.

### 7. QA Test Results (vom QA Engineer)
Ergebnisse pro Akzeptanzkriterium, Desktop-Dimensionen (DPI, Fenstergröße, Upgrade,
Erststart), Security-Audit, gefundene Bugs mit Severity. Vorlage:
`.claude/skills/qa/test-template.md`.

### 8. Release (vom Release Engineer)
```markdown
---

## Release

**Status:** Released
**Version:** 1.0.0
**Released:** 2026-08-20
**Installer:** Ventilsteuerung-Setup-1.0.0.exe
**Git Tag:** v1.0.0
**Verifiziert auf sauberer Maschine:** ja
```

## Workflow

1. **`/init`** legt PRD und Feature-Map an
2. **`/write-spec`** schreibt die vollständige Spec
3. **`/architecture`** ergänzt das technische Design
4. **`/core`** baut Modelle, Migrationen, Repositories, Services
5. **`/ui`** baut die PySide6-Oberfläche
6. **`/qa`** testet und trägt die Ergebnisse in die Spec ein
7. **`/release`** baut Bundle und Installer und trägt den Release-Status ein
8. **`/archive`** verschiebt ausgelieferte Specs nach `features/archive/`

`/autonom` fährt die Schritte 3–6 für alle geplanten Features autonom durch und fragt nur
bei wesentlichen Entscheidungen nach. `/refine PROJ-X` überarbeitet eine bestehende Spec.

## Status-Tracking

Der Status steht im Header der Spec und muss mit `features/INDEX.md` übereinstimmen:
```markdown
# PROJ-1: Feature Name

## Status: Planned
**Created:** 2026-08-20
**Last Updated:** 2026-08-20
```

Roadmap → Planned → Architected → In Progress → In Review → Approved → Released

**Git als Single Source of Truth für die Implementierung:**
- `git log --grep="PROJ-1"` zeigt alle Änderungen zu diesem Feature
- Kein separates Changelog nötig

**Was NICHT ins Archiv wandert:**
- Tests in `tests/` — die sind die dauerhafte Regressions-Suite
- `docs/migration-history.md` — Nutzer aktualisieren über beliebig alte Versionen hinweg,
  die Migrationskette muss nachvollziehbar bleiben
