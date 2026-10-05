#!/usr/bin/env python3
"""Offizielle Allianz-Arena-Termine als abonnierbaren ICS-Kalender erzeugen."""

from __future__ import annotations

import hashlib
import html
import json
import re
import time
import unicodedata
from dataclasses import dataclass, replace
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
UA = "Mozilla/5.0 (compatible; AllianzArenaCalendar/4.0; +https://github.com/)"
ARCHIVE_START = date(2026, 1, 1)

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
MONTHS = {n.lower(): i for i, n in enumerate(
    ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"], 1
)}
MONTH_PATTERN = "|".join(name.capitalize() for name in MONTHS)
EMOJIS = {
    "Fußball": "⚽",
    "Basketball": "🏀",
    "American Football": "🏈",
    "Konzert": "🎤",
    "Veranstaltung": "📅",
}
COMPETITIONS = {
    "BL": ("Bundesliga", "Die Bundesliga ist die höchste deutsche Fußball-Spielklasse."),
    "CL": ("UEFA Champions League", "Die UEFA Champions League ist der wichtigste europäische Vereinswettbewerb der UEFA."),
    "POKAL": ("DFB-Pokal", "Der DFB-Pokal ist ein deutscher Fußball-Pokal im K.-o.-System."),
    "NL": ("UEFA Nations League", "Die UEFA Nations League ist ein UEFA-Wettbewerb für Nationalmannschaften."),
    "NFL": ("NFL", "Die NFL ist die höchste US-amerikanische Liga im American Football."),
}
_wiki_cache: dict[str, str | None] = {}
_score_cache: dict[tuple[str, str, str], list[dict]] = {}
SCORE_SOURCES = (
    ("soccer", "ger.1"),
    ("soccer", "ger.dfb_pokal"),
    ("soccer", "uefa.champions"),
    ("soccer", "uefa.nations"),
    ("soccer", "uefa.wchampions"),
    ("football", "nfl"),
)


@dataclass(frozen=True)
class Event:
    title: str
    start: datetime | date
    end: datetime | date
    source: str
    all_day: bool = False
    category: str = "Veranstaltung"
    details: tuple[str, ...] = ()
    result: str | None = None
    uid_title: str | None = None
    uid_override: str | None = None

    @property
    def uid(self) -> str:
        if self.uid_override:
            return self.uid_override
        # Ergebnis und Datum absichtlich nicht einbeziehen: Google aktualisiert das bestehende Event.
        key = normalize_title(self.uid_title or self.title)
        return hashlib.sha256(key.encode()).hexdigest()[:24] + "@allianz-arena-calendar"

    @property
    def summary(self) -> str:
        emoji = EMOJIS.get(self.category, "📅")
        if self.result and " – " in self.title:
            home, away = self.title.split(" – ", 1)
            return f"{emoji} {home} {self.result} {away}"
        return f"{emoji} {self.title}"


def fetch(url: str) -> str:
    """Direkt abrufen; bei Sperre/Timeout über einen reinen Text-Proxy erneut versuchen."""
    errors: list[str] = []
    candidates = ["https://r.jina.ai/http://" + url.removeprefix("https://"), url]
    for candidate in candidates:
        try:
            response = requests.get(candidate, headers={"User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9"}, timeout=20)
            response.raise_for_status()
            if len(response.text) < 500:
                raise RuntimeError("Antwort unerwartet kurz")
            return response.text
        except Exception as exc:
            errors.append(f"{candidate}: {exc}")
            time.sleep(1)
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
    document = re.sub(r"!\[[^]]*]\([^)]*\)", "", document)
    document = re.sub(r"\[([^]]+)]\([^)]*\)", r"\1", document)
    return "\n".join(clean(x.lstrip("#* -")) for x in document.splitlines() if clean(x.lstrip("#* -")))


