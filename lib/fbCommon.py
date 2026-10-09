# -*- coding: utf-8 -*-
"""
Created on Mon Aug 14 10:38:58 2023

@author: ntrup

Football helpers shared by the gtpdd scripts.

Avoids matplotlib, and imports PIL only inside the logo helpers, so scripts that
only need schedules and scores stay light. Paths are repo-relative, so run
scripts from the repo root.
"""

####
# IMPORTS
####

import csv
import json
import os
from datetime import date, datetime
from html import escape as html_escape
from zoneinfo import ZoneInfo

import cfbd
import numpy as np
import requests
import pandas as pd
from dateutil import parser, tz
from dotenv import load_dotenv

####
# CONSTANTS
####

# Absolute path to the repo, one level up from lib/
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ESPN_TEAM_IDS_CSV = 'csv/espnTeamIDs.csv'
VENUES_CACHE = 'csv/cfbdVenues.json'
TEAM_COLORS_CSV = 'csv/fbPlaychartPBP/fbPlaychartTeamColors.csv'
LOGO_DIR = 'logo'                  # team logo cache shared by every gtpdd script
ESPN_LOGO_URL = 'https://a.espncdn.com/i/teamlogos/ncaa/500/{}.png'
# Games with an unknown venue are assumed to be on Central time, like most Tech games
DEFAULT_TIMEZONE = 'America/Chicago'


####
# ESPN FEEDS
####

def getFBSchedule(teamID):
    # Returns a team's ESPN schedule as a DataFrame, plus its record summary
    from_zone = tz.tzutc()

    schedule_url = 'https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams/'+ teamID + '/schedule'
    r = requests.get(schedule_url)
    x = r.json()

    record = x['team']['recordSummary']

    # Collect each game's id, UTC kickoff, and away/home team ids
    gameIDs = []
    dates = []
    away = []
    home = []
    for game in x['events']:
        gameIDs.append(game['id'])
        z_date = game['date']
        z_datetime = parser.parse(z_date)
        utc = z_datetime.replace(tzinfo=from_zone)
        dates.append(utc)
        away.append(game['competitions'][0]['competitors'][0]['team']['id'])
        home.append(game['competitions'][0]['competitors'][1]['team']['id'])


    df = pd.DataFrame({'gameID': gameIDs,'date': dates, 'away':away, 'home':home})
    return df, record


def getTeamInfo(teamID):
    # Returns a team's (location name, primary color, alternate color) from ESPN
    url = 'https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams/'+ teamID
    r = requests.get(url)
    x = r.json()

    name = x['team']['location']
    color1 = x['team']['color']
    color2 = x['team']['alternateColor']

    return name, color1, color2


def lookupEspnId(name, team_id_csv=ESPN_TEAM_IDS_CSV):
    # Looks up a team or conference's ESPN id in the saved CSV, or None if missing
    if not os.path.isfile(team_id_csv):
        return None
    with open(team_id_csv, newline='') as f:
        for row in csv.reader(f):
            if len(row) >= 2 and row[0].strip().lower() == str(name).strip().lower():
                return row[1].strip()
    return None


# ESPN's full college football team directory
ESPN_TEAMS_URL = ('https://site.api.espn.com/apis/site/v2/sports/football/'
                  'college-football/teams?limit=1000')


def resolveEspnId(name, team_id_csv=ESPN_TEAM_IDS_CSV):
    # Finds a team's ESPN id in the saved CSV, else in ESPN's directory (saving it to the CSV)
    found = lookupEspnId(name, team_id_csv)
    if found is not None:
        return found
    try:
        payload = requests.get(ESPN_TEAMS_URL, timeout=30).json()
        entries = payload['sports'][0]['leagues'][0]['teams']
    except Exception as e:
        print(f"Could not fetch ESPN's team directory ({type(e).__name__}: {e}).")
        return None

    # Match the name against any of ESPN's names for each team
    wanted = str(name).strip().lower()
    for entry in entries:
        team = entry.get('team') or {}
        aliases = {str(team.get(k) or '').strip().lower()
                   for k in ('location', 'displayName', 'shortDisplayName', 'name')}
        if wanted in aliases and team.get('id'):
            team_id = str(team['id'])
            # Save the match so later runs find it on disk
            with open(team_id_csv, 'a', newline='') as f:
                csv.writer(f).writerow([name, team_id])
            print(f"Learned ESPN id {team_id} for '{name}'; saved to {team_id_csv}.")
            return team_id
    print(f"ESPN's directory has no team called '{name}'.")
    return None


