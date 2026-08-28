---
name: autonom
description: Autonome Umsetzung aller geplanten Features — Architektur, UI, Domain/Daten, QA, Bugfixes, Commit. Fragt bei wesentlichen Entscheidungen aktiv nach.
argument-hint: "optional: feature-spec-path oder PROJ-X"
user-invocable: true
model: opus
---

# Autonomer Feature-Orchestrator (Token-Optimiert)

## Rolle
Du bist der autonome Orchestrator für diese PySide6-Desktop-Anwendung. Du delegierst ALLES an wenige, gebündelte Pipeline-Agents.

## ABSOLUTE REGELN

1. **Hauptagent = Orchestrator + Entscheidungs-Gateway** — Für die Umsetzung NUR das `Agent`-Tool verwenden (kein Read, Edit, Write, Bash, Grep, Glob, Skill, ToolSearch, TodoWrite). EINZIGE Ausnahme: `AskUserQuestion`, um wesentliche Entscheidungen mit dem Nutzer zu klären.
2. **Wesentliche Entscheidungen IMMER an den Nutzer** — Bei wesentlichen Entscheidungen (Definition unten) niemals selbst entscheiden, sondern den Nutzer per `AskUserQuestion` fragen. Nur triviale Implementierungsdetails entscheidet der Skill selbst (nach Spec/Konsistenz/Einfachheit).
3. **Minimale Agent-Anzahl** — Features in Batches bündeln. Max 3-5 Features pro Pipeline-Agent.
4. **Ultra-komprimierte Rückgaben** — Jeder Agent gibt max 1 Zeile pro Feature zurück.

## Wesentliche Entscheidungen (Nutzer fragen — NICHT selbst entscheiden)

Eine Entscheidung ist **wesentlich**, wenn sie eine dieser Kategorien trifft:
- **Architektur** — Schichtenzuordnung, Fenster-/Dialogstruktur, Threading-Modell, Pattern-Wahl
- **Datenmodell / Migration** — Tabellen, Spalten, Constraints, Cascade-Verhalten, alles was bestehende Nutzerdaten verändert
- **Neue Abhängigkeit** — jedes zusätzliche Paket vergrößert den Installer und die Angriffsfläche
- **Scope-Abweichung** — alles, was vom Feature-Spec abweicht, darüber hinausgeht oder ihn einschränkt
- **Mehrdeutigkeit** — Spec lässt mehrere sinnvolle Interpretationen zu
- **Destruktive Aktion** — Nutzerdaten oder Dateien löschen/überschreiben, force-push, irreversible Migration

**Triviale Entscheidungen (selbst entscheiden, NICHT fragen):** Variablen-/Datei-/Klassennamen,
Widget-Wahl im Rahmen des Designs, Layout-Details, Reihenfolge von Buttons, Formatierung.

**Ablauf bei wesentlichen Entscheidungen:**
- Tauchen sie VOR der Umsetzung auf (aus Phase 0) → Hauptagent fragt den Nutzer per `AskUserQuestion`, BEVOR Batch-Agents starten. Die Antworten gehen als feste Vorgaben in die Batch-Prompts.
- Tauchen sie WÄHREND der Umsetzung neu auf → Batch-Agent entscheidet NICHT selbst, sondern stoppt das betroffene Feature und meldet `DECISION_NEEDED` zurück. Der Hauptagent fragt den Nutzer und startet das Feature mit der Antwort erneut (idempotent).

## Ablauf (3 Phasen)

---

### Phase 0: Kontext (1 Explore-Agent)

Agent-Typ: `Explore`, Thoroughness: `medium`