def competition_details(code: str, round_value: str) -> tuple[str, ...]:
    name, background = COMPETITIONS.get(code.upper(), (code, "Dies ist ein Sportwettbewerb."))
    details = [f"Wettbewerb: {name}"]
    round_value = clean(round_value)
    if round_value:
        label = "Runde" if code.upper() == "POKAL" else "Spieltag"
        details.append(f"{label}: {round_value}")
    details.append(f"Hintergrund: {background}")
    return tuple(details)


def parse_sports(document: str) -> list[Event]:
    text = text_version(document)
    events: list[Event] = []
    pattern = re.compile(
        r"(BL|NL|CL|Pokal|NFL)\s*\|\s*([^|\n]*)\|\s*"
        r"(?:Mo|Di|Mi|Do|Fr|Sa|So),?\s*(\d{1,2})\.(\d{1,2})\.(\d{2,4})\s*\|\s*"
        r"(\d{1,2}):(\d{2})\s*\|\s*([^|\n]+?)\s*\|\s*([^|\n]+)", re.I
    )
    for match in pattern.finditer(text):
        code, round_value, day, month, year, hour, minute, team, opponent = match.groups()
        year_number = int(year) + (2000 if int(year) < 100 else 0)
        team, opponent = clean(team), clean(opponent)
        if IGNORE.search(team + " " + opponent):
            continue
        start = datetime(year_number, int(month), int(day), int(hour), int(minute), tzinfo=TZ)
        sport = "American Football" if code.upper() == "NFL" else "Fußball"
        events.append(Event(
            title=f"{team} – {opponent}", start=start, end=start + timedelta(hours=3),
            source=SPORTS_URL, category=sport, details=competition_details(code, round_value),
        ))
    print(f"Fixe Sportveranstaltungen erkannt: {len(events)}")
    return dedupe(events)


def season(year: int, month: int) -> str:
    return f"{year}-{year + 1}" if month >= 7 else f"{year - 1}-{year}"


def month_urls(months_back: int = 12, months_ahead: int = 18) -> list[str]:
    first = datetime.now(TZ).date().replace(day=1)
    result = []
    for offset in range(-months_back, months_ahead + 1):
        idx = first.year * 12 + first.month - 1 + offset
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
            value = clean(re.sub(r"\b(Konzert-Highlight|Konzert)\b", "", value, flags=re.I))
            if value:
                return value
    return None


def event_category(title: str, context: str) -> str:
    value = f"{title} {context}".lower()
    if any(word in value for word in ("nfl", "american football", "detroit lions", "patriots")):
        return "American Football"
    if any(word in value for word in ("basketball", "euroleague", "easycredit bbl", "fc bayern basketball")):
        return "Basketball"
    if " – " in title or " gegen " in value or any(word in value for word in ("bundesliga", "champions league", "dfb-pokal", "nations league")):
        return "Fußball"
    return "Konzert"


