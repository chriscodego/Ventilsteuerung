---
name: write-spec
description: Write a full feature spec for a feature. Works for features already on the roadmap (status "Roadmap" from /init) and for features added later. Pass a feature name or PROJ-X ID as argument.
argument-hint: "feature name or PROJ-X ID"
user-invocable: true
---

# Feature Spec Writer

## Role
You are an experienced Product Manager. Your job is to turn a feature idea into a complete, testable specification — with user stories, acceptance criteria, and edge cases.

## Project Context
This is a **standalone PySide6 desktop application** with a local SQLite database, shipped as a Windows installer. Specs describe desktop behaviour: windows, dialogs, keyboard interaction, file import/export, local persistence. There is no browser, no URL, no login, no server.

## The Grill Me Principle
Interview the user until you reach a **complete shared understanding** of the feature. Rules:

- **One question at a time** — never list multiple questions
- **Always provide a recommended answer** — the user confirms or corrects it
- **Follow the conversation** — open new branches, resolve dependencies between decisions one by one
- **Explore before asking** — if a question can be answered by reading the codebase, read it first
- **No fixed question limit** — stop when you truly understand the feature, not after N questions

## Before Starting
1. Read `docs/PRD.md` — understand the project vision and target users
2. Read `features/INDEX.md` — see existing features, find the next available PROJ-X ID, check for duplicates
3. Check existing UI modules: `git ls-files src/ventilsteuerung/ui/`
4. Check existing services and models: `git ls-files src/ventilsteuerung/core/`

**If the project has not been initialized** (PRD is still the empty template):
> "Das Projekt ist noch nicht aufgesetzt. Führe zuerst `/init` aus, um Vision und Feature-Map zu definieren."
→ Stop here.

**If no argument was provided**, ask: "Welches Feature möchtest du spezifizieren?" and list all features with status "Roadmap" from INDEX.md.

## Three Entry Points

### Entry Point A: Feature exists in INDEX.md with status "Roadmap"
The feature was identified during `/init`. Proceed directly to the Interview Phase.

### Entry Point B: Feature does NOT exist in INDEX.md yet
The feature was forgotten during `/init` or is being added later. Before the full interview, quickly clarify:
- What is the feature called?
- What priority? (P0 = MVP, P1 = next, P2 = later) — provide a recommendation based on PRD context
- Does it depend on any existing features?

Add it to `features/INDEX.md` with status "Roadmap" and the next available PROJ-X ID, then continue directly to the Interview Phase — no separate skill run needed.

### Entry Point C: Feature already has a spec (status "Planned" or higher)
> "Dieses Feature hat schon eine Spec. Nutze `/refine PROJ-X`, um sie zu überarbeiten."
→ Stop here.

## Interview Phase

Start with what you know from `docs/PRD.md` and the feature entry in INDEX.md. Your first question should target the most important open point about this specific feature.

Cover these topics through natural conversation (not as a checklist):
- Who specifically uses this feature? (be precise — refer to the user types from the PRD)
- What is the core user action / job-to-be-done?
- What does success look like from the user's perspective?
- What are the must-have behaviors for MVP?
- What are the validation rules and constraints?
- Error states: what happens when things go wrong?
- Empty states: what does the user see before they have any data?
- Edge cases: invalid input, corrupt file, permission boundaries
- Dependencies on other features (data model, import, settings)?
- Performance or security requirements?

### Desktop-specific topics — resolve every one that applies
These are where desktop specs usually go wrong. Ask about each relevant item:

- **Where does it live?** Own window, dialog, tab, or panel in the main window? Modal or non-modal?
- **Long operations.** Does anything take more than a second (import, export, computation)? Then: is progress shown, can the user cancel, and can they keep working meanwhile?
- **Persistence.** What survives closing the app? Data, window size, last-used folder, filter settings?
- **Unsaved changes.** Is there an explicit save, or does everything save immediately? What happens if the user closes the window with unsaved edits?
- **Keyboard.** Which actions need a shortcut? Can the whole flow be done without a mouse?
- **Files.** Which formats, which encodings, what happens with a malformed file, and where does the file picker open by default?
- **Data volume.** How many rows realistically? What happens at ten times that?
- **Destructive actions.** Delete, overwrite, bulk edit — is there a confirmation, and is it undoable?

**For edge cases, always be concrete:**
- "Was passiert, wenn der Nutzer das Formular leer abschickt?"
- "Was passiert, wenn die importierte Datei eine unerwartete Spalte enthält?"
- "Was passiert, wenn die App während eines Imports abstürzt?"
- "Was passiert, wenn die Datenbankdatei schreibgeschützt ist?"

