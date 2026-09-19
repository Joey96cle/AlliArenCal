#!/usr/bin/env python3
"""Offizielle Allianz-Arena-Termine als abonnierbaren ICS-Kalender erzeugen."""

from __future__ import annotations

import hashlib
import html
import json
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

BASE = "https://allianz-arena.com"
SPORTS_URL = BASE + "/de/news/terminkalender-nachste-heimspiele-in-der-allianz-arena"
OUT = Path("docs/allianz-arena.ics")
STATUS = Path("docs/status.json")
TZ = ZoneInfo("Europe/Berlin")
UA = "Mozilla/5.0 (compatible; AllianzArenaCalendar/2.0; +https://github.com/)"

IGNORE = re.compile(
    r"öffnungszeit|touren?\s*&?\s*museum|tickets verfügbar|sonderausstellung|"
    r"geschlossen|bastelspaß|familiensonntag|terminierung ausstehend",
    re.I,
)
DATE_TIME = re.compile(
    r"(?:Montag|Dienstag|Mittwoch|Donnerstag|Freitag|Samstag|Sonntag),?\s*"
    r"(\d{1,2})\.\s*(Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s*"
    r"(20\d{2})\s*(?:um|\|)\s*(\d{1,2}):(\d{2})",
    re.I,
)
SHORT_FIXED = re.compile(r"(?:Mo|Di|Mi|Do|Fr|Sa|So),?\s*(\d{2})\.(\d{2})\.(\d{2})\s*[| ]+\s*(\d{1,2}):(\d{2})")
MONTHS = {n.lower(): i for i, n in enumerate(
    ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"], 1
)}


@dataclass(frozen=True)
class Event:
    title: str
    start: datetime | date
    end: datetime | date
    source: str
    all_day: bool = False

    @property
    def uid(self) -> str:
        # Datum absichtlich nicht einbeziehen: Terminverschiebungen bleiben dasselbe Event.
        key = normalize_title(self.title)
        return hashlib.sha256(key.encode()).hexdigest()[:24] + "@allianz-arena-calendar"


def fetch(url: str) -> str:
    """Direkt abrufen; bei Sperre/Timeout über einen reinen Text-Proxy erneut versuchen."""
    errors: list[str] = []
    candidates = [url, "https://r.jina.ai/http://" + url.removeprefix("https://")]
    for candidate in candidates:
        for attempt in range(2):
            try:
                r = requests.get(candidate, headers={"User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9"}, timeout=25)
                r.raise_for_status()
                if len(r.text) < 500:
                    raise RuntimeError("Antwort unerwartet kurz")
                return r.text
            except Exception as exc:
                errors.append(f"{candidate}: {exc}")
                time.sleep(1 + attempt)
    raise RuntimeError("Abruf fehlgeschlagen: " + " | ".join(errors))


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip(" \t\r\n|-–")


def normalize_title(value: str) -> str:
    value = value.lower().replace("fc bayern münchen", "fc bayern")
    return re.sub(r"[^a-z0-9äöüß]+", "", value)