```
AUFGABE: Sammle Projektkontext für autonome Feature-Umsetzung.

1. `.claude/skills/autonom/LESSONS.md` lesen
2. `features/INDEX.md` — alle Features mit Status "Planned" oder "Architected" identifizieren
3. Jeden zugehörigen Feature-Spec lesen (inkl. Tech Design und Desktop Behaviour, falls vorhanden)
4. `git ls-files src/ventilsteuerung/` ausführen
5. `ls src/ventilsteuerung/ui/widgets/ src/ventilsteuerung/core/services/ src/ventilsteuerung/data/repositories/` ausführen
6. `ls src/ventilsteuerung/migrations/versions/` ausführen
7. `cat src/ventilsteuerung/core/models.py` lesen

RÜCKGABE (PFLICHT — max 40 Zeilen, KEIN Fliesstext):
PLANNED:
- PROJ-X: [Name] | Schichten: UI/CORE/BEIDE | Migration: Y/N | Deps: [IDs/"keine"]
[...pro Feature 1 Zeile]

WESENTLICHE_ENTSCHEIDUNGEN (Architektur/Datenmodell/neue Abhängigkeit/Scope-Abweichung/Mehrdeutigkeit aus den Specs, die VOR der Umsetzung geklärt werden müssen):
- PROJ-X: [Entscheidungsfrage] | Optionen: [A] vs [B] (vs [C])
[...nur echte wesentliche Punkte; wenn keine: "keine"]

BATCHES (3-5 Features pro Batch, abhängige Features im selben Batch, Features mit Migration NIE parallel in verschiedenen Batches):
B1: PROJ-X, PROJ-Y, PROJ-Z
B2: PROJ-A, PROJ-B
[...]

EXISTING: models=[Liste], services=[Liste], repos=[Liste], widgets=[Liste], migrations=[letzte Revision]
LESSONS: [Max 2 Sätze]
```

**Migrations-Regel für die Batch-Bildung:** Alembic-Revisionen bilden eine lineare Kette. Zwei parallel laufende Agents, die je eine Revision erzeugen, produzieren zwei Köpfe und eine kaputte Migration. Alle Features mit `Migration: Y` gehören deshalb in **denselben** Batch und werden dort **nacheinander** abgearbeitet.

---

### Phase 0.5: Entscheidungs-Gate (Hauptagent, VOR jeder Umsetzung)

Wenn Phase 0 `WESENTLICHE_ENTSCHEIDUNGEN` zurückgibt (≠ "keine"):
- Stelle sie dem Nutzer per `AskUserQuestion` (gebündelt, bis zu 4 Fragen pro Aufruf, mehrere Aufrufe falls nötig)
- Formuliere je Frage konkrete Optionen mit kurzer Konsequenz; empfohlene Option zuerst mit „(empfohlen)"
- Die Antworten werden je Feature gesammelt und in Phase 1 als feste Vorgaben in den Batch-Prompt eingesetzt

Wenn `WESENTLICHE_ENTSCHEIDUNGEN: keine` → ohne Rückfrage direkt zu Phase 1.

---

### Phase 1: Pipeline-Batches (1 Agent pro Batch, PARALLEL)

Starte alle Batch-Agents GLEICHZEITIG. Agent-Typ: `general-purpose`

Jeder Agent bekommt diesen Prompt (angepasst pro Batch):

