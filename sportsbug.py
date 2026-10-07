"""Small personal score widget. Python 3.10+, PySide6; no background server."""
import csv
import ast
import io
import json
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QEvent, QRect, QUrl
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap, QFontMetrics, QDesktopServices
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QCheckBox, QSlider, QDialog, QScrollArea, QLineEdit, QMenu,
    QPlainTextEdit, QColorDialog, QMessageBox, QTreeWidget, QTreeWidgetItem)

ROOT = Path.home() / "SportsBug"
CONFIG = ROOT / "settings.json"
VERSION = "0.2.3"
EVENT_ROW_HEIGHT = 54
DEFAULT = {"favorites": ["NFL:SEA", "MLB:136", "F1:all"], "spoilers": False,
           "revealed": [], "top": False, "snap": False, "opacity": 88,
           "check_updates_on_launch": True, "update_repository": "", "background_color": "#0b1c2f", "expanded": False, "x": 100, "y": 100, "completed": {}, "seen_live": {}}
NFL_TEAMS = "Arizona Cardinals|ARI;Atlanta Falcons|ATL;Baltimore Ravens|BAL;Buffalo Bills|BUF;Carolina Panthers|CAR;Chicago Bears|CHI;Cincinnati Bengals|CIN;Cleveland Browns|CLE;Dallas Cowboys|DAL;Denver Broncos|DEN;Detroit Lions|DET;Green Bay Packers|GB;Houston Texans|HOU;Indianapolis Colts|IND;Jacksonville Jaguars|JAX;Kansas City Chiefs|KC;Las Vegas Raiders|LV;Los Angeles Chargers|LAC;Los Angeles Rams|LAR;Miami Dolphins|MIA;Minnesota Vikings|MIN;New England Patriots|NE;New Orleans Saints|NO;New York Giants|NYG;New York Jets|NYJ;Philadelphia Eagles|PHI;Pittsburgh Steelers|PIT;San Francisco 49ers|SF;Seattle Seahawks|SEA;Tampa Bay Buccaneers|TB;Tennessee Titans|TEN;Washington Commanders|WSH"
NHL_TEAMS = "Anaheim Ducks|ANA;Boston Bruins|BOS;Buffalo Sabres|BUF;Calgary Flames|CGY;Carolina Hurricanes|CAR;Chicago Blackhawks|CHI;Colorado Avalanche|COL;Columbus Blue Jackets|CBJ;Dallas Stars|DAL;Detroit Red Wings|DET;Edmonton Oilers|EDM;Florida Panthers|FLA;Los Angeles Kings|LA;Minnesota Wild|MIN;Montreal Canadiens|MTL;Nashville Predators|NSH;New Jersey Devils|NJ;New York Islanders|NYI;New York Rangers|NYR;Ottawa Senators|OTT;Philadelphia Flyers|PHI;Pittsburgh Penguins|PIT;San Jose Sharks|SJ;Seattle Kraken|SEA;St. Louis Blues|STL;Tampa Bay Lightning|TB;Toronto Maple Leafs|TOR;Utah Mammoth|UTA;Vancouver Canucks|VAN;Vegas Golden Knights|VGK;Washington Capitals|WSH;Winnipeg Jets|WPG"
MLB_TEAMS = "Arizona Diamondbacks|109;Atlanta Braves|144;Baltimore Orioles|110;Boston Red Sox|111;Chicago Cubs|112;Chicago White Sox|145;Cincinnati Reds|113;Cleveland Guardians|114;Colorado Rockies|115;Detroit Tigers|116;Houston Astros|117;Kansas City Royals|118;Los Angeles Angels|108;Los Angeles Dodgers|119;Miami Marlins|146;Milwaukee Brewers|158;Minnesota Twins|142;New York Mets|121;New York Yankees|147;Athletics|133;Philadelphia Phillies|143;Pittsburgh Pirates|134;San Diego Padres|135;San Francisco Giants|137;Seattle Mariners|136;St. Louis Cardinals|138;Tampa Bay Rays|139;Texas Rangers|140;Toronto Blue Jays|141;Washington Nationals|120"
MLB_CODES = dict(zip((record.rsplit("|", 1)[1] for record in MLB_TEAMS.split(";")),
    "ARI ATL BAL BOS CHC CWS CIN CLE COL DET HOU KC LAA LAD MIA MIL MIN NYM NYY ATH PHI PIT SD SF SEA STL TB TEX TOR WSH".split()))

CATALOG = {}
for league, listing in (("NFL", NFL_TEAMS), ("NHL", NHL_TEAMS), ("MLB", MLB_TEAMS)):
    for record in listing.split(";"):
        name, code = record.rsplit("|", 1)
        CATALOG[league + ":" + code] = name
for league, label in (("CFB", "football"), ("CBB", "basketball"), ("CBASE", "baseball")):
    for school, name in (("WASH", "Washington Huskies"), ("ARK", "Arkansas Razorbacks")):
        CATALOG[league + ":" + school] = name + " · college " + label
CATALOG["F1:all"] = "Formula 1 events"
# Stable team IDs from the Nippon Baseball Data Repository's schedule dataset.
NPB_TEAMS = {
    "1": "Yomiuri Giants", "2": "Tokyo Yakult Swallows", "3": "Yokohama DeNA BayStars",
    "4": "Chunichi Dragons", "5": "Hanshin Tigers", "6": "Hiroshima Toyo Carp",
    "7": "Saitama Seibu Lions", "8": "Hokkaido Nippon-Ham Fighters",
    "9": "Chiba Lotte Marines", "11": "Orix Buffaloes",
    "12": "Fukuoka SoftBank Hawks", "376": "Tohoku Rakuten Golden Eagles",
}
NPB_CODES = dict(zip(NPB_TEAMS, "YG YS DB CD HT HC SL NF LM OB SH RE".split()))
NPB_REPOSITORY = "https://github.com/armstjc/Nippon-Baseball-Data-Repository"
NPB_MIGRATION = {"PENDING:Hanshin Tigers": "NPB:5", "PENDING:Hiroshima Carp": "NPB:6"}
for code, name in NPB_TEAMS.items():
    CATALOG["NPB:" + code] = name
for league, label in (("football", "football"), ("basketball", "basketball"), ("baseball", "baseball")):
    if league != "football":
        CATALOG["PENDING:CWU-" + league] = "Central Washington University · " + label + " (feed pending)"
CATALOG["CFB:CWU"] = "Central Washington Wildcats · football (schedule only)"
CATALOG["MLS:9726"] = "Seattle Sounders FC · MLS"
CATALOG["J1:7112"] = "Kawasaki Frontale · J1 League"
CATALOG["PENDING:Seattle Orcas"] = "Seattle Orcas · cricket (feed pending)"
CATALOG["PENDING:Geelong Cats"] = "Geelong Cats · AFL (feed pending)"
CATALOG["MLR:142080"] = "Seattle Seawolves · rugby (results and schedule)"
CATALOG["NTSOC:660"] = "United States men · soccer (World Cup / friendlies)"
CATALOG["NTSOC:627"] = "Japan men · soccer (World Cup / friendlies)"
for country in ("United States", "Japan", "Ireland"):
    CATALOG["PENDING:Rugby-" + country] = country + " men · rugby (feed pending)"
for country in ("United States", "Japan"):
    CATALOG["PENDING:Baseball-" + country] = country + " · baseball (feed pending)"

def catalog_group(key):
    prefix, team = key.split(":", 1)
    groups = {
        "NFL": ("Football", "NFL"), "CFB": ("Football", "College football"),
        "NPB": ("Baseball", "NPB"), "MLB": ("Baseball", "MLB"), "CBASE": ("Baseball", "College baseball"),
        "NHL": ("Hockey", "NHL"), "CBB": ("Basketball", "College basketball"),
        "MLS": ("Soccer", "MLS"), "J1": ("Soccer", "J.League"),
        "NTSOC": ("Soccer", "Senior national teams"),
        "MLR": ("Rugby", "Major League Rugby"), "F1": ("Motorsport", "Formula 1"),
    }
    if prefix in groups:
        return groups[prefix]
    if team in ("Hanshin Tigers", "Hiroshima Carp"):
        return "Baseball", "NPB · feed pending"
    if team.startswith("Baseball-"):
        return "Baseball", "National teams · feed pending"
    if team.startswith("Rugby-"):
        return "Rugby", "National teams · feed pending"
    if team == "Seattle Orcas":
        return "Cricket", "Major League Cricket · feed pending"
    if team == "Geelong Cats":
        return "Australian football", "AFL · feed pending"
    if team == "CWU-basketball":
        return "Basketball", "College basketball"
    if team == "CWU-baseball":
        return "Baseball", "College baseball"
    return "Other", "Feed pending"


STARTING_FAVORITES = ["NFL:CLE", "NHL:SEA", "CFB:WASH", "CBB:WASH", "CBASE:WASH",
    "CFB:ARK", "CBB:ARK", "CBASE:ARK", "PENDING:Hanshin Tigers",
    "PENDING:Hiroshima Carp", "PENDING:CWU-football", "PENDING:CWU-basketball",
    "PENDING:CWU-baseball"]
NEW_FAVORITES = ["MLS:9726", "J1:7112", "PENDING:Seattle Orcas", "PENDING:Geelong Cats"]
NATIONAL_FAVORITES = ["NTSOC:660", "NTSOC:627", "PENDING:Rugby-United States",
    "PENDING:Rugby-Japan", "PENDING:Rugby-Ireland", "PENDING:Baseball-United States",
    "PENDING:Baseball-Japan"]

