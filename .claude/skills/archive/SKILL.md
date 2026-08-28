---
name: archive
description: Archive released features, update memory, and reset tracking for the next development cycle. Use after all current features are shipped in an installer.
argument-hint: "optional: specific PROJ-IDs to archive, e.g. PROJ-9 PROJ-10"
user-invocable: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
model: sonnet
---

# Feature Archiver & Context Optimizer

## Role
Du räumst nach einem Feature-Zyklus auf: ausgelieferte Feature-Specs archivieren, das Langzeitgedächtnis aktualisieren, Tracking-Dateien zurücksetzen und den Token-Verbrauch künftiger Gespräche senken.

## Before Starting
1. **Lies [LESSONS.md](LESSONS.md)** — bekannte Fehler und Learnings aus vergangenen Durchläufen anwenden

## When Invoked

### Step 1: Analyze Current State

1. **Lies `features/INDEX.md`** und finde alle Features mit Status **"Released"**
2. **Argumente prüfen** — wenn der Nutzer PROJ-IDs angegeben hat, nur diese archivieren. Sonst ALLE "Released"-Features
3. **Lies den Memory-Index** `MEMORY.md` im Memory-Verzeichnis und prüfe, ob `project_released_features.md` existiert

**Wichtig — nur wirklich ausgelieferte Features archivieren:**
"Released" bedeutet: das Feature ist Teil eines gebauten Installers, der auf einer sauberen Maschine verifiziert wurde. Ein Feature mit Status "Approved" ist getestet, aber noch nicht ausgeliefert — es bleibt in der aktiven Tabelle.

Wenn Features den Status "Approved" haben, aber keinen "Released"-Status, weise darauf hin:
> "PROJ-X ist getestet, aber noch nicht ausgeliefert. Führe zuerst `/release` aus — archiviert wird erst, was tatsächlich beim Nutzer angekommen ist."

Wenn gar nichts zum Archivieren da ist:
> "Keine Features zum Archivieren gefunden. Alle Features in INDEX.md haben noch Status 'Planned', 'In Progress', 'In Review' oder 'Approved'."

### Step 2: Update Long-Term Memory

1. **Lies die bestehende Memory-Datei** `project_released_features.md` (falls vorhanden)
2. **Hänge die neu ausgelieferten Features an die Tabelle an** — bereits archivierte Einträge nicht überschreiben
3. **Aktualisiere das Datum** im Header auf heute
4. **Aktualisiere `MEMORY.md`**, falls die Memory-Datei neu ist

Format der Memory-Datei:
```markdown
---
name: project_released_features
description: Übersicht aller ausgelieferten Features mit Version und Kurzbeschreibung
metadata:
  type: project
---

# Ausgelieferte Features (Stand YYYY-MM-DD)

Alle archivierten Feature-Specs liegen in `features/archive/`.

| ID | Feature | Version | Beschreibung |
|----|---------|---------|--------------|
| PROJ-X | Name | X.Y.Z | Kurzbeschreibung |
```

Die **Version** ist die Spalte, die diesen Eintrag später nützlich macht: bei einem Bugreport aus dem Feld ist die erste Frage immer, welche Version der Nutzer installiert hat und was da drin war.

### Step 3: Migrationen dokumentieren, bevor die Spec verschwindet

Bevor eine Spec ins Archiv wandert: enthielt das Feature eine Alembic-Migration, die bestehende Nutzerdaten verändert hat?

Falls ja, ergänze in `docs/migration-history.md` (anlegen, falls nicht vorhanden) eine Zeile:
```markdown
| Revision | Feature | Version | Was sich an den Nutzerdaten geändert hat |
|----------|---------|---------|------------------------------------------|
| a1b2c3d4 | PROJ-X  | X.Y.Z   | Spalte `notes` hinzugefügt, Bestandsdaten auf NULL |
```

Das ist der Grund, warum diese Datei nicht ins Archiv darf: Nutzer installieren Upgrades über beliebig alte Versionen. Die Migrationskette muss nachvollziehbar bleiben, auch wenn die Feature-Spec längst archiviert ist.

### Step 4: Archive Feature Specs

1. Erstelle `features/archive/`, falls nicht vorhanden
2. Verschiebe die Spec-Dateien der ausgelieferten Features: `features/PROJ-X-*.md` → `features/archive/`
3. Nur die tatsächlich zu archivierenden Features verschieben (per PROJ-ID prüfen)

```bash
mkdir -p features/archive
mv features/PROJ-X-*.md features/archive/
```

**Tests und Code bleiben, wo sie sind.** Archiviert wird ausschließlich die Spec. Die Tests in `tests/` sind die dauerhafte Regressions-Suite und dürfen nie mitverschoben oder gelöscht werden.

### Step 5: Reset INDEX.md

Entferne die archivierten Features aus der aktiven Tabelle, aber lass die Struktur intakt:

```markdown
# Feature Index

> Central tracking for all features. Updated by skills automatically.

## Status Legend
- **Roadmap** - Feature identifiziert, noch keine Spec
- **Planned** - Spec geschrieben
- **Architected** - Technisches Design fertig
- **In Progress** - Wird gebaut
- **In Review** - QA läuft
- **Approved** - QA bestanden, bereit zur Auslieferung
- **Released** - In einem Installer ausgeliefert

## Released (Archived)

PROJ-X bis PROJ-Y sind ausgeliefert (bis Version X.Y.Z). Specs in `features/archive/`.

## Active Features

| ID | Feature | Status | Spec | Created |
|----|---------|--------|------|---------|

<!-- Add features above this line -->

## Next Available ID: PROJ-Z
```

Wichtig: Der Abschnitt "Released (Archived)" muss den **gesamten** archivierten Bereich abbilden, inklusive früher archivierter IDs, und die zuletzt ausgelieferte Version nennen. "Next Available ID" korrekt fortschreiben.

### Step 6: Update PRD Roadmap

Lies `docs/PRD.md` und bring die Roadmap auf den aktuellen Stand:
- Archivierte Features erscheinen als "Released" (Einzeiler, keine ausführliche Tabelle)
- Der Verweis auf `features/INDEX.md` für neue Features bleibt stehen

### Step 7: Summary

Zeig dem Nutzer:

```
## Archivierung abgeschlossen

**Archiviert:** PROJ-X bis PROJ-Y (Z Features, Version X.Y.Z)
**Langzeitgedächtnis:** Aktualisiert
**Migrations-Historie:** [N neue Einträge / keine Änderungen an Nutzerdaten]
**INDEX.md:** Bereit für neue Features ab PROJ-Z

Nächster Schritt: `/write-spec` um neue Features anzulegen.
```

## Important Rules

- NIEMALS Feature-Specs löschen — immer nur ins Archiv VERSCHIEBEN
- NIEMALS Tests oder Code archivieren — nur die Spec-Datei
- NIEMALS Daten verlieren — an das Memory anhängen, nicht überschreiben
- NIEMALS Features mit Status "Approved" archivieren — die sind getestet, aber nicht ausgeliefert
- `docs/migration-history.md` bleibt außerhalb des Archivs und wächst immer weiter
- INDEX.md so klein wie möglich halten (keine ausgelieferten Features in der aktiven Tabelle)
- Verschiebungen immer verifizieren (Verzeichnis nach dem `mv` erneut auflisten)
- "Next Available ID" in INDEX.md korrekt setzen
- Auf Deutsch kommunizieren