####
# CFBD FEEDS
####

def cfbdApi(apiClass):
    # Returns a CFBD client, e.g. cfbdApi(cfbd.GamesApi), using cfbdAuth from the env or .env
    token = os.environ.get('cfbdAuth')
    # Fall back to the repo's .env if the key isn't already in the environment
    if not token:
        load_dotenv(os.path.join(REPO_ROOT, '.env'))
        token = os.environ.get('cfbdAuth')
    if not token:
        raise RuntimeError("No cfbdAuth in the environment or in .env at the repo root.")
    return apiClass(cfbd.ApiClient(cfbd.Configuration(access_token=token)))


def loadVenues(refresh=False, cache_path=VENUES_CACHE):
    # Returns venue id -> city/state/timezone/capacity/dome, cached on disk
    if not refresh and os.path.isfile(cache_path):
        try:
            with open(cache_path) as f:
                return {int(k): v for k, v in json.load(f).items()}
        except (ValueError, OSError):
            pass  # unreadable cache: pull a fresh copy below
    try:
        venues = cfbdApi(cfbd.VenuesApi).get_venues()
    except Exception as e:
        print(f"Could not fetch venues from CFBD ({type(e).__name__}: {e}).")
        return {}
    # Keep only the fields the scripts use, then write the cache
    table = {v.id: {'city': v.city, 'state': v.state, 'timezone': v.timezone,
                    'capacity': v.capacity, 'dome': v.dome}
             for v in venues if v.id is not None}
    os.makedirs(os.path.dirname(cache_path) or '.', exist_ok=True)
    with open(cache_path, 'w') as f:
        json.dump(table, f, indent=2, sort_keys=True)
    return table


def getGames(year, team, season_type='both'):
    # Returns a team's CFBD games for a season, oldest first, or [] on failure
    try:
        games = cfbdApi(cfbd.GamesApi).get_games(year=year, team=team, season_type=season_type)
    except Exception as e:
        print(f"Could not fetch {year} games for '{team}' from CFBD ({type(e).__name__}: {e}).")
        return []
    # Games with no start date sort last
    return sorted(games, key=lambda g: (g.start_date is None, g.start_date))


####
# DATES & TIMES
####

def localDateTime(when, timezone=None, fallback=DEFAULT_TIMEZONE):
    # Converts a UTC kickoff to local time at the venue
    if when is None:
        return None
    zone = timezone
    # Midnight UTC means no known kickoff time, so skip the fallback to avoid shifting the date
    if not zone and (when.hour, when.minute) != (0, 0):
        zone = fallback
    if not zone:
        return when
    try:
        return when.astimezone(ZoneInfo(zone))
    except Exception:
        return when  # unknown zone: UTC is close enough for the date and the clock


def gameDateTime(info, fallback=DEFAULT_TIMEZONE):
    # Returns local kickoff for a flattened game record ('startDate' + 'timezone'), or None
    iso = (info or {}).get('startDate')
    if not iso:
        return None
    try:
        when = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None
    return localDateTime(when, info.get('timezone'), fallback)


def currentSeason(today=None):
    # Seasons run August into January, so Jan-Feb still count as the previous year's season
    today = today or date.today()
    return today.year if today.month >= 3 else today.year - 1


def gameDateText(when):
    # Formats as 'Sep 3, 1988' (day placed by hand since %-d isn't portable)
    return None if when is None else f"{when:%b} {when.day}, {when.year}"


