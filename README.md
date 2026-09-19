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
- weitere feste Großveranstaltungen, sofern sie im offiziellen Monatskalender mit konkreter Uhrzeit erscheinen

Nicht übernommen werden:

- noch nicht terminierte Spiele und Datumsbereiche
- Öffnungszeiten
- Arena-Touren und Museumstermine
- Sonderausstellungen, Familiensonntage und Schließtage

## Google Calendar

1. [Google Calendar](https://calendar.google.com/) im Browser öffnen.
2. Neben **Weitere Kalender** auf **+** klicken.
3. **Per URL** auswählen.
4. Diese Adresse einfügen: **https://joey96cle.github.io/AlliArenCal/allianz-arena.ics**
5. **Kalender hinzufügen** wählen.

Der abonnierte Kalender erscheint anschließend auch in der Google-Calendar-App auf dem Handy. Google legt selbst fest, wann externe Kalender erneut abgerufen werden. Änderungen können deshalb erst nach einigen Stunden, gelegentlich erst innerhalb von 24 Stunden erscheinen.

## Automatische Aktualisierung

Der Workflow [Allianz-Arena-Kalender aktualisieren](.github/workflows/update-calendar.yml) läuft täglich um **04:17 Uhr UTC**:

- 06:17 Uhr während der deutschen Sommerzeit
- 05:17 Uhr während der deutschen Winterzeit

Er kann außerdem unter **Actions → Allianz-Arena-Kalender aktualisieren → Run workflow** manuell gestartet werden.

Der Ablauf:

1. offizielle Allianz-Arena-Seiten abrufen
2. fixe Veranstaltungen erkennen und unerwünschte Einträge herausfiltern
3. **docs/allianz-arena.ics** erzeugen
4. **docs/status.json** aktualisieren
5. Änderungen automatisch in den Branch **main** übertragen
6. Veröffentlichung über GitHub Pages

Stabile Event-IDs verhindern bei Terminänderungen möglichst doppelte Kalendereinträge. Wenn keine zukünftige Veranstaltung erkannt wird, bleibt die bestehende ICS-Datei aus Sicherheitsgründen unverändert.

## Status prüfen

Der aktuelle technische Status steht in [docs/status.json](docs/status.json):

- **updated_at:** Zeitpunkt der letzten erfolgreichen Erzeugung
- **events:** Anzahl der erkannten zukünftigen Veranstaltungen
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
| **scraper.py** | Abruf, Filterung und ICS-Erzeugung |
| **requirements.txt** | Python-Abhängigkeiten |
| **.github/workflows/update-calendar.yml** | tägliche und manuelle Automatisierung |
| **docs/allianz-arena.ics** | öffentlich abonnierbarer Kalender |
| **docs/status.json** | Status des letzten erfolgreichen Laufs |

## Betrieb

Nach der Einrichtung ist kein laufender PC erforderlich. GitHub Actions aktualisiert den Kalender automatisch, GitHub Pages stellt ihn öffentlich bereit und Google Calendar ruft ihn regelmäßig ab.
