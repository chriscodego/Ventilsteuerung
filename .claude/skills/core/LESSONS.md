# Lessons Learned — Core Developer

> Dieses Dokument wird aktualisiert, wenn Fehler auftreten oder Korrekturen nötig sind.
> Lies es VOR jedem Durchlauf und befolge alle Regeln.
> Jede Lesson beantwortet drei Fragen: Was ist passiert? Warum? Was gilt ab jetzt stattdessen?

---

## L1 — Ein Fallback für Race Conditions darf echte Fehler nicht verschlucken

**Was ist passiert?** `_upgrade_to_head()` fängt Exceptions aus `command.upgrade()` ab,
prüft mit `is_at_head()` das Schema und wertet „Schema ist aktuell" als verlorenes
Rennen gegen eine zweite Instanz — protokolliert als harmloses INFO. Genau dieser Zweig
hat im gepackten Build einen `ModuleNotFoundError` aus `migrations/env.py` unsichtbar
gemacht: auf einer vorhandenen Datenbank startete die App fehlerfrei, auf einer leeren
war sie kaputt.

**Warum?** Die Bedingung „Ausnahme aufgetreten UND Datenbank auf head" trifft auf zwei
völlig verschiedene Ursachen zu: verlorenes Rennen (harmlos) und kaputte
Migrationsumgebung (fatal, nur gerade folgenlos, weil nichts zu migrieren war).

**Was gilt ab jetzt stattdessen?** Jeder `except`-Zweig, der eine Exception aufgrund
einer nachträglichen Zustandsprüfung verwirft, protokolliert sie zusätzlich mit
`log.debug(..., exc_info=exc)`. Der geprüfte Zustand rechtfertigt das Weiterlaufen — er
beweist nicht, dass die Ursache harmlos war.

---

## L2 — Zwei gleichzeitig gestartete Instanzen kollidieren bei der Erstmigration

**Was ist passiert?** Beim parallelen Start zweier App-Instanzen auf einer noch leeren
Datenbank lasen beide eine leere `alembic_version`, beide führten dieselbe Revision aus,
die langsamere lief in „table already exists".

**Warum?** SQLite serialisiert die Schreibvorgänge, aber nicht die Entscheidung
„muss ich migrieren?". Zwischen Lesen und Schreiben liegt ein Fenster.

**Was gilt ab jetzt stattdessen?** Der Startpfad ist gegen Nebenläufigkeit ausgelegt und
bleibt es: begrenzte Wiederholungen mit kurzer Pause, danach `is_at_head()` als
Abbruchkriterium, und Marker-Vergleich am Fehlertext statt Exception-Typ
(`already exists`, `database is locked`, `duplicate column name`). Auch Hilfsdateien im
Datenverzeichnis brauchen instanz-eindeutige Namen — die Schreibprobe hängt deshalb
`os.getpid()` an. Wer diesen Pfad anfasst, testet ihn mit zwei gleichzeitig gestarteten
Prozessen gegen eine leere Datenbank.

<!-- Neue Lessons werden hier eingefügt -->
