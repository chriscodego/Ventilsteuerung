# Lessons Learned — UI Developer

> Dieses Dokument wird aktualisiert, wenn Fehler auftreten oder Korrekturen nötig sind.
> Lies es VOR jedem Durchlauf und befolge alle Regeln.
> Jede Lesson beantwortet drei Fragen: Was ist passiert? Warum? Was gilt ab jetzt stattdessen?

---

## L1 — Headless verifizieren: Testlauf und gepackte App brauchen verschiedene Wege

**Was ist passiert?** Die Gesamtsuite (193 Tests, inklusive pytest-qt) läuft nur mit
`QT_QPA_PLATFORM=offscreen` durch. Beim Rauchtest der **gepackten** App kam dagegen
kein einziges Ausgabezeichen zurück.

**Warum?** Die EXE wird mit `console=False` gebaut — sie hat kein stdout/stderr, an das
sich ein Aufrufer hängen könnte. Ein Startfehler erscheint dort ausschließlich als
QMessageBox, und die ist im Offscreen-Modus unsichtbar: der Prozess wirkt „läuft" und
steht in Wahrheit in einem Dialog.

**Was gilt ab jetzt stattdessen?** Bei der gepackten App gilt der Prozessstatus **nicht**
als Beweis. Verifiziert wird über die rotierende Logdatei unter
`%LOCALAPPDATA%\UPB\Ventilsteuerung\Logs\app.log`: Zeilenzahl vor dem Start merken,
App mit `QT_QPA_PLATFORM=offscreen` starten, nach einigen Sekunden beenden, das neue
Log-Ende lesen und aktiv nach `ERROR` und `Traceback` suchen. `VENTIL_LOG_LEVEL=DEBUG` und
`VENTIL_DATABASE_URL` auf eine Wegwerfdatei halten den Test von den echten Benutzerdaten
fern. Voraussetzung im Bundle: `plugins/platforms/qoffscreen.dll`.

<!-- Neue Lessons werden hier eingefügt -->
