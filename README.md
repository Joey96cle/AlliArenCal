# Allianz-Arena-Kalender für Google Calendar

Dieses Projekt erzeugt automatisch einen abonnierbaren ICS-Kalender aus den offiziellen Veranstaltungsseiten der Allianz Arena.

**Kalender abonnieren:**  
https://joey96cle.github.io/AlliArenCal/allianz-arena.ics

## Enthaltene Termine

Übernommen werden Veranstaltungen mit eindeutig festgelegtem Datum und Uhrzeit, insbesondere:

- Heimspiele des FC Bayern
- Champions-League- und DFB-Pokal-Spiele
- Länderspiele
- NFL-Spiele
- Konzerte und weitere feste Großveranstaltungen; Konzerte ohne veröffentlichte Uhrzeit werden als Ganztagstermin übernommen

Nicht übernommen werden:

- noch nicht terminierte Spiele und Datumsbereiche
- Öffnungszeiten
- Arena-Touren und Museumstermine
- Sonderausstellungen, Familiensonntage und Schließtage

## Darstellung, Zusatzinformationen und Ergebnisse

Jeder Kalendertitel beginnt mit einem passenden Symbol:

- ⚽ Fußball
- 🏀 Basketball
- 🏈 American Football / NFL
- 🎤 Konzert
- 📅 sonstige Veranstaltung

Statt der allgemeinen Kategorie „Sport“ wird die konkrete **Sportart** angezeigt. Bei abgeschlossenen Spielen steht das Ergebnis zwischen den Teams, zum Beispiel **⚽ FC Bayern 7:0 Union Berlin**. Jeder Termin enthält außerdem in der Beschreibung den sichtbaren Eintrag **Zuletzt aktualisiert: TT.MM.JJJJ, HH:MM Uhr** und technisch das ICS-Feld **LAST-MODIFIED**.

Die Beschreibung eines Sporttermins enthält – soweit auf der offiziellen Seite angegeben – den Wettbewerb sowie Spieltag oder Pokalrunde. Eine kurze Erklärung ordnet Bundesliga, Champions League, DFB-Pokal, Nations League oder NFL ein.

Bei Konzert- und Live-Terminen wird nach Möglichkeit eine kurze Hintergrundinformation zum Künstler ergänzt. Ist keine eindeutige Information verfügbar, bleibt es bei einer neutralen Einordnung als Konzert oder Live-Veranstaltung.

Der Kalender enthält rückwirkend **alle erkannten Veranstaltungen ab dem 1. Januar 2026** und zusätzlich die zukünftigen Termine. Bereits gespeicherte vergangene Veranstaltungen bilden ein dauerhaftes Archiv: Sie bleiben einschließlich Endständen und Künstlerinformationen erhalten, auch wenn die Allianz Arena sie später von ihren Übersichtsseiten entfernt. Sobald ein Spiel beendet ist, sucht der Generator den Endstand zunächst auf der offiziellen Monatsseite und anschließend zusätzlich bei **ESPN**. Ein gefundener Endstand erscheint im Titel und in der Beschreibung des Sporttermins, zum Beispiel:

- **⚽ FC Bayern München 4:3 Real Madrid**
- Beschreibung: **Endstand: 4:3**

Ein externes Ergebnis wird nur übernommen, wenn Datum, Heimteam, Auswärtsteam und der Status „beendet“ übereinstimmen. In der Beschreibung steht dann **Ergebnisquelle: ESPN**. Kann kein eindeutiger Treffer gefunden werden, wird kein Ergebnis geraten. Fehlen Wettbewerb oder Spieltag auf der offiziellen Veranstaltungsseite, weist der Kalendereintrag darauf hin.

Die stabile Event-ID sorgt dafür, dass Google einen bestehenden Termin aktualisieren kann, statt bei einem nachträglich ergänzten Endstand oder einer Terminverschiebung einen zweiten Termin anzulegen.

## Google Calendar