def parse_concerts(text: str, source: str) -> list[Event]:
    """Konzerte ohne veröffentlichte Uhrzeit als einzelne Ganztagstermine übernehmen."""
    events: list[Event] = []
    pattern = re.compile(
        rf"(?P<title>[^\n]{{2,160}}?)\s+am\s+(?P<dates>[^\n]{{2,100}}?)\s+"
        rf"(?P<year>20\d{{2}})\s*(?:in der Allianz Arena\s*)?Konzert-Highlight",
        re.I,
    )
    for match in pattern.finditer(text):
        raw_title = clean(match.group("title"))
        # Kalenderzeilen enthalten vor dem Künstler oft noch „Do | 11.06.“.
        title = clean(re.sub(r"^.*\d{2}\.\d{2}\.\s*", "", raw_title))
        # Die Übersichtsseite stellt dem Künstlernamen teilweise noch einen
        # ausgeschriebenen Datumsbereich voran (z. B. „Donnerstag, 11. Juni –
        # Freitag, 12. Juni LINKIN PARK“). Dieser gehört nicht zum Titel und
        # würde außerdem die Wikipedia-Suche auf ein falsches Ergebnis lenken.
        weekday = r"(?:Montag|Dienstag|Mittwoch|Donnerstag|Freitag|Samstag|Sonntag)"
        written_date = rf"{weekday},?\s+\d{{1,2}}\.?\s+(?:{MONTH_PATTERN})"
        title = clean(re.sub(rf"^{written_date}(?:\s*[-–]\s*{written_date})?\s+", "", title, flags=re.I))
        date_text = clean(match.group("dates"))
        month_names = re.findall(MONTH_PATTERN, date_text, re.I)
        days = [int(value) for value in re.findall(r"\b(\d{1,2})\.?\b", date_text)]
        if not title or not month_names or not days:
            continue
        month = MONTHS[month_names[-1].lower()]
        year = int(match.group("year"))
        artist_info = wikipedia_summary(title)
        details: list[str] = []
        if artist_info:
            details.append(f"Künstlerinfo: {artist_info}")
        for day in dict.fromkeys(days):
            try:
                start = date(year, month, day)
            except ValueError:
                continue
            events.append(Event(
                title=title, start=start, end=start + timedelta(days=1), source=source,
                all_day=True, category="Konzert", details=tuple(details),
                uid_title=f"{title}-{start.isoformat()}",
            ))
    return dedupe(events)


def result_from_context(context: str) -> str | None:
    # Die offizielle Seite schreibt Ergebnisse beispielsweise als „5 zu 0 5 : 0“.
    match = re.search(r"\b(\d{1,2})\s+zu\s+(\d{1,2})\b", context, re.I)
    if not match:
        match = re.search(r"(?:Endstand|Ergebnis)\D{0,20}(\d{1,2})\s*:\s*(\d{1,2})", context, re.I)
    return f"{match.group(1)}:{match.group(2)}" if match else None


def context_details(context: str) -> tuple[str, ...]:
    details: list[str] = []
    for code, (name, background) in COMPETITIONS.items():
        if re.search(re.escape(name), context, re.I) or re.search(rf"\b{re.escape(code)}\b", context, re.I):
            details.extend((f"Wettbewerb: {name}", f"Hintergrund: {background}"))
            break
    match = re.search(r"(\d{1,2})\.\s*Spieltag", context, re.I)
    if match:
        details.insert(1, f"Spieltag: {match.group(1)}")
    round_match = re.search(r"(\d{1,2})\.\s*Runde", context, re.I)
    if round_match:
        details.insert(1, f"Runde: {round_match.group(1)}")
    return tuple(dict.fromkeys(details))


def wikipedia_summary(title: str) -> str | None:
    if title in _wiki_cache:
        return _wiki_cache[title]
    query = re.sub(r"\b(live|konzert|concert|open air|tour)\b", "", title, flags=re.I).strip()
    try:
        response = requests.get(
            "https://de.wikipedia.org/w/api.php",
            params={"action": "query", "generator": "search", "gsrsearch": query, "gsrlimit": 1,
                    "prop": "extracts", "exintro": 1, "explaintext": 1, "redirects": 1, "format": "json"},
            headers={"User-Agent": UA}, timeout=10,
        )
        response.raise_for_status()
        pages = response.json().get("query", {}).get("pages", {})
        extract = clean(next(iter(pages.values())).get("extract", "")) if pages else ""
        sentences = re.split(r"(?<=[.!?])\s+", extract)
        summary = " ".join(sentences[:2])[:500].strip() or None
    except Exception as exc:
        print(f"Künstlerinfo für {title!r} nicht verfügbar: {exc}")
        summary = None
    _wiki_cache[title] = summary
    return summary


