# Lessons Learned — Release Engineer

> Dieses Dokument wird aktualisiert, wenn Fehler auftreten oder Korrekturen nötig sind.
> Lies es VOR jedem Durchlauf und befolge alle Regeln.
> Jede Lesson beantwortet drei Fragen: Was ist passiert? Warum? Was gilt ab jetzt stattdessen?

---

## L1 — Ein Build, der startet, ist noch kein funktionierender Build

**Was ist passiert?** Der erste echte PyInstaller-Build von PROJ-6 startete sauber.
Erst der Start gegen eine *leere* Datenbank (`VENTIL_DATABASE_URL` auf eine frische Datei)
brach ab: `ModuleNotFoundError: No module named 'logging.config'` aus
`migrations/env.py`.

**Warum?** Auf der Entwicklermaschine existierte die Datenbank längst und war auf
`head`. Die Erstmigration — der einzige Codepfad, der `env.py` ausführt — lief also nie.
Genau dieser Pfad ist beim Endnutzer aber der allererste.

**Was gilt ab jetzt stattdessen?** Der Rauchtest des gefrorenen Bundles läuft **immer
zweimal**: einmal gegen die vorhandene Datenbank und einmal mit
`VENTIL_DATABASE_URL=sqlite:///<temp>/fresh.sqlite3` gegen eine leere. Danach im Log
prüfen, dass `Running upgrade  -> <revision>` tatsächlich erschienen ist, und die
Tabellen der frischen Datei auflisten. Ohne diesen zweiten Lauf ist das
Akzeptanzkriterium „startet auf frischem Windows" nicht belegt.

---

## L2 — Jeder Import in `migrations/env.py` gehört in `hiddenimports`

**Was ist passiert?** `env.py` macht `from logging.config import fileConfig`. Kein
anderes Modul der Anwendung importiert dieses Submodul (`logging_setup.py` nutzt nur
`logging.handlers`), also fehlte es im Bundle.

**Warum?** `env.py` wird als **Datendatei** ausgeliefert und von Alembic zur Laufzeit
über `spec_from_file_location` geladen. PyInstallers Analyse sieht Datendateien nicht —
die Importe darin sind für den Bundler unsichtbar. Dasselbe gilt für Qt-Module, die nur
über eine Port-Indirektion ausgewählt werden (QtBluetooth), und für die
Revisionsdateien selbst.

**Was gilt ab jetzt stattdessen?** Vor jedem Build `migrations/env.py` öffnen und jeden
Top-Level-Import gegen die `hiddenimports`-Liste der Spec abgleichen — auch
stdlib-Submodule wie `logging.config`. Wer `env.py` ändert, ändert die Spec mit.
Standardposten, die PyInstaller nie von allein findet:
`ventilsteuerung.core.models`, `ventilsteuerung.config`, `logging.config`,
`sqlalchemy.dialects.sqlite`, `PySide6.QtBluetooth` — dazu `migrations/` als `datas`,
sonst fehlen die Revisionsdateien im Bundle.

---

## L3 — Die gefrorene App darf kein Bytecode ins Installationsverzeichnis schreiben

**Was ist passiert?** Alembic lädt `env.py` und die Revisionsdateien mit CPythons
`SourceFileLoader`, der Bytecode neben die Quelldatei legt — im Bundle also nach
`{app}\_internal\ventilsteuerung\migrations\__pycache__`.

**Warum?** Bei einer Per-User-Installation ist das Verzeichnis beschreibbar, der
Schreibvorgang fällt also nicht auf. Er verletzt trotzdem die Projektregel „nie ins
Installationsverzeichnis schreiben", hinterlässt Reste nach der Deinstallation und
würde bei einer Maschinen-Installation scheitern.

**Was gilt ab jetzt stattdessen?** `__main__.py` setzt `sys.dont_write_bytecode = True`,
sobald `getattr(sys, "frozen", False)` gilt. Nach einem Rauchtest, der die
Erstmigration enthielt, gegenprüfen: `find dist/ -name __pycache__ -o -name "*.pyc"`
muss leer sein.

---

## L4 — „Hidden import not found" nach Herkunft sortieren

**Was ist passiert?** Der Build meldete drei fehlende Hidden Imports: `tzdata`,
`pysqlite2`, `MySQLdb`. Alle drei sehen alarmierend aus, sind aber harmlos.

**Warum?** Sie stammen aus fremden PyInstaller-Hooks (SQLAlchemy fragt optionale
Treiber ab), nicht aus unserer Spec. Ein Name aus *unserer* `hiddenimports`-Liste in
dieser Warnung wäre dagegen ein echter Fehler — meist ein umbenanntes Modul.

**Was gilt ab jetzt stattdessen?** Warnungen weder pauschal abnicken noch pauschal
verwerfen: jeden gemeldeten Namen gegen die eigene `hiddenimports`-Liste halten. Nur
Namen, die dort nicht vorkommen, sind Fremdhooks und dürfen stehen bleiben.

<!-- Neue Lessons werden hier eingefügt -->