def load():
    try:
        settings = {**DEFAULT, **json.loads(CONFIG.read_text(encoding="utf-8"))}
        if not settings.get("favorites_seeded_v2"):
            settings["favorites"] = list(dict.fromkeys(settings["favorites"] + STARTING_FAVORITES))
            settings["favorites_seeded_v2"] = True
            save(settings)
        if not settings.get("favorites_seeded_v3"):
            settings["favorites"] = list(dict.fromkeys(settings["favorites"] + NEW_FAVORITES))
            settings["favorites_seeded_v3"] = True
            save(settings)
        if not settings.get("favorites_seeded_v4"):
            settings["favorites"] = list(dict.fromkeys(settings["favorites"] + NATIONAL_FAVORITES))
            settings["favorites_seeded_v4"] = True
            save(settings)
        if not settings.get("favorites_seeded_v5"):
            settings["favorites"] = list(dict.fromkeys(settings["favorites"] + ["MLR:142080"]))
            settings["favorites_seeded_v5"] = True
            save(settings)
        if not settings.get("favorites_seeded_v6"):
            settings["favorites"] = ["CFB:CWU" if key == "PENDING:CWU-football" else key
                                     for key in settings["favorites"]]
            settings["favorites"] = list(dict.fromkeys(settings["favorites"]))
            settings["favorites_seeded_v6"] = True
            save(settings)
        if not settings.get("palette_v1"):
            settings["background_color"] = "#0b1c2f"
            settings["palette_v1"] = True
            save(settings)
        migrated = list(dict.fromkeys(NPB_MIGRATION.get(key, key) for key in settings["favorites"]))
        if migrated != settings["favorites"]:
            settings["favorites"] = migrated
            save(settings)
        return settings
    except (OSError, ValueError):
        return {**DEFAULT, "favorites": DEFAULT["favorites"] + [NPB_MIGRATION.get(key, "CFB:CWU" if key == "PENDING:CWU-football" else key) for key in STARTING_FAVORITES]
                + NEW_FAVORITES + NATIONAL_FAVORITES + ["MLR:142080"],
                "favorites_seeded_v2": True, "favorites_seeded_v3": True, "favorites_seeded_v4": True,
                "favorites_seeded_v5": True, "favorites_seeded_v6": True, "palette_v1": True}

def save(settings):
    ROOT.mkdir(exist_ok=True)
    temp = CONFIG.with_suffix(".tmp")
    temp.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    temp.replace(CONFIG)

def get(url):
    # Some score endpoints reject non-browser user agents even for public JSON.
    request = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urllib.request.urlopen(request, timeout=12) as response:
        return json.load(response)

def get_text(url):
    request = urllib.request.Request(url, headers={"User-Agent": "SportsBug/0.2"})
    with urllib.request.urlopen(request, timeout=12) as response:
        return response.read().decode("utf-8-sig")

def iso(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))

def local_event_time(when, now=None):
    """Show Today for events on the viewer's local calendar day."""
    local = when.astimezone()
    today = (now or datetime.now(timezone.utc)).astimezone().date()
    return ("Today" if local.date() == today else local.strftime("%a %b %d")) + local.strftime(" · %H:%M")

def score_text(value):
    """Accept numeric scores, including ESPN's structured score objects."""
    if isinstance(value, dict):
        for field in ("displayValue", "value"):
            score = score_text(value.get(field))
            if score != "":
                return score
        return ""
    if value is None or isinstance(value, bool):
        return ""
    text = str(value).strip()
    if text.startswith("{"):
        # Earlier versions persisted score dictionaries as Python strings.
        try:
            return score_text(ast.literal_eval(text))
        except (ValueError, SyntaxError):
            return ""
    if re.fullmatch(r"\d+(?:\.0+)?", text):
        return text.partition(".")[0]
    return ""

def espn_schedule_score(value):
    score = score_text(value)
    if score != "" or not isinstance(value, dict):
        return score
    ref = value.get("$ref", "")
    parsed = urllib.parse.urlsplit(ref)
    if parsed.hostname not in ("sports.core.api.espn.com", "sports.core.api.espn.pvt"):
        return ""
    # Schedule responses sometimes contain ESPN's internal host name.
    url = urllib.parse.urlunsplit(("https", "sports.core.api.espn.com", parsed.path, parsed.query, ""))
    try:
        return score_text(get(url))
    except Exception:
        return ""

def item(key, league, left, right, when, state, status, a="", b="", teams=()):
    return dict(key=key, league=league, left=left, right=right, when=when,
                state=state, status=status, a=score_text(a), b=score_text(b), teams=list(teams))

def event_detail(event, hidden=False, now=None):
    """Two compact lines: score (including shootout), then game state."""
    state = event["state"]
    if state == "pre":
        return local_event_time(event["when"], now)
    if state == "window":
        return "Match window\nNo score yet"
    if state == "unverified":
        return "Update\nunavailable"
    if hidden:
        return "—\n" + ("FINAL" if state == "post" else "LIVE" if state == "in" else event["status"])
    a, b = score_text(event.get("a")), score_text(event.get("b"))
    score = a + "–" + b if a != "" and b != "" else ""
    status = event["status"]
    if state == "post":
        if not score:
            return "—\nFINAL · —"
        penalties = (score_text(event.get("pen_a")), score_text(event.get("pen_b")))
        if all(value != "" for value in penalties):
            score += " · PK " + penalties[0] + "–" + penalties[1]
            status = "FINAL"
        else:
            pk = re.search(r"\bPK\s*(\d+)\s*[-–]\s*(\d+)", status, re.I)
            if pk:
                score += " · PK " + pk[1] + "–" + pk[2]
                status = "FINAL"
            elif re.search(r"\b\d*OT\b|overtime", status, re.I):
                overtime = re.search(r"\b(\d*OT)\b", status, re.I)
                status = "FINAL · " + (overtime[1].upper() if overtime else "OT")
            elif re.search(r"extra time|\bAET\b", status, re.I):
                status = "FINAL · AET"
            elif not re.search(r"\b\d+ IN\b|\bSO\b|pen", status, re.I):
                status = "FINAL"
    return score + "\n" + status if score else status

def sport_label(event):
    """Use the sport, rather than INTL, for national-team event rows."""
    teams = event.get("teams", ())
    if event["league"] == "INTL" or any(t.startswith("NTSOC:") for t in teams):
        return "SOCCER"
    for prefix, label in (("NTBASE:", "BASEBALL"), ("NTRUGBY:", "RUGBY"),
                          ("NTHOCKEY:", "HOCKEY"),
                          ("PENDING:Baseball-", "BASEBALL"),
                          ("PENDING:Rugby-", "RUGBY"),
                          ("PENDING:Hockey-", "HOCKEY")):
        if any(t.startswith(prefix) for t in teams):
            return label
    return event["league"]

def followed_result(event):
    """Return the final result from the sole followed team's point of view."""
    if event.get("state") != "post" or len(event.get("teams", ())) != 1:
        return None
    try:
        away_score, home_score = int(event["a"]), int(event["b"])
    except (ValueError, TypeError, KeyError):
        return None
    if "pen_a" in event and "pen_b" in event:
        try:
            away_score, home_score = int(event["pen_a"]), int(event["pen_b"])
        except (ValueError, TypeError):
            return None
    elif "pen" in event.get("status", "").lower() or re.search(r"\bPK\b", event.get("status", ""), re.I):
        return None  # Match scores alone do not identify the shootout winner.
    favorite = event["teams"][0]
    league, _, code = favorite.partition(":")
    aliases = {"MLS:9726": ("SEA", "Seattle Sounders"),
               "J1:7112": ("KAW", "Kawasaki Frontale"),
               "NTSOC:660": ("USA", "United States"),
               "NTSOC:627": ("JPN", "JAP", "Japan"),
               "MLR:142080": ("Seattle Seawolves",),
               "CFB:CWU": ("CWU", "CWASH", "C WASH", "CENTWA", "Central Wash")}
    if favorite in aliases:
        names = aliases[favorite]
    elif league == "NPB":
        names = (NPB_CODES.get(code, ""),)
    elif league == "MLB":
        names = (MLB_CODES.get(code, ""),)
    elif league in ("NFL", "NHL", "CFB", "CBB", "CBASE"):
        names = (code,)
    else:
        names = ()
    def matches(side):
        normalized = "".join(c for c in side.casefold() if c.isalnum())
        return any(name and (normalized == "".join(c for c in name.casefold() if c.isalnum()) or
                            len(name) > 5 and "".join(c for c in name.casefold() if c.isalnum()) in normalized)
                   for name in names)
    away, home = matches(event["left"]), matches(event["right"])
    if away == home:
        return None
    own, opponent = (away_score, home_score) if away else (home_score, away_score)
    return "DRAW" if own == opponent else "WIN" if own > opponent else "LOSS"

def configure_windows_identity():
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SportsBug.Desktop")


def sportsbug_icon():
    icon_path = Path(__file__).resolve().with_name("SportsBug.ico")
    if icon_path.is_file():
        return QIcon(str(icon_path))
    image = QPixmap(64, 64)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#172b43"))
    painter.drawRoundedRect(3, 3, 58, 58, 13, 13)
    painter.setBrush(QColor("#55d994"))
    painter.drawEllipse(46, 8, 10, 10)
    painter.setPen(QColor("#f3f6fb"))
    font = QFont("Segoe UI", 20, QFont.Bold)
    painter.setFont(font)
    painter.drawText(image.rect(), Qt.AlignCenter, "SB")
    painter.end()
    return QIcon(image)

