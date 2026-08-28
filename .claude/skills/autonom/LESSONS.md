# Lessons Learned — Autonomer Orchestrator

> Dieses Dokument wird aktualisiert, wenn Fehler auftreten oder Korrekturen nötig sind.
> Lies es VOR jedem Durchlauf und befolge alle Regeln.
> Jede Lesson beantwortet drei Fragen: Was ist passiert? Warum? Was gilt ab jetzt stattdessen?

---

## L1 — Parallele Agents im selben Repo brauchen disjunkte Pfade und `git add <pfad>`

**Was ist passiert?** In diesem Durchlauf liefen mehrere Feature-Agents gleichzeitig im
selben Arbeitsverzeichnis (PROJ-4/PROJ-5 in `src/`, PROJ-6 in `packaging/`).

**Warum?** Es gibt genau einen Arbeitsbaum und genau einen Index. `git add -A` oder
`git commit -a` eines Agents nimmt die halbfertigen Dateien der anderen mit — der
Commit ist dann weder überprüfbar noch rücknehmbar, und die Quality Gates messen einen
Zustand, den niemand absichtlich hergestellt hat.

**Was gilt ab jetzt stattdessen?** Jeder parallel laufende Agent bekommt eine klar
abgegrenzte Pfadmenge zugewiesen und stagt **ausschließlich namentlich genannte
Dateien** (`git add <pfad> ...`). `git add -A`, `git add .` und `git commit -a` sind im
Parallelbetrieb verboten. Features, die dieselben Dateien anfassen, laufen
nacheinander, nicht parallel.

---

## L2 — Was ein Agent nicht selbst setzen darf, wird zur Nachtragsliste

**Was ist passiert?** Der PROJ-6-Agent (Paketierung) hat einen echten Fehler gefunden —
Alembic schreibt `__pycache__` ins Installationsverzeichnis —, durfte `src/` aber nicht
anfassen und hat die Lösung nur in seiner QA-Sektion beschrieben. Ohne einen expliziten
Abschlussschritt wäre der Fix nie eingebaut worden.

**Was gilt ab jetzt stattdessen?** Findet ein Agent einen Fehler außerhalb seiner
Pfadmenge, meldet er ihn als **Nachtrag mit Datei, Zeile und fertigem Commit-Betreff**
zurück. Der Orchestrator führt diese Nachträge in einer Liste und arbeitet sie im
Finalisierungsschritt ab, bevor die Gates das letzte Mal laufen.

---

## L3 — Der echte Build gehört ans Ende, nicht in den Feature-Schritt

**Was ist passiert?** PROJ-6 wurde parallel zu PROJ-4/PROJ-5 bearbeitet und konnte
deshalb nur statisch prüfen — Spec lesen, Trockenlauf der `.spec`-Datei. Der erst
danach nachgeholte echte Build fand sofort einen release-blockierenden Fehler
(fehlender Hidden Import `logging.config`), den die statische Prüfung strukturell nicht
finden konnte.

**Warum?** Ein Bundle lässt sich erst bauen und starten, wenn der Anwendungscode steht.
Alles davor ist Konfigurationsprüfung, kein Nachweis.

**Was gilt ab jetzt stattdessen?** Der Finalisierungsschritt eines Durchlaufs enthält
verpflichtend: (1) `alembic heads` zeigt genau einen Head, (2) alle vier Gates,
(3) `python -m <paket>` startet, (4) echter PyInstaller-Lauf **plus** Start des Bundles
gegen eine leere Datenbank. Punkt 4 darf nicht als „im Feature-Schritt erledigt"
abgehakt werden, wenn dort nur statisch geprüft wurde — und das Ergebnis wird in die
QA-Sektion der Paketierungs-Spec nachgetragen.

<!-- Neue Lessons werden hier eingefügt -->