def kickoffText(info, fallback=DEFAULT_TIMEZONE):
    # Formats as 'Saturday, August 30, 2025 • 6:30 PM CDT' in the venue's local time
    when = gameDateTime(info, fallback)
    if when is None:
        return None
    day = f"{when:%A, %B} {when.day}, {when.year}"
    # TBD kickoffs show the date only
    if info.get('startTimeTbd'):
        return day
    # %-I isn't portable, so strip the hour's leading zero by hand
    clock = f"{when:%I:%M %p}".lstrip('0')
    zone = when.strftime('%Z')
    return f"{day} • {clock} {zone}".rstrip()


####
# COLORS
####

def loadColors(path):
    # Loads a JSON color file
    with open(path) as f:
        return json.load(f)


def hexLuminance(hex_color):
    # Perceived brightness (0-255) of a #RRGGBB color; lower is darker
    h = str(hex_color).lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 0.299 * r + 0.587 * g + 0.114 * b


def whiteToBlack(hex_color):
    # Swaps a white team color for black so it shows up on charts
    h = str(hex_color).lstrip('#').lower()
    if h in ('fff', 'ffffff'):
        return '#000000'
    return hex_color


def loadTeamColorsCsv(path):
    # Returns team (lowercased) -> {'pass': ..., 'run': ...} from the saved color CSV
    table = {}
    if not os.path.isfile(path):
        return table
    with open(path, newline='') as f:
        for row in csv.DictReader(f):
            name = (row.get('team') or '').strip()
            if name:
                table[name.lower()] = {'pass': (row.get('passColor') or '').strip(),
                                       'run': (row.get('runColor') or '').strip()}
    return table


def appendTeamColors(team, pass_color, run_color, path):
    # Adds one team to the color CSV, writing the header if the file is new
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    is_new = not os.path.isfile(path)
    with open(path, 'a', newline='') as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(['team', 'passColor', 'runColor'])
        writer.writerow([team, pass_color, run_color])


def fetchTeamColors(team, team_id_csv=ESPN_TEAM_IDS_CSV):
    # Returns a team's (darker, lighter) ESPN colors, or None if the team can't be found
    team_id = resolveEspnId(team, team_id_csv)
    if team_id is None:
        print(f"No ESPN id for '{team}' in {team_id_csv}.")
        return None
    try:
        _, color1, color2 = getTeamInfo(str(team_id))
    except Exception as e:
        print(f"Could not fetch ESPN colors for '{team}' ({type(e).__name__}: {e}).")
        return None
    c1 = whiteToBlack('#' + str(color1).lstrip('#'))
    c2 = whiteToBlack('#' + str(color2).lstrip('#'))
    # Order darkest first
    try:
        return tuple(sorted((c1, c2), key=hexLuminance))
    except (ValueError, IndexError):
        return c1, c2  # non-hex color: keep color1/color2 order


# Placeholder pass/run colors for a team ESPN can't supply
FALLBACK_TEAM_COLORS = {'pass': '#4d4d4d', 'run': '#a6a6a6'}


def teamColors(team, path=TEAM_COLORS_CSV):
    # Returns a team's {'pass': ..., 'run': ...} chart colors from the saved CSV
    entry = loadTeamColorsCsv(path).get(str(team).strip().lower())
    # New teams get ESPN's colors (or a placeholder) and are saved for next time
    if entry is None:
        fetched = fetchTeamColors(team)
        if fetched is None:
            entry = dict(FALLBACK_TEAM_COLORS)
            print(f"Wrote placeholder colors for '{team}' to {path} — edit that row to fix them.")
        else:
            entry = {'pass': fetched[0], 'run': fetched[1]}
            print(f"Added '{team}' to {path}: pass={entry['pass']}, run={entry['run']}")
        appendTeamColors(team, entry['pass'], entry['run'], path)
    return entry


####
# LOGOS
####

def downloadLogo(url, path, name):
    # Downloads a logo to path; returns True on success
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'wb') as f:
            f.write(response.content)
        print(f"Saved {name} logo to {path}")
        return True
    except Exception as e:
        print(f"Could not fetch the logo for '{name}' ({type(e).__name__}: {e}).")
        return False