1. [Google Calendar](https://calendar.google.com/) im Browser öffnen.
2. Neben **Weitere Kalender** auf **+** klicken.
3. **Per URL** auswählen.
4. Diese Adresse einfügen: **https://joey96cle.github.io/AlliArenCal/allianz-arena.ics**
5. **Kalender hinzufügen** wählen.

Der abonnierte Kalender erscheint anschließend auch in der Google-Calendar-App auf dem Handy. Google legt selbst fest, wann externe Kalender erneut abgerufen werden. Änderungen und Endstände können deshalb erst nach einigen Stunden, gelegentlich erst innerhalb von 24 Stunden erscheinen.

## Automatische Aktualisierung

Der Workflow [Allianz-Arena-Kalender aktualisieren](.github/workflows/update-calendar.yml) läuft täglich um **04:17 Uhr UTC**:

- 06:17 Uhr während der deutschen Sommerzeit
- 05:17 Uhr während der deutschen Winterzeit

Er kann außerdem unter **Actions → Allianz-Arena-Kalender aktualisieren → Run workflow** manuell gestartet werden.

Der Ablauf:

1. vorhandene vergangene Termine aus dem ICS-Archiv laden
2. offizielle Allianz-Arena-Seiten abrufen
3. Fußball, Basketball, American Football/NFL, Konzerte und weitere Veranstaltungen unterscheiden
4. passende Emojis, Zusatzinformationen und den Aktualisierungszeitpunkt ergänzen
5. fehlende Endstände abgeschlossener Spiele zusätzlich bei ESPN suchen
6. neue Daten mit dem dauerhaften Archiv zusammenführen
7. **docs/allianz-arena.ics** und **docs/status.json** aktualisieren
8. Änderungen automatisch in den Branch **main** übertragen und über GitHub Pages veröffentlichen

Wenn die Quellen vorübergehend keine zukünftige Veranstaltung liefern, verwendet der Workflow automatisch die bestehende ICS-Datei als Backup. Der Lauf bleibt erfolgreich und versucht die Aktualisierung am nächsten Tag erneut; im Status wird dann **fallback_used: true** vermerkt.

## Status prüfen

Der aktuelle technische Status steht in [docs/status.json](docs/status.json):

- **updated_at:** Zeitpunkt der letzten erfolgreichen Erzeugung
- **events:** Gesamtzahl der enthaltenen vergangenen und zukünftigen Veranstaltungen
- **future_events:** Anzahl der zukünftigen Veranstaltungen
- **archive_start:** Beginn des Kalendersarchivs (aktuell 2026-01-01)
- **fallback_used:** zeigt an, ob wegen leerer Quelldaten die bestehende ICS als Backup verwendet wurde
- **failed_pages:** Seiten, die beim Abruf nicht erreichbar waren

Ein erfolgreicher Lauf wird unter **Actions** mit einem grünen Haken angezeigt. Danach veröffentlicht der automatische Workflow **pages build and deployment** die neue ICS-Datei.

## Fehlerbehebung

### Workflow wird nicht angezeigt

Die Workflow-Datei muss exakt unter **.github/workflows/update-calendar.yml** liegen.

### Lauf endet nach 15 Minuten

Direkte Abrufe der Allianz-Arena-Webseite können blockiert werden oder in einen Timeout laufen. Der Scraper verwendet deshalb vorrangig eine textbasierte Abrufmethode.

### Push wird mit „fetch first“ abgelehnt

Der Workflow lädt vor dem Push den aktuellen Stand von **main** per Rebase. Dadurch werden zwischenzeitliche Repository-Änderungen berücksichtigt.

### „Keine zukünftigen Veranstaltungen erkannt“

Dann konnte der Parser keine passenden festen Termine erkennen. Die vorhandene ICS-Datei wird dabei nicht überschrieben. Unter **Actions** den Schritt **Kalender erzeugen** öffnen und das Protokoll prüfen.

## Dateien

| Datei | Zweck |
|---|---|
| **scraper.py** | Abruf, Filterung, Zusatzinformationen, Ergebnisse und ICS-Erzeugung |
| **requirements.txt** | Python-Abhängigkeiten |
| **.github/workflows/update-calendar.yml** | tägliche und manuelle Automatisierung |
| **docs/allianz-arena.ics** | öffentlich abonnierbarer Kalender |
| **docs/status.json** | Status des letzten erfolgreichen Laufs |

## Betrieb

Nach der Einrichtung ist kein laufender PC erforderlich. GitHub Actions aktualisiert den Kalender automatisch, GitHub Pages stellt ihn öffentlich bereit und Google Calendar ruft ihn regelmäßig ab.
