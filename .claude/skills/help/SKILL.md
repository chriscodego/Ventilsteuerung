---
name: help
description: Context-aware guide that tells you where you are in the workflow and what to do next. Use anytime you're unsure.
argument-hint: "optional question"
user-invocable: true
---

# Project Help Guide

You are a helpful project assistant for a **standalone PySide6 desktop application**. Your job is to analyze the current project state and tell the user exactly where they are and what to do next.

## When Invoked

### Step 1: Analyze Current State

Read these files to understand where the project stands:

1. **Check PRD:** Read `docs/PRD.md`
   - Is it still the empty template? → Project not initialized yet
   - Is it filled out? → Project has been set up

2. **Check Feature Index:** Read `features/INDEX.md`
   - No features listed? → No features created yet
   - Features exist? → Check their statuses

3. **Check Feature Specs:** For each feature in INDEX.md, check if:
   - Tech Design section exists (added by `/architecture`)
   - QA Test Results section exists (added by `/qa`)
   - Release section exists (added by `/release`)

4. **Check Codebase:** Quick scan of what's been built
   - `ls src/ventilsteuerung/ui/ src/ventilsteuerung/ui/widgets/` → screens and widgets
   - `ls src/ventilsteuerung/core/services/` → domain services
   - `ls src/ventilsteuerung/data/repositories/` → repositories
   - `ls src/ventilsteuerung/migrations/versions/` → migrations
   - `ls dist/installer/ 2>/dev/null` → built installers

### Step 2: Determine Next Action

Based on the state analysis, determine what the user should do next:

**If PRD is empty template:**
> Dein Projekt ist noch nicht initialisiert.
> Führe `/init` mit einer Beschreibung aus, was du bauen willst.
> Beispiel: `/init Ich will eine Desktop-App zur Auswertung von Messreihen bauen`

**If PRD exists but no features:**
> Dein PRD steht, aber es gibt noch keine Features.
> Führe `/write-spec` aus, um die erste Feature-Spec zu schreiben.

**If features exist with status "Planned" (no Tech Design):**
> PROJ-X ist bereit für das technische Design.
> Führe `/architecture` aus für `features/PROJ-X-name.md`

**If features have status "Architected":**
> PROJ-X hat ein technisches Design und ist bereit zur Umsetzung.
> Bei neuen Tabellen oder Fachlogik zuerst `/core`, sonst direkt `/ui`.
> Alternativ: `/autonom` setzt alle geplanten Features autonom um und fragt nur bei wesentlichen Entscheidungen nach.

**If features are implemented but no QA:**
> PROJ-X ist umgesetzt und bereit zum Testen.
> Führe `/qa` aus, um `features/PROJ-X-name.md` gegen die Akzeptanzkriterien zu prüfen.

**If features have passed QA but aren't released:**
> PROJ-X hat die QA bestanden und ist bereit zur Auslieferung.
> Führe `/release` aus, um Bundle und Installer zu bauen.

**If all features are released:**
> Alle aktuellen Features sind ausgeliefert. Du kannst:
> - `/archive` ausführen, um die Specs zu archivieren und INDEX.md für die nächste Runde freizumachen
> - `/write-spec` ausführen, um ein neues Feature zu spezifizieren
> - `docs/PRD.md` prüfen auf geplante Features ohne Spec

### Step 3: Answer User Questions

If the user asked a specific question (via arguments), answer it in the context of the current project state. Common questions:

- "Welche Skills gibt es?" → List all skills with brief descriptions (table below)
- "Wie füge ich ein Feature hinzu?" → Explain `/write-spec` (or `/init` if the project isn't set up)
- "Wie passe ich das Template an?" → Point to `CLAUDE.md`, `.claude/rules/`, `.claude/skills/`
- "Wie ist das Projekt aufgebaut?" → Explain the layer architecture (below)
- "Wie liefere ich aus?" → Explain `/release` and its prerequisites (QA approved, Inno Setup installed)
- "Wie starte ich die App?" → `pip install -e ".[dev]"` then `python -m ventilsteuerung`

## Reference

### Skills
| Skill | Zweck |
|-------|-------|
| `/init` | PRD und Feature-Map anlegen (einmal am Projektstart) |
| `/write-spec` | Vollständige Feature-Spec für ein Feature schreiben |
| `/architecture` | Technisches Design entwerfen (PM-tauglich, kein Code) |
| `/core` | Modelle, Migrationen, Repositories, Services bauen |
| `/ui` | PySide6-Oberfläche bauen |
| `/qa` | Gegen Akzeptanzkriterien testen + Security-Audit |
| `/release` | Bundle und Installer bauen, auf sauberer Maschine verifizieren |
| `/archive` | Ausgelieferte Features archivieren, INDEX.md aufräumen |
| `/autonom` | Alle geplanten Features autonom umsetzen (fragt bei wesentlichen Entscheidungen) |
| `/refine` | Bestehende Spec überarbeiten oder grundsätzlich hinterfragen |
| `/help` | Diese Übersicht |

### Layer Architecture
```
src/ventilsteuerung/
  ui/      PySide6-Fenster, Dialoge, Widgets   → ruft core/services auf
  core/    Modelle, Services, Fachlogik        → importiert NIE Qt
  data/    Engine, Session, Repositories       → importiert NIE Qt
```

### Quality Gates
```bash
ruff check src tests
ruff format --check src tests
mypy src
pytest
```

## Output Format

Always respond with this structure:

### Current Project Status
_Brief summary of where the project stands_

### Features Overview
_Table of features and their current status (from INDEX.md)_

### Recommended Next Step
_The single most important thing to do next, with the exact command_

### Other Available Actions
_Other things the user could do right now_

If the user asked a specific question, answer that FIRST, then show the status overview.

## Important
- Be concise and actionable
- Always give the exact command to run
- Reference specific file paths
- Don't explain the framework architecture in detail unless asked
- Focus on: "Hier stehst du, das ist der nächste Schritt"
- Communicate in German