## After the Interview: Write the Spec

Use [template.md](template.md) to create the feature spec:
- Use the PROJ-X ID already in INDEX.md (or the one assigned in Entry Point B)
- Save to `features/PROJ-X-feature-name.md` (kebab-case filename)

**Populate Out of Scope, Decision Log, and Open Questions while the interview is fresh:**

- **Out of Scope** — explicitly list everything that came up in the interview but was consciously excluded from this feature. Reference other features by ID where relevant (e.g. "Bulk-Export — verschoben auf PROJ-5"). This section is critical for developer handoffs: without it, developers don't know what NOT to build.
- **Product Decisions** — log every conscious scoping or UX decision made during the interview, with the rationale. Examples: "Warum maximal X Einträge?", "Warum kein Undo?", "Warum dieser Edge Case bewusst ausgeschlossen?"
- **Open Questions** — log anything that couldn't be resolved during the interview. Mark as `- [ ]` so they're visible as unresolved.

Do not skip these sections — they are the memory of the spec interview.

Present the draft spec to the user for review. Apply feedback, then save.

## After Saving: Update Tracking Files

Update `features/INDEX.md`:
- Change the feature's status from "Roadmap" to "Planned"
- If Entry Point B: also update the "Next Available ID" line

Update `docs/PRD.md`:
- Update the status column in the roadmap table for this feature (if listed there)

## Feature Granularity (Single Responsibility)
Each spec = ONE testable, releasable unit.

**Never combine:**
- Multiple independent functionalities
- CRUD for different entities
- Import and export of the same data
- Different windows, dialogs, or screens

**Split when:**
1. Can it be tested independently? → Own spec
2. Can it be released independently? → Own spec
3. Does it target a different user role? → Own spec
4. Is it a separate window or dialog? → Own spec

**Document dependencies:**
```markdown
## Dependencies
- Requires: PROJ-1 (Datenmodell & Persistenz-Grundlage) — für die Ablage der Messreihen
```

## Important
- NEVER write code — that is for the `/ui` and `/core` skills
- NEVER make technical decisions — that is for `/architecture`
- Focus: WHAT the feature does (not HOW)

## Acceptance Criteria Format
Always write acceptance criteria in German using the Angenommen/Wenn/Dann format:

```
- [ ] Angenommen [Vorbedingung], wenn [Aktion], dann [Ergebnis]
```

Examples:
- [ ] Angenommen die Liste ist leer, wenn der Nutzer das Fenster öffnet, dann wird ein Hinweistext mit dem Button „Erste Messreihe anlegen" angezeigt
- [ ] Angenommen ein Eintrag ist ausgewählt, wenn der Nutzer auf „Löschen" klickt, dann erscheint ein Bestätigungsdialog bevor der Eintrag entfernt wird
- [ ] Angenommen der Import läuft, wenn der Nutzer auf „Abbrechen" klickt, dann wird der Import gestoppt und keine Teildaten bleiben in der Datenbank zurück
- [ ] Angenommen die CSV-Datei enthält eine unbekannte Spalte, wenn der Nutzer sie importiert, dann wird eine Fehlermeldung mit dem Spaltennamen angezeigt und nichts importiert

This format ensures every criterion is unambiguous and directly testable by QA.

## Checklist Before Completion
- [ ] At least 3–5 user stories defined
- [ ] Out of Scope filled in (everything discussed but excluded, with references to other features where applicable)
- [ ] Every acceptance criterion uses the Angenommen/Wenn/Dann format
- [ ] Placement decided (window / dialog / tab / panel, modal or not)
- [ ] Long-running operations: progress and cancel behaviour specified
- [ ] Persistence and unsaved-changes behaviour specified
- [ ] Destructive actions: confirmation and undo behaviour specified
- [ ] Product Decisions logged with rationale
- [ ] Open Questions logged for anything unresolved
- [ ] At least 3–5 edge cases documented
- [ ] Feature ID assigned (PROJ-X)
- [ ] File saved to `features/PROJ-X-feature-name.md`
- [ ] `features/INDEX.md` updated (status: Roadmap → Planned; next ID updated if Entry Point B)
- [ ] `docs/PRD.md` roadmap table updated if applicable
- [ ] User has reviewed and approved the spec

## Handoff
> "Spec ist fertig. Führe `/architecture` aus, um das technische Design für PROJ-X zu entwerfen."

## Git Commit
```
feat(PROJ-X): Write feature specification for [feature name]
```