def text_version(document: str) -> str:
    if "<html" in document[:1000].lower() or "<!doctype" in document[:1000].lower():
        soup = BeautifulSoup(document, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()
        return "\n".join(clean(x) for x in soup.stripped_strings if clean(x))
    # Jina liefert Markdown; Links und Bildsyntax vereinfachen.
    document = re.sub(r"!\[[^]]*]\([^)]*\)", "", document)
    document = re.sub(r"\[([^]]+)]\([^)]*\)", r"\1", document)
    return "\n".join(clean(x.lstrip("#* -")) for x in document.splitlines() if clean(x.lstrip("#* -")))


def parse_sports(document: str) -> list[Event]:
    events: list[Event] = []
    rows: list[list[str]] = []
    if "<html" in document[:1000].lower() or "<!doctype" in document[:1000].lower():
        soup = BeautifulSoup(document, "html.parser")
        rows = [[clean(c.get_text(" ", strip=True)) for c in tr.find_all(["th", "td"])] for tr in soup.find_all("tr")]
    else:
        for line in document.splitlines():
            if "|" in line:
                rows.append([clean(c) for c in line.strip().strip("|").split("|")])

    for cells in rows:
        row = " | ".join(cells)
        m = SHORT_FIXED.search(row)
        if not m or "-:-" in row:
            continue
        day, month, yy, hour, minute = map(int, m.groups())
        # Offizielle Tabelle: Liga | Spieltag | Datum | Uhrzeit | Team | Gegner
        if len(cells) < 6:
            continue
        team, opponent = cells[-2], cells[-1]
        if IGNORE.search(team + " " + opponent):
            continue
        title = f"{team} – {opponent}"
        start = datetime(2000 + yy, month, day, hour, minute, tzinfo=TZ)
        events.append(Event(title, start, start + timedelta(hours=3), SPORTS_URL))
    return dedupe(events)


def season(year: int, month: int) -> str:
    return f"{year}-{year + 1}" if month >= 7 else f"{year - 1}-{year}"


def month_urls(months_ahead: int = 18) -> list[str]:
    today = datetime.now(TZ).date().replace(day=1)
    result = []
    for offset in range(months_ahead + 1):
        idx = today.year * 12 + today.month - 1 + offset
        year, month0 = divmod(idx, 12)
        month = month0 + 1
        result.append(f"{BASE}/de/events/{season(year, month)}/{year}-{month}")
    return result


def plausible_title(lines: list[str], start_index: int) -> str | None:
    for raw in lines[start_index:start_index + 12]:
        value = clean(raw)
        if not value or IGNORE.search(value) or DATE_TIME.search(value):
            continue
        if " gegen " in value.lower():
            return re.sub(r"\s+gegen\s+", " – ", value, flags=re.I)
        if any(k in value.lower() for k in ("konzert", "concert", "nfl", "live", "open air")):
            value = re.sub(r"\b(Konzert-Highlight|Konzert)\b", "", value, flags=re.I)
            value = clean(value)
            if value:
                return value
    return None


def parse_calendar_page(document: str, source: str) -> list[Event]:
    lines = text_version(document).splitlines()
    text = "\n".join(lines)
    events: list[Event] = []
    for m in DATE_TIME.finditer(text):
        line_index = text[:m.end()].count("\n")
        context = " ".join(lines[line_index:line_index + 15])
        if IGNORE.search(context):
            continue
        title = plausible_title(lines, line_index)
        if not title:
            continue
        day, month_name, year, hour, minute = m.groups()
        start = datetime(int(year), MONTHS[month_name.lower()], int(day), int(hour), int(minute), tzinfo=TZ)
        events.append(Event(title, start, start + timedelta(hours=3), source))
    return dedupe(events)


def dedupe(events: list[Event]) -> list[Event]:
    found: dict[str, Event] = {}
    for event in events:
        found[event.uid] = event
    return list(found.values())


def escape_ics(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold(line: str) -> str:
    chunks: list[str] = []
    while len(line.encode("utf-8")) > 73:
        cut = 70
        while len(line[:cut].encode("utf-8")) > 73:
            cut -= 1
        chunks.append(line[:cut])
        line = " " + line[cut:]
    chunks.append(line)
    return "\r\n".join(chunks)


def make_ics(events: list[Event]) -> str:
    now = datetime.now(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Allianz Arena Calendar//DE", "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:Allianz Arena", "X-WR-TIMEZONE:Europe/Berlin", "X-PUBLISHED-TTL:PT12H"]
    for e in sorted(events, key=lambda x: x.start):
        lines += ["BEGIN:VEVENT", f"UID:{e.uid}", f"DTSTAMP:{now}", f"SUMMARY:{escape_ics(e.title)}"]
        if e.all_day:
            lines += [f"DTSTART;VALUE=DATE:{e.start:%Y%m%d}", f"DTEND;VALUE=DATE:{e.end:%Y%m%d}"]
        else:
            lines += [f"DTSTART;TZID=Europe/Berlin:{e.start:%Y%m%dT%H%M%S}", f"DTEND;TZID=Europe/Berlin:{e.end:%Y%m%dT%H%M%S}"]
        lines += ["LOCATION:Allianz Arena\\, Werner-Heisenberg-Allee 25\\, 80939 München", f"DESCRIPTION:Offizielle Quelle: {escape_ics(e.source)}", f"URL:{e.source}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(x) for x in lines) + "\r\n"


def main() -> None:
    sports = parse_sports(fetch(SPORTS_URL))
    calendar_events: list[Event] = []
    failures: list[str] = []
    for url in month_urls():
        try:
            calendar_events.extend(parse_calendar_page(fetch(url), url))
        except Exception as exc:
            failures.append(f"{url}: {exc}")
    events = dedupe(sports + calendar_events)
    future = [e for e in events if (e.start.date() if isinstance(e.start, datetime) else e.start) >= datetime.now(TZ).date()]
    if not future:
        raise RuntimeError("Keine zukünftigen Veranstaltungen erkannt; bestehende ICS-Datei bleibt unverändert.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(make_ics(future), encoding="utf-8", newline="")
    STATUS.write_text(json.dumps({"updated_at": datetime.now(TZ).isoformat(), "events": len(future), "failed_pages": failures}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(future)} zukünftige Veranstaltungen geschrieben; {len(failures)} Seitenfehler.")


if __name__ == "__main__":
    main()