def visible_events(events, now, expanded, completed=None):
    live = sorted((e for e in events if e["state"] in ("in", "window", "starting", "unverified")), key=lambda e: e["when"])
    busy = {team for event in live for team in event.get("teams", ())}
    candidates = sorted((e for e in events if e["state"] == "pre"
                         and now <= e["when"] <= now + timedelta(days=7)
                         and not busy.intersection(e.get("teams", ()))),
                        key=lambda e: e["when"])
    upcoming, covered = [], set()
    for event in candidates:
        teams = set(event.get("teams", ())) or {event["key"]}
        if covered.isdisjoint(teams):
            upcoming.append(event)
            covered.update(teams)
    recent, finished_teams = [], set()
    for record in sorted((completed or {}).values(), key=lambda r: r.get("ended_at", 0), reverse=True):
        if record.get("superseded") or not 0 <= now.timestamp() - record["ended_at"] < 3 * 86400:
            continue
        event = dict(record["event"])
        event["when"] = iso(event["when"])
        teams = set(event.get("teams", ()))
        if teams.intersection(busy) or teams.intersection(finished_teams):
            continue
        recent.append(event)
        finished_teams.update(teams)
    return live + upcoming + recent

def refresh_delay_ms(events, now):
    if any(e["state"] in ("in", "window", "starting", "unverified") for e in events):
        return 60_000
    delay = timedelta(hours=12)
    for event in events:
        if event["state"] == "pre" and event["when"] > now:
            until_start = event["when"] - now
            wake = until_start - timedelta(minutes=5) if until_start > timedelta(minutes=5) else until_start
            delay = min(delay, wake)
    return max(10_000, int(delay.total_seconds() * 1000))

ESPN_PATHS = {"NFL": "football/nfl", "NHL": "hockey/nhl",
    "CFB": "football/college-football", "CBB": "basketball/mens-college-basketball",
    "CBASE": "baseball/college-baseball",
    "MLS": "soccer/usa.1", "J1": "soccer/jpn.1",
    "NTSOC_WORLD": "soccer/fifa.world", "NTSOC_FRIENDLY": "soccer/fifa.friendly"}

def live_status(status, league):
    kind = status.get("type", {})
    period = status.get("period", 0)
    detail = kind.get("shortDetail", "")
    if league in ("MLS", "J1", "NTSOC_WORLD", "NTSOC_FRIENDLY"):
        import re
        minute = re.search(r"\b(\d{1,3}(?:\+\d{1,2})?)\s*['’]", detail)
        return minute.group(0).strip() if minute else "LIVE"
    if league in ("NFL", "CFB", "CBB", "NHL") and period:
        if league in ("NFL", "CFB"):
            return "OT" if period > 4 else f"Q{period}"
        if league == "CBB":
            return "OT" if period > 2 else f"H{period}"
        return "OT" if period > 3 else f"P{period}"
    if league == "CBASE":
        import re
        match = re.search(r"\b(Top|Bottom|Mid|End)\s+(\d+)(?:st|nd|rd|th)?\b", detail, re.I)
        if match:
            return {"top": "TOP", "bottom": "BOT", "mid": "MID", "end": "END"}[match[1].lower()] + " " + match[2]
    return "LIVE"

def espn(league, favorites):
    favorite_prefix = "NTSOC:" if league.startswith("NTSOC_") else league + ":"
    if not any(f.startswith(favorite_prefix) for f in favorites):
        return []
    result = []
    now = datetime.now(timezone.utc)
    url = "https://site.api.espn.com/apis/site/v2/sports/" + ESPN_PATHS[league] + "/scoreboard"
    if league in ("CFB", "CBB", "CBASE"):
        start = (now - timedelta(days=4)).strftime("%Y%m%d")
        finish = (now + timedelta(days=12)).strftime("%Y%m%d")
        group = "80" if league == "CFB" else "50"
        url += "?" + urllib.parse.urlencode({"dates": start + "-" + finish,
                                               "groups": group, "limit": 500})
    elif league in ("NHL", "MLS", "J1", "NTSOC_WORLD", "NTSOC_FRIENDLY"):
        url += "?" + urllib.parse.urlencode({"dates": (now - timedelta(days=4)).strftime("%Y%m%d")
                    + "-" + (now + timedelta(days=10)).strftime("%Y%m%d")})
    data = get(url)
    for event in data.get("events", []):
        competitions = event.get("competitions") or []
        if not competitions:
            continue
        comp = competitions[0]
        teams = comp.get("competitors", [])
        when = iso(event["date"])
        if when < now - timedelta(days=4) or when > now + timedelta(days=21):
            continue
        state_info = event.get("status") or comp.get("status") or {}
        state = state_info.get("type", {}).get("state", "pre")
        status = state_info.get("type", {}).get("shortDetail", "")
        if state == "in":
            status = live_status(state_info, league)
        elif league in ("MLS", "J1", "NTSOC_FRIENDLY", "NTSOC_WORLD") and state == "pre" and when <= now < when + timedelta(hours=3):
            state, status = "window", "Match window · score unavailable"
        elif league in ("NFL", "CFB") and state == "pre" and when <= now < when + timedelta(hours=5):
            state, status = "window", "Game window · score unavailable"
        if league == "F1":
            if "F1:all" in favorites:
                result.append(item("F1:" + event["id"], "F1", event.get("shortName", event["name"]), "", when, state, status, teams=["F1:all"]))
        elif len(teams) >= 2:
            followed = set()
            for competitor in teams:
                team = competitor.get("team", {})
                candidates = {favorite_prefix + str(team.get("id", "")),
                              favorite_prefix + team.get("abbreviation", "")}
                if "Washington Huskies" in team.get("displayName", ""):
                    candidates.add(league + ":WASH")
                if "Arkansas Razorbacks" in team.get("displayName", ""):
                    candidates.add(league + ":ARK")
                if "Central Washington Wildcats" in team.get("displayName", ""):
                    candidates.add(league + ":CWU")
                followed.update(candidates.intersection(favorites))
            if not followed:
                continue
            away = next((t for t in teams if t.get("homeAway") == "away"), teams[0])
            home = next((t for t in teams if t.get("homeAway") == "home"), teams[-1])
            display_league = "SOCCER" if league.startswith("NTSOC_") else league
            key_league = "NTSOC" if league.startswith("NTSOC_") else league
            result.append(item(key_league + ":" + event["id"], display_league,
                away["team"].get("abbreviation") or away["team"].get("displayName", "Team"),
                home["team"].get("abbreviation") or home["team"].get("displayName", "Team"), when, state, status,
                away.get("score", ""), home.get("score", ""), teams=followed))
    return result

def soccer_team_schedule(league, favorites, code=None):
    """Check each followed club's fixtures when the league scoreboard is incomplete."""
    code = code or ("9726" if league == "MLS" else "7112" if league == "J1" else "660")
    favorite = ("NTSOC:" if league == "NTSOC_FRIENDLY" else league + ":") + code
    if favorite not in favorites:
        return []
    now = datetime.now(timezone.utc)
    url = ("https://site.api.espn.com/apis/site/v2/sports/" + ESPN_PATHS[league]
           + "/teams/" + code + "/schedule?" + urllib.parse.urlencode({"season": now.year}))
    data = get(url)
    result = []
    for event in data.get("events", []):
        when = iso(event["date"])
        if not now - timedelta(days=4) <= when <= now + timedelta(days=7):
            continue
        competition = (event.get("competitions") or [{}])[0]
        competitors = competition.get("competitors", [])
        if len(competitors) < 2 or not any(str(c.get("team", {}).get("id")) == code for c in competitors):
            continue
        away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[0])
        home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[-1])
        state_info = event.get("status") or competition.get("status") or {}
        state = state_info.get("type", {}).get("state", "pre")
        status = state_info.get("type", {}).get("shortDetail", "Scheduled")
        if state == "in":
            status = live_status(state_info, league)
        elif state == "pre" and when <= now < when + timedelta(hours=3):
            state, status = "window", "Match window · score unavailable"
        result.append(item(("NTSOC" if league.startswith("NTSOC") else league) + ":" + str(event["id"]),
            "SOCCER" if league.startswith("NTSOC") else league,
            away.get("team", {}).get("abbreviation") or away.get("team", {}).get("displayName", "Team"),
            home.get("team", {}).get("abbreviation") or home.get("team", {}).get("displayName", "Team"),
            when, state, status,
            espn_schedule_score(away.get("score", "")) if state in ("in", "post") else "",
            espn_schedule_score(home.get("score", "")) if state in ("in", "post") else "",
            teams=[favorite]))
    return result

def japan_senior_results(favorites, now=None):
    """Dated JFA-confirmed senior result when ESPN omits the Kirin Cup."""
    if "NTSOC:627" not in favorites:
        return []
    now = now or datetime.now(timezone.utc)
    kickoff = iso("2026-10-01T10:10:00+00:00")
    ended = iso("2026-10-01T13:10:00+00:00")
    if not ended <= now < ended + timedelta(days=3):
        return []
    event = item("fixture:NTSOC:627:2026-10-01", "SOCCER", "ECU", "JPN",
                 kickoff, "post", "FINAL · PK 4–5", 0, 0, teams=["NTSOC:627"])
    event.update(pen_a="4", pen_b="5")
    return [event]

def mlb(favorites):
    ids = {f.split(":", 1)[1] for f in favorites if f.startswith("MLB:")}
    if not ids:
        return []
    now = datetime.now(timezone.utc)
    begin = (now - timedelta(days=4)).date().isoformat()
    end = (now + timedelta(days=10)).date().isoformat()
    query = urllib.parse.urlencode({"sportId": 1, "startDate": begin, "endDate": end,
                                    "hydrate": "linescore"})
    data = get("https://statsapi.mlb.com/api/v1/schedule?" + query)
    result = []
    for day in data.get("dates", []):
        for game in day.get("games", []):
            away, home = game["teams"]["away"], game["teams"]["home"]
            if str(away["team"]["id"]) not in ids and str(home["team"]["id"]) not in ids:
                continue
            abstract = game["status"].get("abstractGameState", "Preview")
            state = {"Live": "in", "Final": "post"}.get(abstract, "pre")
            status = game["status"].get("detailedState", abstract)
            linescore = game.get("linescore", {})
            if state == "post" and linescore.get("currentInning", 0) > 9:
                status = "FINAL · " + str(linescore["currentInning"]) + " IN"
            if state == "in":
                inning = linescore.get("currentInning")
                phase = linescore.get("inningState", "").lower()
                status = (("TOP" if phase == "top" else "BOT" if phase == "bottom" else phase.upper())
                          + " " + str(inning)) if inning else "LIVE"
            result.append(item("MLB:" + str(game["gamePk"]), "MLB",
                MLB_CODES.get(str(away["team"]["id"]), away["team"]["name"]),
                MLB_CODES.get(str(home["team"]["id"]), home["team"]["name"]), iso(game["gameDate"]),
                state, status, away.get("score", ""), home.get("score", ""),
                teams={"MLB:" + str(side["team"]["id"]) for side in (away, home)}.intersection(favorites)))
    return result