```
AUFGABE: Implementiere diese Features KOMPLETT — Architektur, UI, Domain/Daten, QA, Bugfixes, Commits.

PROJEKT: Standalone-Desktop-App in Python. PySide6 (Qt 6) GUI, SQLAlchemy 2.0 + SQLite,
Alembic-Migrationen, Auslieferung als PyInstaller-Bundle im Inno-Setup-Installer.
KEIN Web, kein Browser, kein Server, keine REST-API.

FEATURES IN DIESEM BATCH:
- PROJ-X: [Name] | Schichten: UI/CORE/BEIDE | Migration: Y/N
- PROJ-Y: [Name] | Schichten: ... | Migration: ...
[...]

GEKLÄRTE VORGABEN (vom Nutzer entschieden — verbindlich befolgen, NICHT erneut hinterfragen):
- PROJ-X: [Entscheidung] → [gewählte Option]
[...oder "keine"]

BESTEHEND: models=[Liste], services=[Liste], repos=[Liste], widgets=[Liste], letzte Migration=[Revision]
LESSONS: [Zusammenfassung]

WICHTIG — ENTSCHEIDUNGEN:
- Triviale Implementierungsdetails (Namen, Widget-Wahl im Rahmen des Designs, Layout-Details) selbst entscheiden nach Spec/Konsistenz/Einfachheit.
- Taucht eine NEUE wesentliche Entscheidung auf (Architektur, Datenmodell/Migration, neue Abhängigkeit, Scope-Abweichung vom Spec, echte Mehrdeutigkeit, destruktive Aktion), die NICHT durch die geklärten Vorgaben abgedeckt ist: NICHT selbst entscheiden. Das betroffene Feature stoppen (bereits Erledigtes committen) und über RÜCKGABE als DECISION_NEEDED melden. Andere Features im Batch normal weiterführen.

MIGRATIONEN: Features mit Migration NACHEINANDER abarbeiten, nie parallel. Alembic-Revisionen
bilden eine lineare Kette — zwei gleichzeitig erzeugte Revisionen ergeben zwei Köpfe.
Nach jeder Revision: `alembic upgrade head` prüfen.

---

PRO FEATURE diese Pipeline durchlaufen:

**Schritt 1: Architektur** (überspringen, wenn Status bereits "Architected")
- Feature-Spec lesen (Pfad: features/PROJ-X-*.md)
- Tech Design ans Ende des Specs schreiben: Screen-Struktur, Datenmodell, Schichtenzuordnung (ui/core/data), Threading für lange Operationen, neue Abhängigkeiten
- Commit: `docs(PROJ-X): Add technical design`

**Schritt 2: Domain & Daten** (NUR wenn Schichten CORE oder BEIDE)
- `.claude/rules/data.md` und `.claude/rules/security.md` lesen und befolgen
- Modelle in `core/models.py` (SQLAlchemy 2.0: Mapped[...] / mapped_column), Indizes, Constraints, Cascade
- Migration: `alembic revision --autogenerate -m "..."` — generierte Datei IMMER prüfen und korrigieren, funktionierendes downgrade() schreiben
- Verifizieren: `alembic upgrade head && alembic downgrade -1 && alembic upgrade head`
- Repository in `data/repositories/`, Service in `core/services/`
- KEIN PySide6-Import in core/ oder data/
- Unit-Tests in `tests/unit/`
- `ruff check src tests && ruff format --check src tests && mypy src && pytest` müssen passen
- Commit: `feat(PROJ-X): Implement domain and data layer`

**Schritt 3: UI** (NUR wenn Schichten UI oder BEIDE)
- `.claude/rules/ui.md` lesen und befolgen
- Qt-Widgets bevorzugen, keine Nachbauten von Qt-Primitiven
- Layout-Manager statt setGeometry(); Model/View für Tabellen
- Jede Operation über ~100 ms in QThreadPool/QRunnable, Ergebnis per Signal — GUI-Thread NIE blockieren
- Alle vier Zustände: loading, error, empty, populated
- Deutsche UI-Strings mit echten Umlauten, in self.tr(...)
- Services aus core/services/ aufrufen; keine DB-Session in ui/
- GUI-Tests in `tests/gui/`, markiert mit @pytest.mark.gui
- `ruff check src tests && ruff format --check src tests && mypy src && pytest` müssen passen
- Commit: `feat(PROJ-X): Implement UI`

**Schritt 4: QA**
- Acceptance Criteria aus dem Feature-Spec gegen den Code prüfen
- Desktop-Dimensionen prüfen: Minimalgröße, DPI 150%, keine GUI-Blockade bei langen Operationen, Persistenz über Neustart, leerer Erststart, Upgrade mit vorhandener Datenbank
- Security-Check: fehlerhafte Importdateien, kein pickle/eval/yaml.load auf Nutzerdaten, keine Schreibzugriffe im Installationsverzeichnis, keine personenbezogenen Daten im Log
- Bugs mit Severity dokumentieren (CRITICAL/HIGH/MEDIUM/LOW) — eine GUI-Blockade ist mindestens HIGH
- `ruff check src tests && mypy src && pytest`

**Schritt 5: Bugfixes** (nur bei CRITICAL/HIGH Bugs)
- Bugs fixen
- `ruff check src tests && ruff format --check src tests && mypy src && pytest`
- Commit: `fix(PROJ-X): Fix QA issues`
- Bei weiterhin CRITICAL Bugs: nochmal QA → Fix (max 2 Iterationen)

**Schritt 6: Status**
- Feature-Spec Status auf "In Review" setzen
- `features/INDEX.md` aktualisieren (Status-Spalte)
- Nach dem Edit verifizieren (Datei nochmal lesen)

---

REGELN:
- Qt-Widgets bevorzugen, KEINE Nachbauten vorhandener Qt-Primitiven
- Schichtentrennung strikt: core/ und data/ importieren NIEMALS PySide6
- Nutzerdaten liegen im Benutzerdatenordner (config.database_path()), NIE neben der EXE
- Einfachste Lösung bevorzugen
- Echte UTF-8-Umlaute (ä/ö/ü/ß), nie ae/oe/ue
- Code und Commits auf Englisch, UI-Strings auf Deutsch
- Alle Commits mit: Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>

---

RÜCKGABE-FORMAT (PFLICHT — EXAKT dieses Format, NICHTS anderes):
BATCH_STATUS: OK/TEILWEISE/FEHLER
FEATURES:
- PROJ-X: OK | Commits: abc1234, def5678 | QA: 5/5 AC | Migration: a1b2c3d4/keine | Entscheidungen: [kurz]
- PROJ-Y: DECISION_NEEDED | Frage: [Entscheidungsfrage] | Optionen: [A] vs [B] | Bisher committet: ghi9012
[1 Zeile pro Feature, NICHT MEHR]
OFFENE_BUGS: keine / [Liste mit PROJ-ID und Bug]
```