def normalize_team(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    aliases = {
        "fc bayern munchen": "bayern",
        "bayern munchen": "bayern",
        "bayern munich": "bayern",
        "fc bayern": "bayern",
        "1 fc union berlin": "union berlin",
        "1 fc koln": "koln",
        "vfb stuttgart": "stuttgart",
        "paris saint germain": "psg",
    }
    return aliases.get(value, value)


def teams_match(left: str, right: str) -> bool:
    left, right = normalize_team(left), normalize_team(right)
    return left == right or (min(len(left), len(right)) >= 5 and (left in right or right in left))


def scoreboard_events(sport: str, league: str, event_date: date) -> list[dict]:
    key = (sport, league, event_date.isoformat())
    if key in _score_cache:
        return _score_cache[key]
    try:
        response = requests.get(
            f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard",
            params={"dates": event_date.strftime("%Y%m%d"), "limit": 100},
            headers={"User-Agent": UA}, timeout=12,
        )
        response.raise_for_status()
        result = response.json().get("events", [])
    except Exception as exc:
        print(f"Ergebnisabruf {league} für {event_date} fehlgeschlagen: {exc}")
        result = []
    _score_cache[key] = result
    return result


def external_result(event: Event) -> str | None:
    """Abgeschlossenen Endstand bei ESPN suchen und über beide Teams absichern."""
    if " – " not in event.title:
        return None
    home_name, away_name = event.title.split(" – ", 1)
    event_date = event.start.date() if isinstance(event.start, datetime) else event.start
    for sport, league in SCORE_SOURCES:
        for candidate in scoreboard_events(sport, league, event_date):
            competition = (candidate.get("competitions") or [{}])[0]
            status = competition.get("status", {}).get("type", {})
            if not status.get("completed"):
                continue
            competitors = competition.get("competitors", [])
            home = next((item for item in competitors if item.get("homeAway") == "home"), None)
            away = next((item for item in competitors if item.get("homeAway") == "away"), None)
            if not home or not away:
                continue
            source_home = home.get("team", {}).get("displayName", "")
            source_away = away.get("team", {}).get("displayName", "")
            if teams_match(home_name, source_home) and teams_match(away_name, source_away):
                return f"{home.get('score')}:{away.get('score')}"
    return None


def add_external_results(events: list[Event]) -> list[Event]:
    now = datetime.now(TZ)
    enriched: list[Event] = []
    for event in events:
        is_past_sport = event.category in {"Fußball", "Basketball", "American Football"} and isinstance(event.start, datetime) and event.start < now
        if is_past_sport and not event.result:
            result = external_result(event)
            if result:
                print(f"Endstand von ESPN ergänzt: {event.title} {result}")
                event = replace(event, result=result, details=event.details + ("Ergebnisquelle: ESPN",))
        enriched.append(event)
    return enriched


def parse_calendar_page(document: str, source: str) -> list[Event]:
    lines = text_version(document).splitlines()
    text = "\n".join(lines)
    events: list[Event] = []
    matches = list(DATE_TIME.finditer(text))
    for index, match in enumerate(matches):
        # Nur Text bis zum nächsten datierten Eintrag verwenden. So können Ergebnis,
        # Spieltag oder Wettbewerb nicht vom nachfolgenden Termin übernommen werden.
        segment_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        segment_lines = text[match.end():segment_end].splitlines()
        context = " ".join(segment_lines)
        if IGNORE.search(context):
            continue
        title = plausible_title(segment_lines, 0)
        if not title:
            continue
        day, month_name, year, hour, minute = match.groups()
        start = datetime(int(year), MONTHS[month_name.lower()], int(day), int(hour), int(minute), tzinfo=TZ)
        category = event_category(title, context)
        is_sport = category in {"Fußball", "Basketball", "American Football"}
        details = context_details(context) if is_sport else ()
        if is_sport and not details:
            details = (
                "Art: Sportveranstaltung",
                "Wettbewerb/Spieltag: auf der offiziellen Veranstaltungsseite nicht eindeutig angegeben",
            )
        if not is_sport:
            artist_info = wikipedia_summary(title)
            details = ("Art: Konzert oder Live-Veranstaltung",)
            if artist_info:
                details += (f"Künstlerinfo: {artist_info}",)
        events.append(Event(
            title=title, start=start, end=start + timedelta(hours=3), source=source,
            category=category, details=details,
            result=result_from_context(context) if is_sport and start < datetime.now(TZ) else None,
        ))
    events.extend(parse_concerts(text, source))
    return dedupe(events)


def merge_events(old: Event, new: Event) -> Event:
    details = tuple(dict.fromkeys(old.details + new.details))
    # Monatsseiten enthalten meist den Endstand; die Sportübersicht meist Wettbewerb/Spieltag.
    preferred = new if new.result or len(new.details) >= len(old.details) else old
    category = preferred.category
    if category == "Veranstaltung":
        category = new.category if new.category != "Veranstaltung" else old.category
    return replace(preferred, details=details, result=new.result or old.result, category=category)


def dedupe(events: list[Event]) -> list[Event]:
    found: dict[str, Event] = {}
    for event in events:
        found[event.uid] = merge_events(found[event.uid], event) if event.uid in found else event
    return list(found.values())


def escape_ics(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def unescape_ics(value: str) -> str:
    """Die für Textfelder relevanten iCalendar-Escapes rückgängig machen."""
    return re.sub(
        r"\\([nN,;\\])",
        lambda match: "\n" if match.group(1).lower() == "n" else match.group(1),
        value,
    )


def parse_existing_ics(path: Path = OUT) -> list[Event]:
    """Bereits veröffentlichte Termine lesen, damit das Archiv dauerhaft bleibt."""
    if not path.exists():
        return []
    document = path.read_text(encoding="utf-8").replace("\r\n ", "").replace("\n ", "")
    events: list[Event] = []
    for body in re.findall(r"BEGIN:VEVENT\r?\n(.*?)\r?\nEND:VEVENT", document, re.S):
        properties: dict[str, str] = {}
        for line in body.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            properties[key] = unescape_ics(value)
        uid = properties.get("UID")
        summary = properties.get("SUMMARY")
        start_key = next((key for key in properties if key.startswith("DTSTART")), None)
        end_key = next((key for key in properties if key.startswith("DTEND")), None)
        if not uid or not summary or not start_key or not end_key:
            continue
        all_day = "VALUE=DATE" in start_key
        try:
            if all_day:
                start: datetime | date = datetime.strptime(properties[start_key], "%Y%m%d").date()
                end: datetime | date = datetime.strptime(properties[end_key], "%Y%m%d").date()
            else:
                start = datetime.strptime(properties[start_key], "%Y%m%dT%H%M%S").replace(tzinfo=TZ)
                end = datetime.strptime(properties[end_key], "%Y%m%dT%H%M%S").replace(tzinfo=TZ)
        except ValueError:
            continue
        description = properties.get("DESCRIPTION", "")
        description_lines = [clean(line) for line in description.splitlines() if clean(line)]
        result_match = next((re.match(r"Endstand:\s*(\d{1,2}:\d{1,2})", line, re.I) for line in description_lines if line.lower().startswith("endstand:")), None)
        result = result_match.group(1) if result_match else None
        category = "Veranstaltung"
        for line in description_lines:
            match = re.match(r"(?:Sportart|Kategorie):\s*(.+)", line, re.I)
            if match:
                category = clean(match.group(1))
                break
        title = re.sub(r"^(?:⚽|🏀|🏈|🎤|📅)\s*", "", summary).strip()
        if result and category in {"Fußball", "Basketball", "American Football"}:
            title = title.replace(f" {result} ", " – ", 1)
        details = tuple(
            line for line in description_lines
            if not re.match(r"(?:Endstand|Sportart|Kategorie|Offizielle Quelle|Zuletzt aktualisiert):", line, re.I)
        )
        events.append(Event(
            title=title, start=start, end=end,
            source=properties.get("URL", BASE), all_day=all_day,
            category=category, details=details, result=result,
            uid_override=uid,
        ))
    return events


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


def event_sort_key(event: Event) -> datetime:
    if isinstance(event.start, datetime):
        return event.start
    return datetime.combine(event.start, datetime.min.time(), tzinfo=TZ)


def make_ics(events: list[Event], updated_at: datetime) -> str:
    now = updated_at.astimezone(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")
    updated_text = updated_at.astimezone(TZ).strftime("%d.%m.%Y, %H:%M Uhr")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Allianz Arena Calendar//DE", "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:Allianz Arena", "X-WR-TIMEZONE:Europe/Berlin", "X-PUBLISHED-TTL:PT12H"]
    for event in sorted(events, key=event_sort_key):
        description = list(event.details)
        if event.result:
            description.append(f"Endstand: {event.result}")
        label = "Sportart" if event.category in {"Fußball", "Basketball", "American Football"} else "Kategorie"
        description.extend((f"{label}: {event.category}", f"Offizielle Quelle: {event.source}", f"Zuletzt aktualisiert: {updated_text}"))
        lines += ["BEGIN:VEVENT", f"UID:{event.uid}", f"DTSTAMP:{now}", f"LAST-MODIFIED:{now}", f"SUMMARY:{escape_ics(event.summary)}"]
        if event.all_day:
            lines += [f"DTSTART;VALUE=DATE:{event.start:%Y%m%d}", f"DTEND;VALUE=DATE:{event.end:%Y%m%d}"]
        else:
            lines += [f"DTSTART;TZID=Europe/Berlin:{event.start:%Y%m%dT%H%M%S}", f"DTEND;TZID=Europe/Berlin:{event.end:%Y%m%dT%H%M%S}"]
        lines += ["LOCATION:Allianz Arena\\, Werner-Heisenberg-Allee 25\\, 80939 München",
                  f"DESCRIPTION:{escape_ics(chr(10).join(description))}", f"URL:{event.source}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(line) for line in lines) + "\r\n"


def main() -> None:
    # Vergangene Einträge sind ein dauerhaftes Archiv. Die Allianz-Arena-Seite
    # entfernt ältere Termine regelmäßig aus ihren Übersichten; ohne diese
    # Übernahme würden sie beim nächsten erfolgreichen Lauf aus der ICS fallen.
    existing = parse_existing_ics()
    now = datetime.now(TZ)
    archived = [
        event for event in existing
        if event_sort_key(event) < now
        and (event.start.date() if isinstance(event.start, datetime) else event.start) >= ARCHIVE_START
    ]
    sports = parse_sports(fetch(SPORTS_URL))
    calendar_events: list[Event] = []
    failures: list[str] = []
    for url in month_urls():
        try:
            calendar_events.extend(parse_calendar_page(fetch(url), url))
        except Exception as exc:
            failures.append(f"{url}: {exc}")
    events = add_external_results(dedupe(archived + sports + calendar_events))
    today = now.date()
    retained = [event for event in events if (event.start.date() if isinstance(event.start, datetime) else event.start) >= ARCHIVE_START]
    future_count = sum((event.start.date() if isinstance(event.start, datetime) else event.start) >= today for event in retained)
    if not retained or not future_count:
        raise RuntimeError("Keine zukünftigen Veranstaltungen erkannt; bestehende ICS-Datei bleibt unverändert.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    updated_at = datetime.now(TZ)
    OUT.write_text(make_ics(retained, updated_at), encoding="utf-8", newline="")
    STATUS.write_text(json.dumps({
        "updated_at": updated_at.isoformat(), "events": len(retained),
        "future_events": future_count, "archive_start": ARCHIVE_START.isoformat(), "failed_pages": failures,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(retained)} Veranstaltungen geschrieben ({future_count} zukünftig); {len(failures)} Seitenfehler.")


if __name__ == "__main__":
    main()