def nhl(favorites):
    codes = {f.partition(":")[2] for f in favorites if f.startswith("NHL:")}
    results = {}
    now = datetime.now(timezone.utc)
    for code in codes:
        data = get("https://api-web.nhle.com/v1/club-schedule-season/" + code + "/now")
        for game in data.get("games", []):
            when = iso(game["startTimeUTC"])
            state_code = game.get("gameState", "FUT")
            state = "in" if state_code in ("LIVE", "CRIT") else "post" if state_code in ("OFF", "FINAL") else "pre"
            if state == "pre" and when <= now < when + timedelta(hours=4):
                state = "starting"
            if not (now - timedelta(days=4) <= when <= now + timedelta(days=7)) and state != "in":
                continue
            away, home = game.get("awayTeam", {}), game.get("homeTeam", {})
            period = game.get("periodDescriptor", {}).get("number")
            status = (("P" + str(period) if period else "LIVE") if state == "in" else
                      "FINAL" if state == "post" else "Awaiting puck drop" if state == "starting" else "Scheduled")
            if state == "post" and game.get("periodDescriptor", {}).get("periodType") in ("OT", "SO"):
                status = "FINAL · " + game["periodDescriptor"]["periodType"]
            event = item("NHL:" + str(game["id"]), "NHL", away.get("abbrev", "Away"), home.get("abbrev", "Home"),
                         when, state, status, away.get("score", ""), home.get("score", ""),
                         teams={"NHL:" + side.get("abbrev", "") for side in (away, home)}.intersection(favorites))
            results[event["key"]] = event
    return list(results.values())