**Nach Phase 1 — Hauptagent prüft auf `DECISION_NEEDED`:**
- Für jedes Feature mit `DECISION_NEEDED`: den Nutzer per `AskUserQuestion` fragen
- Danach das betroffene Feature mit der Antwort als `GEKLÄRTE VORGABEN` erneut an einen `general-purpose`-Agent geben (idempotent — bereits Erledigtes wird übersprungen)
- Erst wenn keine offenen `DECISION_NEEDED` mehr existieren → Phase 2

---

### Phase 2: Abschluss (1 Agent)

Agent-Typ: `general-purpose`

```
AUFGABE: Finalisiere den autonom-Durchlauf.

1. `features/INDEX.md` lesen — verifiziere, dass alle bearbeiteten Features "In Review" sind
2. Falls Features fehlen: Status korrigieren
3. Migrations-Kette prüfen: `alembic heads` — es darf GENAU EIN Head existieren.
   Bei mehreren Heads: mit `alembic merge` zusammenführen und `alembic upgrade head` verifizieren
4. Gesamtsuite laufen lassen: `ruff check src tests && ruff format --check src tests && mypy src && pytest`
5. App-Start verifizieren: `python -m ventilsteuerung` startet ohne Fehler
6. `.claude/skills/autonom/LESSONS.md` lesen
7. Falls Fehler aufgetreten sind (aus den Batch-Ergebnissen): neue Lessons hinzufügen
   - UI-/Qt-Fehler → `.claude/skills/ui/LESSONS.md`
   - Modell-/Migrations-Fehler → `.claude/skills/core/LESSONS.md`
   - Packaging-Fehler → `.claude/skills/release/LESSONS.md`
   - Orchestrierung → `.claude/skills/autonom/LESSONS.md`
8. Commit: `docs: Update feature statuses and lessons`

Batch-Ergebnisse:
[Hier die 1-Zeilen-Ergebnisse aller Batches einfügen]

RÜCKGABE (PFLICHT — max 5 Zeilen):
STATUS: OK/FEHLER
FEATURES_IN_REVIEW: [Anzahl]
ALEMBIC_HEADS: [Anzahl — muss 1 sein]
SUITE: [ruff/mypy/pytest jeweils OK oder FEHLER]
NEUE_LESSONS: [Anzahl]
```

---

## Zusammenfassung am Ende

Zeige dem Nutzer eine kompakte Übersicht:

```
## Ergebnis

| Feature | Status | QA | Migration | Commits |
|---------|--------|----|-----------|---------|
| PROJ-X: [Name] | In Review | 5/5 AC | a1b2c3d4 | abc1234, def5678 |
[...1 Zeile pro Feature]

**Mit dir geklärte Entscheidungen:** [Nur wenn es welche gab — sonst weglassen]
| Feature | Entscheidung | Gewählt |
|---------|-------------|---------|
| PROJ-X | [Was] | [Option] |

**Qualitäts-Gates:** ruff OK | mypy OK | pytest X passed | App startet

**Nächster Schritt:** `/release` um die Features als Installer auszuliefern.
```

Wenn ein Qualitäts-Gate fehlgeschlagen ist, sag das direkt und ungeschönt — nicht als Fußnote.

## Entscheidungsleitfaden
0. **Wesentliche Entscheidung? → Nutzer fragen** (Architektur, Datenmodell/Migration, neue Abhängigkeit, Scope-Abweichung, Mehrdeutigkeit, destruktive Aktion). Nie selbst entscheiden.

Für triviale Entscheidungen gilt danach:
1. Feature-Spec hat Vorrang
2. Bestehender Code → Konsistenz
3. Qt-Bordmittel bevorzugen
4. Einfachheit → minimale Lösung
5. Nutzerdaten → im Zweifel die Variante, die nichts verliert

## Context Recovery

Falls der Kontext komprimiert wird, starte einen `Explore`-Agent:
```
Sammle: features/INDEX.md, git log --oneline -10, alembic heads
RÜCKGABE (max 5 Zeilen): Welche Features fehlen noch? Wie viele Alembic-Heads gibt es?
```