def trimmedLogo(path):
    # Opens a cached logo as RGBA, cropped to its artwork so every logo sizes alike
    from PIL import Image
    try:
        img = Image.open(path).convert('RGBA')
        bbox = img.split()[3].getbbox()
        return img.crop(bbox) if bbox else img
    except Exception as e:
        print(f"Could not read {path} ({type(e).__name__}: {e}).")
        return None


def teamLogo(name, box):
    # Returns a team's ESPN logo as an RGBA array no larger than box x box, or None
    from PIL import Image
    path = os.path.join(LOGO_DIR, f"{name}.png")
    # Download into the cache on first use
    if not os.path.isfile(path):
        espn_id = resolveEspnId(name)
        if espn_id is None or not downloadLogo(ESPN_LOGO_URL.format(espn_id), path, name):
            return None
    img = trimmedLogo(path)
    if img is None:
        return None
    img.thumbnail((box, box), Image.LANCZOS)
    return np.asarray(img)


####
# SITE PUBLISHING
####

def assetSlug(name):
    # 'Louisiana Tech' -> 'Louisiana_Tech', so published file names need no URL escaping
    import re
    return re.sub(r'[^0-9A-Za-z]+', '_', str(name)).strip('_')


def previewMetaTags(title, description, page_url, image_url=None, twitter_handle=None):
    # Builds link-preview meta tags: twitter:* for X, og:* for everyone else
    tags = [('name', 'title', title),
            ('name', 'description', description),
            ('name', 'twitter:card', 'summary_large_image')]
    if twitter_handle:
        tags += [('name', 'twitter:site', twitter_handle),
                 ('name', 'twitter:creator', twitter_handle)]
    tags += [('name', 'twitter:title', title),
             ('name', 'twitter:description', description),
             ('property', 'og:type', 'website'),
             ('property', 'og:title', title),
             ('property', 'og:description', description),
             ('property', 'og:url', page_url)]
    if image_url:
        tags += [('name', 'twitter:image', image_url), ('property', 'og:image', image_url)]
    # One escaped <meta> tag per line
    return ''.join(f'<meta {attr}="{name}" content="{html_escape(value, quote=True)}" />\n'
                   for attr, name, value in tags)


def publishAsset(src, web_dir, link_prefix=''):
    # Copies an asset into the published site folder; returns its page-relative link
    if not os.path.isfile(src):
        print(f"Missing {src}; the page will do without it.")
        return None
    os.makedirs(web_dir, exist_ok=True)
    dest = os.path.join(web_dir, os.path.basename(src))
    # Only copy when the source is newer than the published copy
    if not os.path.isfile(dest) or os.path.getmtime(src) > os.path.getmtime(dest):
        import shutil
        shutil.copyfile(src, dest)
    return link_prefix + os.path.basename(web_dir) + '/' + os.path.basename(src)


def loadYears(base_dir, current=None):
    # Returns available seasons (four-digit subfolders of base_dir), newest first
    import re
    years = set()
    listing = os.listdir(base_dir) if os.path.isdir(base_dir) else []
    for fn in listing:
        if re.fullmatch(r'\d{4}', fn) and os.path.isdir(os.path.join(base_dir, fn)):
            years.add(int(fn))
    # Always include the current season, even before it has a folder
    if current is not None:
        years.add(int(current))
    return sorted(years, reverse=True)


def writeJsGlobal(path, name, data, indent=1, header=None, dumps=None):
    # Writes data as 'window.<name> = <json>;' so pages can load it as a script, even over file://
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    # A custom dumps lets callers lay out the JSON by hand, e.g. one record per line
    body = dumps(data) if dumps else json.dumps(data, indent=indent)
    with open(path, 'w') as f:
        if header:
            f.write(header.rstrip('\n') + '\n')
        f.write(f"window.{name} = " + body + ";\n")
    return path


def readJsGlobal(path, name):
    # Reads back a writeJsGlobal file by parsing its JSON; None if the file is missing
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        text = f.read()
    marker = f"window.{name} ="
    if marker not in text:
        raise ValueError(f"{path} does not assign window.{name}")
    # Strip the assignment and trailing semicolon to leave the JSON
    body = text.split(marker, 1)[1].rsplit(';', 1)[0]
    return json.loads(body)