def seawolves(favorites):
    if "MLR:142080" not in favorites:
        return []
    result = []
    now = datetime.now(timezone.utc)
    for endpoint in ("eventslast", "eventsnext"):
        data = get("https://www.thesportsdb.com/api/v1/json/123/" + endpoint + ".php?id=142080")
        for match in data.get("events") or []:
            timestamp = match.get("strTimestamp")
            if not timestamp:
                continue
            when = iso(timestamp.replace(" ", "T"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            home, away = match.get("intHomeScore"), match.get("intAwayScore")
            finished = home is not None and away is not None and when < now
            if not finished and when < now:
                continue  # An unscored past fixture is not a confirmed result.
            result.append(item("MLR:" + str(match["idEvent"]), "MLR",
                match.get("strAwayTeam") or "Away", match.get("strHomeTeam") or "Home",
                when, "post" if finished else "pre", "FINAL" if finished else "Scheduled",
                away if finished else "", home if finished else "", teams=["MLR:142080"]))
    return result

def eastern_kickoff(day, time_text):
    kickoff = datetime.strptime(day + " " + time_text, "%Y-%m-%d %H:%M")
    year = kickoff.year
    march_first = date(year, 3, 1)
    november_first = date(year, 11, 1)
    dst_start = date(year, 3, 1 + (6 - march_first.weekday()) % 7 + 7)
    dst_end = date(year, 11, 1 + (6 - november_first.weekday()) % 7)
    offset = -4 if dst_start <= kickoff.date() < dst_end else -5
    return kickoff.replace(tzinfo=timezone(timedelta(hours=offset))).astimezone(timezone.utc)

def nfl_schedule(favorites):
    codes = {f.partition(":")[2] for f in favorites if f.startswith("NFL:")}
    if not codes:
        return []
    cache = ROOT / "nfl-games.csv"
    # Refresh more often while a followed game could be in progress or just ended.
    cache_age_limit = 43200
    if cache.exists():
        try:
            cached_rows = csv.DictReader(io.StringIO(cache.read_text(encoding="utf-8-sig")))
            now = datetime.now(timezone.utc)
            if any(row.get("away_team") in codes or row.get("home_team") in codes
                   for row in cached_rows if row.get("gameday") == now.strftime("%Y-%m-%d")
                   or row.get("gameday") == (now - timedelta(days=1)).strftime("%Y-%m-%d")):
                cache_age_limit = 3600
        except OSError:
            pass
    if cache.exists() and datetime.now().timestamp() - cache.stat().st_mtime < cache_age_limit:
        content = cache.read_text(encoding="utf-8-sig")
    else:
        try:
            content = get_text("https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv")
            ROOT.mkdir(exist_ok=True)
            cache.write_text(content, encoding="utf-8")
        except Exception:
            if not cache.exists():
                raise
            content = cache.read_text(encoding="utf-8-sig")
    now = datetime.now(timezone.utc)
    results = []
    for row in csv.DictReader(io.StringIO(content)):
        away, home = row.get("away_team", ""), row.get("home_team", "")
        if away not in codes and home not in codes:
            continue
        try:
            when = eastern_kickoff(row["gameday"], row["gametime"])
        except (ValueError, KeyError, TypeError):
            continue
        if now - timedelta(days=3) <= when <= now + timedelta(days=7):
            scored = row.get("away_score", "").strip() and row.get("home_score", "").strip()
            if scored and now >= when + timedelta(hours=5):
                state, status = "post", "FINAL"
            elif when <= now < when + timedelta(hours=5):
                state, status = "window", "Game window · score unavailable"
            elif when > now:
                state, status = "pre", "Scheduled"
            else:
                continue
            results.append(item("NFL:" + row.get("game_id", row["gameday"] + away + home),
                                "NFL", away, home, when, state, status,
                                row.get("away_score", "") if state == "post" else "",
                                row.get("home_score", "") if state == "post" else "",
                                teams={"NFL:" + away, "NFL:" + home}.intersection(favorites)))
    return results

# Confirmed 2026 kickoffs from the three schools' published football schedules.
# These are start times only; add later dates after schools announce firm times.
COLLEGE_KICKOFFS = (
    ("CFB:WASH", "2026-09-27T03:00:00+00:00", "MINN", "WASH"),
    ("CFB:ARK", "2026-09-27T00:00:00+00:00", "TULSA", "ARK"),
    ("CFB:CWU", "2026-09-27T01:00:00+00:00", "SRSU", "CWU"),
    ("CFB:WASH", "2026-10-03T23:30:00+00:00", "WASH", "USC"),
    ("CFB:ARK", "2026-10-03T23:00:00+00:00", "ARK", "TAMU"),
    ("CFB:CWU", "2026-10-03T23:00:00+00:00", "CWU", "ASU"),
    ("CFB:WASH", "2026-10-10T01:00:00+00:00", "IOWA", "WASH"),
    ("CFB:CWU", "2026-10-11T01:00:00+00:00", "MSU", "CWU"),
)

def ncaa_football(favorites, now=None, only_division=None):
    now = now or datetime.now(timezone.utc)
    followed = set(favorites).intersection(("CFB:WASH", "CFB:ARK", "CFB:CWU"))
    if not followed:
        return []
    # NCAA's season week 1 runs into early September; subsequent Thursdays
    # begin the next scoreboard week.
    eastern_day = (now - timedelta(hours=4)).date()
    first_thursday = date(now.year, 9, 1)
    first_thursday += timedelta(days=(3 - first_thursday.weekday()) % 7)
    week = max(1, (eastern_day - first_thursday).days // 7 + 1)
    result = []
    for division, wanted in (("fbs", followed - {"CFB:CWU"}),
                             ("d2", followed.intersection({"CFB:CWU"}))):
        if not wanted or (only_division is not None and only_division != division):
            continue
        # A finished Saturday game can move to the previous scoreboard week
        # after the weekly rollover; retain access to its final for three days.
        entries = []
        failures = []
        for requested_week in {max(1, week - 1), week}:
            url = "https://ncaa-api.henrygd.me/scoreboard/football/" + division + "/" + str(now.year) + "/" + f"{requested_week:02d}" + "/all-conf"
            try:
                data = get(url)
                if not isinstance(data.get("games"), list):
                    raise ValueError("NCAA scoreboard returned no games list")
                entries.extend(data["games"])
            except Exception as exc:
                failures.append(exc)
        if not entries and failures:
            raise failures[-1]
        for entry in entries:
            game = entry.get("game", entry)
            home, away = game.get("home", {}), game.get("away", {})
            names = [side.get("names", {}) for side in (home, away)]
            names = [{k: str(v).lower() for k, v in values.items()} for values in names]
            all_names = {v for side in names for v in side.values()}
            match = set()
            if division == "fbs" and {"washington", "washington huskies", "washington-huskies"}.intersection(all_names):
                match.add("CFB:WASH")
            if division == "fbs" and {"arkansas", "arkansas razorbacks", "arkansas-razorbacks"}.intersection(all_names):
                match.add("CFB:ARK")
            if division == "d2" and any("central wash" in name for name in all_names):
                match.add("CFB:CWU")
            match.intersection_update(wanted)
            if not match:
                continue
            epoch = game.get("startTimeEpoch")
            if epoch:
                epoch = float(epoch)
                when = datetime.fromtimestamp(epoch / 1000 if epoch > 1e12 else epoch, timezone.utc)
            else:
                known = next((iso(start) for favorite, start, left, right in COLLEGE_KICKOFFS
                              if favorite in match and
                              (left.lower() in all_names or right.lower() in all_names)), None)
                if known is None:
                    continue
                when = known
            state = {"live": "in", "final": "post"}.get(str(game.get("gameState", "")).lower(), "pre")
            period = str(game.get("currentPeriod") or "").strip()
            status = (period or "LIVE") if state == "in" else "FINAL" if state == "post" else "Scheduled"
            if state == "in" and period.isdigit():
                status = "Q" + period
            elif state == "pre" and when <= now < when + timedelta(hours=5):
                state, status = "window", "Game window · score unavailable"
            short = lambda side: side.get("names", {}).get("char6") or side.get("names", {}).get("short") or "Team"
            result.append(item("NCAA:" + str(game.get("gameID") or when.isoformat() + short(away)),
                               "CFB", short(away), short(home), when, state, status,
                               away.get("score", ""), home.get("score", ""), teams=match))
    return result

def college_schedule(favorites, existing, now=None):
    now = now or datetime.now(timezone.utc)
    result = []
    for favorite, start, away, home in COLLEGE_KICKOFFS:
        when = iso(start)
        if favorite not in favorites or not (now <= when <= now + timedelta(days=7)
                                            or when <= now < when + timedelta(hours=5)):
            continue
        # A working score feed takes precedence over a schedule-only entry.
        if any(favorite in event.get("teams", ()) and
               abs((event["when"] - when).total_seconds()) < 12 * 3600
               for event in existing):
            continue
        started = when <= now
        result.append(item("schedule:" + favorite + ":" + when.date().isoformat(),
                           "CFB", away, home, when, "window" if started else "pre",
                           "Game window · score unavailable" if started else "Scheduled", teams=[favorite]))
    return result

F1_SESSIONS = (("SprintQualifying", "Sprint Qualifying", 2),
               ("Sprint", "Sprint", 1), ("Qualifying", "Qualifying", 2),
               ("Race", "Race", 4))

def f1_schedule(favorites, now=None):
    if "F1:all" not in favorites:
        return []
    now = now or datetime.now(timezone.utc)
    data = get("https://api.jolpi.ca/ergast/f1/" + str(now.year) + "/races/?limit=100")
    result = []
    for race in data.get("MRData", {}).get("RaceTable", {}).get("Races", []):
        name = race["raceName"].replace(" Grand Prix", " GP")
        for field, label, hours in F1_SESSIONS:
            session = race if field == "Race" else race.get(field)
            if not session or not session.get("time"):
                continue
            when = iso(session["date"] + "T" + session["time"])
            if not now - timedelta(hours=hours) <= when <= now + timedelta(days=7):
                continue
            key = "F1:" + str(race["season"]) + ":" + str(race["round"]) + ":" + field
            running = when <= now < when + timedelta(hours=hours)
            result.append(item(key, "F1", name + " · " + label, "", when,
                               "window" if running else "pre",
                               "Scheduled session" if running else "Scheduled", teams=["F1:all"]))
    return result

def parse_npb_schedule(text, favorites, now=None):
    """Read release CSV; finals require the source's completed state and scores."""
    now = now or datetime.now(timezone.utc)
    rows = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    required = {"game_id", "game_date", "game_state", "home_team_id", "away_team_id",
                "home_score", "away_score"}
    if not required.issubset(rows.fieldnames or ()):
        raise ValueError("NPB schedule format changed")
    result = []
    for row in rows:
        home, away = row["home_team_id"], row["away_team_id"]
        if home not in NPB_TEAMS or away not in NPB_TEAMS:
            continue  # All-star and undecided playoff teams are not selectable clubs.
        teams = [key for key in ("NPB:" + away, "NPB:" + home) if key in favorites]
        if not teams or row["game_state"] not in ("1", "2", "3"):
            continue  # Cancelled games (state 4) must not appear as upcoming or final.
        try:
            when = iso(row["game_date"])
        except ValueError:
            continue
        if when.tzinfo is None:
            continue
        if not now - timedelta(days=4) <= when <= now + timedelta(days=7):
            continue
        a, b = score_text(row["away_score"]), score_text(row["home_score"])
        if row["game_state"] == "2" and a != "" and b != "":
            state, status = "post", "FINAL"
        elif when > now and row["game_state"] == "1":
            state, status = "pre", "Scheduled"
            a = b = ""
        elif when <= now < when + timedelta(hours=8):
            # This periodically published dataset is not a verified live feed.
            state, status = "window", "Match window · awaiting result"
            a = b = ""
        else:
            continue
        result.append(item("NPB:" + row["game_id"], "NPB", NPB_CODES[away], NPB_CODES[home],
                           when, state, status, a, b, teams))
    return result


def npb_schedule(favorites):
    year = (datetime.now(timezone.utc) + timedelta(hours=9)).year
    # The maintainer updates release assets; committed files may be historical.
    url = NPB_REPOSITORY + "/releases/download/schedule/" + str(year) + "_npb_schedule.csv"
    return parse_npb_schedule(get_text(url), favorites)


class Fetcher(QThread):
    complete = Signal(list, list)
    def __init__(self, favorites):
        super().__init__()
        self.favorites = favorites[:]
    def run(self):
        events, errors = [], []
        jobs = {league: (lambda league=league: espn(league, self.favorites))
                for league in ESPN_PATHS if league != "NHL" and any(f.startswith(("NTSOC:" if league.startswith("NTSOC_") else league + ":")) for f in self.favorites)}
        if any(f.startswith("MLB:") for f in self.favorites):
            jobs["MLB"] = lambda: mlb(self.favorites)
        if any(f.startswith("NFL:") for f in self.favorites):
            jobs["NFL-schedule"] = lambda: nfl_schedule(self.favorites)
        if any(f.startswith("NHL:") for f in self.favorites):
            jobs["NHL"] = lambda: nhl(self.favorites)
        if any(f.startswith("NPB:") for f in self.favorites):
            jobs["NPB"] = lambda: npb_schedule(self.favorites)
        if "MLR:142080" in self.favorites:
            jobs["MLR"] = lambda: seawolves(self.favorites)
        if "F1:all" in self.favorites:
            jobs["F1"] = lambda: f1_schedule(self.favorites)
        if any(f in self.favorites for f in ("CFB:WASH", "CFB:ARK")):
            jobs["NCAA-FBS"] = lambda: ncaa_football(self.favorites, only_division="fbs")
        if "CFB:CWU" in self.favorites:
            jobs["NCAA-D2"] = lambda: ncaa_football(self.favorites, only_division="d2")
        for league, code in (("MLS", "9726"), ("J1", "7112"),
                             ("NTSOC_FRIENDLY", "660"), ("NTSOC_FRIENDLY", "627")):
            favorite = ("NTSOC:" if league == "NTSOC_FRIENDLY" else league + ":") + code
            if favorite in self.favorites:
                jobs[league + "-team-" + code] = lambda league=league, code=code: soccer_team_schedule(league, self.favorites, code)
        if jobs:
            with ThreadPoolExecutor(max_workers=min(4, len(jobs))) as pool:
                pending = {pool.submit(job): league for league, job in jobs.items()}
                for future in as_completed(pending):
                    try:
                        events.extend(future.result())
                    except Exception as exc:
                        errors.append(pending[future] + ": " + str(exc))
        for confirmed in japan_senior_results(self.favorites):
            matching = [event for event in events if "NTSOC:627" in event.get("teams", ())
                        and abs((event["when"] - confirmed["when"]).total_seconds()) < 12 * 3600]
            if matching:
                confirmed["key"] = matching[0]["key"]
                events = [event for event in events if event not in matching]
            events.append(confirmed)
        # Confirmed kickoff is a last-resort backup if both NFL requests omit
        # this game. It never pretends to have a live score.
        now = datetime.now(timezone.utc)
        for favorite, away, home, away_score, home_score in (
                ("NFL:SEA", "SEA", "WAS", 31, 33),
                ("NFL:CLE", "CAR", "CLE", 18, 21)):
            kickoff = iso("2026-09-27T17:00:00+00:00")
            if favorite in self.favorites and kickoff - timedelta(days=7) <= now <= kickoff + timedelta(days=3):
                # Team-published results for these two fixtures override an old
                # schedule row. The normal score feed remains the live source.
                finished = now >= kickoff + timedelta(hours=5)
                if finished or not any(favorite in e.get("teams", ()) and
                           abs((e["when"] - kickoff).total_seconds()) < 12 * 3600 for e in events):
                    events.append(item("confirmed:" + favorite + ":2026-09-27", "NFL", away, home, kickoff,
                        "post" if finished else "window" if now >= kickoff else "pre",
                        "FINAL" if finished else "Game window · score unavailable" if now >= kickoff else "Scheduled",
                        away_score if finished else "", home_score if finished else "", teams=[favorite]))
        # Prefer the ESPN score feed if both score sources report the same game.
        events = [event for event in events if not (event["key"].startswith("NCAA:") and
                  any(other["key"].startswith("CFB:") and
                      set(other.get("teams", ())).intersection(event.get("teams", ())) and
                      abs((other["when"] - event["when"]).total_seconds()) < 12 * 3600
                      for other in events))]
        # Both soccer endpoints can describe the same match; keep the league
        # scoreboard version, then use a club fixture only when it adds a match.
        unique = {}
        for event in events:
            unique.setdefault(event["key"], event)
        events = list(unique.values())
        # Published club fixtures cover matches outside ESPN's league feed.
        club_fixtures = (
            ("MLS:9726", "2026-09-27T00:30:00+00:00", "MIN", "SEA", "MLS", "confirmed-without-score"),
            ("MLS:9726", "2026-10-02T01:30:00+00:00", "SKC", "SEA", "MLS", None),
            ("J1:7112", "2026-09-29T10:03:00+00:00", "RSK", "KAW", "J Cup", (0, 1)),
            ("NTSOC:660", "2026-09-26T20:30:00+00:00", "PER", "USA", "SOCCER", (1, 4)),
            ("NTSOC:660", "2026-09-30T00:00:00+00:00", "CHI", "USA", "SOCCER", None),
        )
        now = datetime.now(timezone.utc)
        for favorite, start, away, home, league, confirmed_final in club_fixtures:
            when = iso(start)
            if favorite not in self.favorites or not now - timedelta(days=3) <= when <= now + timedelta(days=7):
                continue
            elapsed = now - when
            confirmed_score = isinstance(confirmed_final, tuple) and elapsed >= timedelta(hours=3)
            if any((event["state"] == "post" and event["a"] != "" and event["b"] != ""
                    if confirmed_score else event["state"] in ("in", "post", "window"))
                   and favorite in event.get("teams", ()) and
                   abs((event["when"] - when).total_seconds()) < 12 * 3600 for event in events):
                continue
            if elapsed < timedelta(0):
                state, status = "pre", "Scheduled"
            elif confirmed_final is not None and elapsed >= timedelta(hours=2 if confirmed_final == "confirmed-without-score" else 3):
                state, status = "post", "FINAL" if isinstance(confirmed_final, tuple) else "Final · score unavailable"
            elif elapsed < timedelta(hours=3):
                state, status = "window", "Match window · score unavailable"
            else:
                continue
            events.append(item("fixture:" + favorite + ":" + when.date().isoformat(),
                               league, away, home, when, state, status,
                               *(confirmed_final if state == "post" and isinstance(confirmed_final, tuple) else ("", "")),
                               teams=[favorite]))
        events.extend(college_schedule(self.favorites, events))
        self.complete.emit(events, errors)

def release_repository(settings):
    configured = settings.get("update_repository", "").strip()
    if not configured:
        try:
            configured = json.loads(Path(__file__).with_name("release.json").read_text())["repository"]
        except (OSError, ValueError, KeyError):
            return ""
    return configured if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", configured) else ""


def version_tuple(value):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", value)
    if not match:
        raise ValueError("Release version must use vMAJOR.MINOR.PATCH")
    return tuple(map(int, match.groups()))


class UpdateChecker(QThread):
    complete = Signal(object, str)
    def __init__(self, repository):
        super().__init__()
        self.repository = repository
    def run(self):
        try:
            request = urllib.request.Request(
                "https://api.github.com/repos/" + self.repository + "/releases/latest",
                headers={"User-Agent": "SportsBug/" + VERSION,
                         "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(request, timeout=15) as response:
                release = json.load(response)
            latest = release["tag_name"]
            newer = version_tuple(latest) > version_tuple(VERSION)
            assets = release.get("assets", [])
            url = next((a["browser_download_url"] for a in assets
                        if a.get("name") == "SportsBug-Setup.exe"), "")
            if newer and (not url.startswith("https://github.com/" + self.repository + "/releases/download/")):
                raise ValueError("The latest release has no SportsBug installer yet")
            self.complete.emit({"version": latest, "newer": newer, "url": url}, "")
        except Exception as error:
            self.complete.emit(None, str(error))


class FittingLabel(QLabel):
    """Keep event text inside its fixed row, shrinking only when necessary."""
    def __init__(self, text):
        super().__init__(text)
        self.text_style = ""
        self.setWordWrap(True)

    def set_text_style(self, style):
        self.text_style = style
        self.fit_text()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_text()

    def fit_text(self):
        area = self.contentsRect()
        if area.width() <= 0 or area.height() <= 0:
            return
        flags = int(Qt.TextWordWrap | Qt.AlignLeft)
        for size in range(12, 6, -1):
            font = QFont("Segoe UI")
            font.setPixelSize(size)
            font.setBold("700" in self.text_style)
            bounds = QFontMetrics(font).boundingRect(
                QRect(0, 0, area.width(), 10000), flags, self.text())
            if bounds.height() <= area.height() and bounds.width() <= area.width():
                break
        style = self.text_style + f"font-size:{size}px;"
        if self.styleSheet() != style:
            self.setStyleSheet(style)


class ResizeHandle(QLabel):
    def __init__(self, bug):
        super().__init__("", bug)
        self.bug = bug
        self.origin = None
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(16)
        self.setCursor(Qt.SizeVerCursor)
        self.setToolTip("Drag down for more events; drag up to make the widget shorter")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.origin = (event.globalPosition().toPoint().y(), self.bug.height())
            event.accept()

    def mouseMoveEvent(self, event):
        if self.origin and event.buttons() & Qt.LeftButton:
            screen = self.bug.screen().availableGeometry()
            minimum = self.bug.minimumHeight()
            max_height = max(minimum, screen.bottom() - self.bug.y() + 1)
            height = self.origin[1] + event.globalPosition().toPoint().y() - self.origin[0]
            self.bug.resize(self.bug.width(), max(minimum, min(max_height, height)))
            event.accept()

    def mouseReleaseEvent(self, event):
        if self.origin:
            self.origin = None
            self.bug.settings["height"] = self.bug.height()
            self.bug.persist()
            event.accept()

class Bug(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = load()
        self.events, self.errors, self.drag = [], [], None
        self.last_checked = None
        self.next_refresh_at = None
        self.last_calendar_check = datetime.now().astimezone().date()
        self.diagnostics = None
        # Keep normal taskbar minimize/restore behavior with a borderless window.
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window |
                            Qt.WindowSystemMenuHint | Qt.WindowMinimizeButtonHint)
        self.setWindowTitle("SportsBug")
        self.setWindowIcon(sportsbug_icon())
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumWidth(310)
        self.setMinimumHeight(140)
        self.move(self.settings["x"], self.settings["y"])
        self.apply_top()
        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(0, 0, 0, 0)
        self.panel = QWidget()
        self.panel.setObjectName("panel")
        self.context_menu_on(self.panel)
        self.outer.addWidget(self.panel)
        self.box = QVBoxLayout(self.panel)
        self.box.setContentsMargins(14, 12, 14, 0)
        self.box.setSpacing(6)
        header = QHBoxLayout()
        header.addStretch()
        self.reload = QPushButton("↻")
        self.reload.setToolTip("Refresh scores now")
        self.reload.clicked.connect(self.refresh)
        header.addWidget(self.reload)
        self.spoil = QPushButton("◉")
        self.spoil.setToolTip("Toggle spoiler mode")
        self.spoil.clicked.connect(self.toggle_spoilers)
        header.addWidget(self.spoil)
        self.top_button = QPushButton("○")
        self.top_button.clicked.connect(lambda: self.set_top(not self.settings["top"]))
        header.addWidget(self.top_button)
        gear = QPushButton("⚙")
        gear.setToolTip("Favorites and window settings")
        gear.clicked.connect(self.options)
        header.addWidget(gear)
        self.expand = QPushButton("⌄")
        self.expand.setToolTip("Show individual reveal buttons while spoiler mode is on")
        self.expand.clicked.connect(self.toggle_expand)
        header.addWidget(self.expand)
        for button in (self.reload, self.spoil, self.top_button, gear, self.expand):
            button.setFixedSize(30, 30)
        header.setSpacing(4)
        self.box.addLayout(header)
        self.event_scroll = QScrollArea()
        self.event_scroll.setWidgetResizable(True)
        self.event_scroll.setFrameShape(QScrollArea.NoFrame)
        self.event_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.event_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.event_scroll.setMinimumHeight(EVENT_ROW_HEIGHT)
        self.event_container = QWidget()
        self.body = QVBoxLayout(self.event_container)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(1)
        self.event_scroll.setWidget(self.event_container)
        self.context_menu_on(self.event_container)
        self.context_menu_on(self.event_scroll.viewport())
        self.box.addWidget(self.event_scroll, 1)
        self.footer = QLabel("Loading scores…")
        self.footer.setObjectName("muted")
        self.footer.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.context_menu_on(self.footer)
        self.box.addWidget(self.footer)
        handle = ResizeHandle(self)
        self.context_menu_on(handle)
        self.box.addWidget(handle)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.check_refresh_clock)
        self.heartbeat = QTimer(self)
        self.heartbeat.timeout.connect(self.check_refresh_clock)
        self.heartbeat.start(30_000)
        QApplication.instance().applicationStateChanged.connect(self.check_refresh_clock)
        self.resize(350, self.settings.get("height", 230))
        self.render()
        QTimer.singleShot(0, self.update_minimum_height)
        QTimer.singleShot(0, self.refresh)
        if self.settings.get("check_updates_on_launch", True):
            QTimer.singleShot(1500, lambda: self.check_updates(False))

    def update_minimum_height(self):
        # Measure the actual header, footer and margins after Qt lays them out.
        chrome = self.height() - self.event_scroll.viewport().height()
        self.setMinimumHeight(max(140, chrome + EVENT_ROW_HEIGHT))

    def persist(self):
        self.settings["x"], self.settings["y"] = self.x(), self.y()
        save(self.settings)

    def context_menu_on(self, widget):
        widget.setContextMenuPolicy(Qt.CustomContextMenu)
        widget.customContextMenuRequested.connect(
            lambda point, target=widget: self.show_context_menu(target.mapToGlobal(point)))

    def show_context_menu(self, position):
        menu = QMenu(self)
        menu.addAction("Refresh now", self.refresh)
        menu.addAction("Settings", self.options)
        menu.addSeparator()
        menu.addAction("Quit SportsBug", self.close)
        menu.exec(position)

    def closeEvent(self, event):
        if getattr(self, "worker", None) and self.worker.isRunning():
            event.ignore()
            self.hide()
            self.worker.finished.connect(QApplication.instance().quit)
            if not self.worker.isRunning():
                QApplication.instance().quit()
        else:
            event.accept()

    def apply_top(self):
        state = self.windowState()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.settings["top"])
        self.setWindowState(state)
        self.show()

    def restore_from_taskbar(self):
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.show()
        self.raise_()
        self.activateWindow()

    def nativeEvent(self, event_type, message):
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x0112:  # WM_SYSCOMMAND
                command = int(msg.wParam) & 0xFFF0
                if command == 0xF020:  # SC_MINIMIZE, including taskbar clicks
                    self.showMinimized()
                    return True, 0
                if command == 0xF120:  # SC_RESTORE
                    QTimer.singleShot(0, self.restore_from_taskbar)
                    return True, 0
        return super().nativeEvent(event_type, message)

    def changeEvent(self, event):
        if event.type() == QEvent.ActivationChange and self.isActiveWindow():
            self.raise_()
        super().changeEvent(event)

    def refresh(self):
        if getattr(self, "worker", None) and self.worker.isRunning():
            return
        self.reload.setEnabled(False)
        self.footer.setText("Refreshing…")
        self.worker = Fetcher(self.settings["favorites"])
        self.worker.complete.connect(self.updated)
        self.worker.start()

    def check_refresh_clock(self, *args):
        now = datetime.now(timezone.utc)
        local = now.astimezone()
        calendar_due = (local.date() != self.last_calendar_check and
                        (local.hour, local.minute) >= (0, 1))
        if calendar_due:
            self.last_calendar_check = local.date()
            # Update local date labels immediately, even if a feed fails or a
            # request is already running. The heartbeat also catches waking up
            # after midnight; no continuously running network task is needed.
            self.render()
        if calendar_due or (self.next_refresh_at and now >= self.next_refresh_at):
            self.refresh()

    def updated(self, events, errors):
        self.reload.setEnabled(True)
        now = datetime.now(timezone.utc)
        failed = {message.partition(":")[0] for message in errors}
        if failed:
            carried = set()
            for previous in self.events:
                same_game = any((previous["key"] == current["key"] or
                                 (previous["league"] == current["league"] and
                                  previous["left"] == current["left"] and
                                  previous["right"] == current["right"] and
                                  abs((previous["when"] - current["when"]).total_seconds()) < 12 * 3600) or
                                 (set(previous.get("teams", ())).intersection(current.get("teams", ())) and
                                  abs((previous["when"] - current["when"]).total_seconds()) < 12 * 3600))
                                and current["state"] in ("in", "post", "window") for current in events)
                if previous["league"] in failed and previous["state"] in ("in", "starting", "unverified"):
                    if not same_game and previous["key"] not in carried and now - previous["when"] < timedelta(hours=8):
                        events.append({**previous, "state": "unverified", "status": "Update unavailable"})
                        carried.add(previous["key"])
        # Old releases could accumulate identical fallback rows in memory.
        distinct = {}
        for event in events:
            original = distinct.get(event["key"])
            if original is None or (original["state"] == "unverified" and event["state"] != "unverified"):
                distinct[event["key"]] = event
        events = list(distinct.values())
        # ESPN and NCAA use different IDs for the same college match. Prefer
        # a current live/final record over any stale copy of that matchup.
        ranking = {"post": 4, "in": 3, "window": 2, "starting": 1, "unverified": 0}
        grouped = []
        for event in sorted(events, key=lambda e: ranking.get(e["state"], 1), reverse=True):
            if any(event["league"] == prior["league"] and
                   event["left"] == prior["left"] and event["right"] == prior["right"] and
                   abs((event["when"] - prior["when"]).total_seconds()) < 12 * 3600
                   for prior in grouped):
                continue
            grouped.append(event)
        events = grouped
        self.events = events
        stamp = now.timestamp()
        old = self.settings.get("completed", {})
        finals = {key: dict(value) for key, value in old.items()
                  if 0 <= stamp - value.get("ended_at", 0) < 3 * 86400}
        seen = {key: value for key, value in self.settings.get("seen_live", {}).items()
                if 0 <= stamp - value < 4 * 86400}
        live = [event for event in events if event["state"] == "in"]
        for record in finals.values():
            previous = record["event"]
            if any(set(previous.get("teams", ())).intersection(current.get("teams", ()))
                   and iso(previous["when"]) < current["when"] for current in live):
                record["superseded"] = True
        for event in events:
            if event["state"] == "in":
                seen[event["key"]] = stamp
            elif event["state"] == "post":
                if event["key"] not in finals and event["key"] not in old:
                    # Feeds rarely include a finish timestamp. For finals first seen
                    # after a restart, estimate it from the scheduled start.
                    hours = {"MLB": 3, "NPB": 3, "NFL": 3.5, "NHL": 2.5}.get(event["league"], 2)
                    ended = stamp if event["key"] in seen else min(stamp, (event["when"] + timedelta(hours=hours)).timestamp())
                    if 0 <= stamp - ended < 3 * 86400:
                        snapshot = {**event, "when": event["when"].isoformat()}
                        finals[event["key"]] = {"ended_at": ended, "event": snapshot}
                elif event["key"] in finals:
                    finals[event["key"]]["event"] = {**event, "when": event["when"].isoformat()}
                seen.pop(event["key"], None)
        if finals != old or seen != self.settings.get("seen_live", {}):
            self.settings["completed"] = finals
            self.settings["seen_live"] = seen
            self.persist()
        self.errors = errors
        self.last_checked = datetime.now()
        if self.diagnostics is not None:
            self.diagnostics.setPlainText(self.feed_status())
        self.render()
        delay = refresh_delay_ms(self.events, now)
        self.next_refresh_at = datetime.now(timezone.utc) + timedelta(milliseconds=delay)
        self.timer.start(delay)

    def feed_status(self):
        if self.errors:
            return "\n".join(self.errors)
        if self.last_checked is None:
            return "No check completed yet."
        return "No feed errors on the last check (" + self.last_checked.strftime("%H:%M") + ")."

    def clear(self):
        while self.body.count():
            child = self.body.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def render(self):
        self.clear()
        s = self.settings
        self.spoil.setText("◉" if s["spoilers"] else "◎")
        self.spoil.setToolTip("Spoiler mode ON (click to show all scores)" if s["spoilers"] else "Scores visible (click to hide)")
        self.top_button.setText("●" if s["top"] else "○")
        self.top_button.setToolTip("Always on top ON (click to turn off)" if s["top"] else "Always on top OFF (click to turn on)")
        self.top_button.setAccessibleName("Always on top")
        self.expand.setText("⌃" if s["expanded"] else "⌄")
        alpha = round(s["opacity"] * 2.55)
        background = QColor(s.get("background_color", "#0b1c2f"))
        if not background.isValid():
            background = QColor("#0b1c2f")
        self.panel.setStyleSheet("QWidget {background: transparent; color:#f3f6fb; font: 12px 'Segoe UI';}"
          "QWidget#panel {background: rgba(%d,%d,%d,%d); border: 1px solid #404b5b; border-radius: 16px;}" % (background.red(), background.green(), background.blue(), alpha)
          + "QPushButton {border:0; background:transparent; color:#c9d5e9; font-size:18px; padding:2px 5px;}"
          + "QPushButton:hover {color:white; background:#40506b; border-radius:7px;}"
          + "QLabel#muted {color:#9aacc3; font-size:10px;}")
        now = datetime.now(timezone.utc)
        events = visible_events(self.events, now, s["expanded"], s.get("completed", {}))
        for event in events:
            event = {**event, "a": score_text(event.get("a")), "b": score_text(event.get("b"))}
            hidden = s["spoilers"] and event["key"] not in s["revealed"]
            line = QWidget()
            line.setFixedHeight(EVENT_ROW_HEIGHT)
            self.context_menu_on(line)
            row = QHBoxLayout(line)
            row.setContentsMargins(2, 7, 2, 7)
            row.setSpacing(6)
            outcome = None if hidden else followed_result(event)
            badge = QLabel({"WIN": "W", "LOSS": "L", "DRAW": "T"}.get(outcome, ""))
            badge.setFixedSize(22, 22)
            badge.setAlignment(Qt.AlignCenter)
            badge.setToolTip({"WIN": "Win", "LOSS": "Loss", "DRAW": "Tie"}.get(outcome, ""))
            self.context_menu_on(badge)
            sport = sport_label(event)
            label = FittingLabel(("SOC" if sport == "SOCCER" else sport) + "   " + event["left"] + ("  @  " + event["right"] if event["right"] else ""))
            self.context_menu_on(label)
            label.setWordWrap(True)
            label.setMaximumWidth(210)
            row.addWidget(label, 1)
            if outcome:
                badge.setStyleSheet({
                    "WIN": "color:#3af888; background-color:#0f243c;",
                    "LOSS": "color:#ffaaa6; background-color:#0f243c;",
                    "DRAW": "color:#c7d1df; background-color:#0f243c;",
                }[outcome] + "border-radius:4px; font-size:9px; font-weight:700; padding:3px 0;")
            detail = FittingLabel(event_detail(event, hidden, now))
            detail.setFixedWidth(140 if event["state"] == "pre" else 112)
            detail.setWordWrap(True)
            detail.setToolTip("" if hidden else ("Final · score unavailable" if event["state"] == "post" and (event["a"] == "" or event["b"] == "") else event["status"]))
            self.context_menu_on(detail)
            if event["state"] == "pre" and event["when"].astimezone().date() > now.astimezone().date():
                detail.set_text_style("color: #9aacc3;")
            elif event["state"] == "in":
                detail.set_text_style("color: #55d994; font-weight: 700;")
            elif event["state"] == "post" and not hidden:
                detail.set_text_style("color: #f6c877; font-weight: 700;")
            detail.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(detail)
            if s["expanded"] and s["spoilers"] and event["state"] not in ("pre", "window", "starting", "unverified"):
                eye = QPushButton("◌" if hidden else "●")
                eye.setToolTip("Reveal this event" if hidden else "Hide this event")
                eye.clicked.connect(lambda checked=False, key=event["key"]: self.toggle_event(key))
                row.addWidget(eye)
            if event["state"] != "pre":
                row.addWidget(badge, 0, Qt.AlignVCenter)
            self.body.addWidget(line)
        if not events:
            empty = QLabel("No favorites playing in the next 7 days.")
            empty.setFixedHeight(EVENT_ROW_HEIGHT)
            self.context_menu_on(empty)
            self.body.addWidget(empty)
        self.body.addStretch(1)
        self.footer.setText("Checked " + self.last_checked.strftime("%H:%M") if self.last_checked else "Waiting for first check…")
        self.footer.setToolTip("")

    def toggle_spoilers(self):
        self.settings["spoilers"] = not self.settings["spoilers"]
        self.settings["revealed"] = []
        self.persist()
        self.render()

    def toggle_event(self, key):
        revealed = self.settings["revealed"]
        if key in revealed:
            revealed.remove(key)
        else:
            revealed.append(key)
        self.persist()
        self.render()

    def toggle_expand(self):
        self.settings["expanded"] = not self.settings["expanded"]
        self.persist()
        self.render()

    def check_updates(self, manual=True):
        if getattr(self, "update_worker", None) and self.update_worker.isRunning():
            return
        repository = release_repository(self.settings)
        if not repository:
            if manual:
                QMessageBox.information(self, "SportsBug updates",
                    "Enter the GitHub repository in Settings first (owner/SportsBug).")
            return
        self.update_status = "Checking for updates…"
        self.update_worker = UpdateChecker(repository)
        self.update_worker.complete.connect(lambda result, error: self.update_checked(result, error, manual))
        self.update_worker.start()
        self.sync_update_status()

    def sync_update_status(self):
        label = getattr(self, "update_status_label", None)
        if label is not None:
            label.setText(getattr(self, "update_status", "Version " + VERSION))

    def update_checked(self, result, error, manual):
        if error:
            self.update_status = "Update check failed: " + error
            if manual:
                QMessageBox.information(self, "SportsBug updates", self.update_status)
        elif result["newer"]:
            self.update_status = "Version " + result["version"] + " is available."
            answer = QMessageBox.question(self, "SportsBug update available",
                self.update_status + "\nDownload the installer? Run it to update your installed app.")
            if answer == QMessageBox.Yes:
                QDesktopServices.openUrl(QUrl(result["url"]))
        else:
            self.update_status = "You’re up to date (" + VERSION + ")."
            if manual:
                QMessageBox.information(self, "SportsBug updates", self.update_status)
        self.sync_update_status()

    def options(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("SportsBug settings")
        dialog.resize(440, 720)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Choose favorites"))
        search = QLineEdit()
        search.setPlaceholderText("Search team, league, or school")
        layout.addWidget(search)
        tree = QTreeWidget()
        tree.setHeaderHidden(True)
        tree.setMinimumHeight(180)
        sports, leagues, entries = {}, {}, []
        for key, name in sorted(CATALOG.items(), key=lambda pair: (*catalog_group(pair[0]), pair[1])):
            sport, league = catalog_group(key)
            if sport not in sports:
                sports[sport] = QTreeWidgetItem(tree, [sport])
            if (sport, league) not in leagues:
                leagues[sport, league] = QTreeWidgetItem(sports[sport], [league])
            display_name = name.split(" · ", 1)[0]
            if key.startswith("PENDING:"):
                display_name += " · pending"
            elif key == "CFB:CWU":
                display_name += " · schedule only"
            entry = QTreeWidgetItem(leagues[sport, league], [display_name])
            entry.setData(0, Qt.UserRole, key)
            entry.setToolTip(0, name)
            entry.setFlags(entry.flags() | Qt.ItemIsUserCheckable)
            entry.setCheckState(0, Qt.Checked if key in self.settings["favorites"] else Qt.Unchecked)
            entries.append((entry, key, name, sport, league))
        def selection_changed(entry, column):
            key = entry.data(0, Qt.UserRole)
            if key:
                self.favorite(key, entry.checkState(0) == Qt.Checked)
        tree.itemChanged.connect(selection_changed)
        def filter_teams(value):
            query = value.strip().casefold()
            for entry, key, name, sport, league in entries:
                entry.setHidden(query not in (name + " " + sport + " " + league).casefold())
            for branch in leagues.values():
                branch.setHidden(all(branch.child(i).isHidden() for i in range(branch.childCount())))
                branch.setExpanded(bool(query))
            for branch in sports.values():
                branch.setHidden(all(branch.child(i).isHidden() for i in range(branch.childCount())))
                branch.setExpanded(bool(query))
        search.textChanged.connect(filter_teams)
        layout.addWidget(tree, 1)
        notice = QLabel("“Pending” teams are saved favorites but have no connected feed yet. Central Washington football has schedule coverage. National soccer covers senior men’s World Cup and friendlies.")
        notice.setWordWrap(True)
        layout.addWidget(notice)
        top = QCheckBox("Always on top")
        top.setChecked(self.settings["top"])
        top.toggled.connect(self.set_top)
        layout.addWidget(top)
        snap = QCheckBox("Snap near screen edges")
        snap.setChecked(self.settings["snap"])
        snap.toggled.connect(lambda enabled: self.set_setting("snap", enabled))
        layout.addWidget(snap)
        color_row = QHBoxLayout()
        color_button = QPushButton("Background color…")
        reset_color = QPushButton("Reset color")
        def update_color_button():
            color_button.setText("Background color · " + self.settings["background_color"].upper())
        def choose_color():
            color = QColorDialog.getColor(QColor(self.settings["background_color"]), dialog,
                                          "Choose SportsBug background")
            if color.isValid():
                self.set_setting("background_color", color.name())
                update_color_button()
                self.render()
        def restore_color():
            self.set_setting("background_color", DEFAULT["background_color"])
            update_color_button()
            self.render()
        color_button.clicked.connect(choose_color)
        reset_color.clicked.connect(restore_color)
        update_color_button()
        color_row.addWidget(color_button)
        color_row.addWidget(reset_color)
        layout.addLayout(color_row)
        layout.addWidget(QLabel("Background opacity"))
        slider = QSlider(Qt.Horizontal)
        slider.setRange(30, 100)
        slider.setValue(self.settings["opacity"])
        slider.valueChanged.connect(lambda value: (self.set_setting("opacity", value), self.render()))
        layout.addWidget(slider)
        layout.addWidget(QLabel("Updates · version " + VERSION))
        repository = QLineEdit(release_repository(self.settings))
        repository.setPlaceholderText("GitHub repository: owner/SportsBug")
        repository.editingFinished.connect(lambda: self.set_setting("update_repository", repository.text().strip()))
        layout.addWidget(repository)
        automatic = QCheckBox("Automatically check for updates on launch")
        automatic.setChecked(self.settings.get("check_updates_on_launch", True))
        automatic.toggled.connect(lambda enabled: self.set_setting("check_updates_on_launch", enabled))
        layout.addWidget(automatic)
        update_button = QPushButton("Check for updates")
        update_button.clicked.connect(lambda: (self.set_setting("update_repository", repository.text().strip()), self.check_updates(True)))
        layout.addWidget(update_button)
        self.update_status_label = QLabel(getattr(self, "update_status", ""))
        self.update_status_label.setWordWrap(True)
        layout.addWidget(self.update_status_label)
        attribution = QLabel("This uses data sourced from the Nippon Baseball Data Repository, "
                             'which can be accessed <a href="' + NPB_REPOSITORY + '">here</a>.<br>'
                             "NPB: schedules and published results; live tracking unverified.")
        attribution.setWordWrap(True)
        attribution.setOpenExternalLinks(True)
        layout.addWidget(attribution)
        layout.addWidget(QLabel("Feed status"))
        self.diagnostics = QPlainTextEdit()
        self.diagnostics.setReadOnly(True)
        self.diagnostics.setMaximumHeight(80)
        self.diagnostics.setPlainText(self.feed_status())
        layout.addWidget(self.diagnostics)
        close = QPushButton("Close")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()
        self.diagnostics = None
        self.update_status_label = None
        self.refresh()

    def favorite(self, key, enabled):
        fav = self.settings["favorites"]
        if enabled and key not in fav:
            fav.append(key)
        elif not enabled and key in fav:
            fav.remove(key)
        self.persist()

    def set_setting(self, key, value):
        self.settings[key] = value
        self.persist()

    def set_top(self, enabled):
        self.set_setting("top", enabled)
        self.apply_top()
        self.render()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.position().y() < 42:
            self.drag = event.globalPosition().toPoint() - self.pos()
    def mouseMoveEvent(self, event):
        if self.drag is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag)
    def mouseReleaseEvent(self, event):
        if self.drag is not None:
            if self.settings["snap"]:
                bounds = self.screen().availableGeometry()
                x, y = self.x(), self.y()
                if abs(x - bounds.left()) < 24: x = bounds.left()
                if abs(x + self.width() - bounds.right()) < 24: x = bounds.right() - self.width()
                if abs(y - bounds.top()) < 24: y = bounds.top()
                if abs(y + self.height() - bounds.bottom()) < 24: y = bounds.bottom() - self.height()
                self.move(x, y)
            self.drag = None
            self.persist()

if __name__ == "__main__":
    configure_windows_identity()
    app = QApplication(sys.argv)
    app.setWindowIcon(sportsbug_icon())
    app.setQuitOnLastWindowClosed(True)
    bug = Bug()
    sys.exit(app.exec())
