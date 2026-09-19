# Allianz-Arena-Kalender für Google Calendar

Dieses Projekt liest täglich die offiziellen Seiten der Allianz Arena und erzeugt einen abonnierbaren Kalender. Übernommen werden nur Veranstaltungen mit festem Datum und fester Uhrzeit. Öffnungszeiten, Touren, Museumstermine, Schließtage und noch nicht terminierte Spiele werden ignoriert.

## Einmalige Einrichtung auf GitHub

1. Entpacke die ZIP-Datei auf dem PC.
2. Öffne dein bereits angelegtes GitHub-Repository.
3. Klicke **Add file → Upload files**.
4. Ziehe **den Inhalt** des Ordners `allianz-arena-calendar` in das Upload-Feld – einschließlich der Ordner `.github` und `docs`. Nicht den äußeren Ordner hochladen.
5. Klicke unten auf **Commit changes**.
6. Öffne im Repository **Settings → Actions → General**. Unter **Workflow permissions** wählst du **Read and write permissions** und speicherst.
7. Öffne **Actions → Allianz-Arena-Kalender aktualisieren → Run workflow → Run workflow**.
8. Warte auf den grünen Haken. Danach sollte `docs/status.json` eine Eventanzahl größer als 0 anzeigen.
9. Öffne **Settings → Pages**. Wähle bei **Source** „Deploy from a branch“, bei **Branch** `main` und als Ordner `/docs`; dann **Save**.

Deine Kalenderadresse lautet anschließend normalerweise:

```text
https://DEIN-GITHUB-NAME.github.io/REPOSITORY-NAME/allianz-arena.ics
```

Du findest die genaue Pages-Adresse nach der Veröffentlichung unter **Settings → Pages**.

## In Google Calendar abonnieren

Das erstmalige Abonnieren geht am zuverlässigsten im Browser (auch später am Handy in der Desktop-Ansicht):

1. Öffne [Google Calendar](https://calendar.google.com/).
2. Links neben **Weitere Kalender** auf `+` klicken.
3. **Per URL** auswählen.
4. Die oben erzeugte `.ics`-Adresse einfügen und **Kalender hinzufügen** wählen.

Danach erscheint der Kalender automatisch auch in der Google-Calendar-App auf dem Handy. Du musst weder deinen PC eingeschaltet lassen noch dort ein Programm ausführen. GitHub aktualisiert die Datei jeden Morgen; Google entscheidet selbst, wann abonnierte Kalender neu eingelesen werden, was einige Stunden dauern kann.

## Was automatisch passiert

- Die GitHub Action läuft täglich gegen 06:17 Uhr deutscher Sommerzeit bzw. 05:17 Uhr deutscher Winterzeit.
- Zusätzlich kann sie jederzeit unter **Actions** mit **Run workflow** gestartet werden.
- Fix terminierte Fußball-, Länderspiel- und NFL-Termine kommen aus der offiziellen Heimspielübersicht.
- Weitere fixe Großveranstaltungen werden aus dem offiziellen Monatskalender ergänzt.
- Eine Terminverschiebung behält dieselbe Kalender-ID und sollte daher nicht als Dublette erscheinen.
- Falls gar kein zukünftiger Termin erkannt wird, überschreibt das Programm den vorhandenen Kalender aus Sicherheitsgründen nicht.

## Fehler prüfen

Unter **Actions** siehst du den letzten Lauf. In `docs/status.json` stehen die Zahl der erkannten Veranstaltungen und eventuell nicht erreichbare Monatsseiten. Einzelne Seitenfehler verhindern die Aktualisierung nicht, solange mindestens ein künftiger Termin erkannt wird.

