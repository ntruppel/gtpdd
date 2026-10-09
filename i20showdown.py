# -*- coding: utf-8 -*-
"""
Builds html/i20showdown/, the scoreboard for the I-20 Showdown: Louisiana Tech vs
ULM across 12 sports, one point each (ties split), first to 6.5 wins and a 6-6
split goes to the football winner.

Head-to-head results come from the latechsports.com schedule pages. Conference
finishes (cross country, golf, track) are entered by hand in CONFERENCE_RESULTS,
since the site doesn't list ULM's place. Templates live in lib/html/i20showdown/.

Run from the repo root:

    python i20showdown.py                # current academic year
    python i20showdown.py --year 2026    # the 2026-27 series
    python i20showdown.py --dry-run      # print the standings, write nothing
    python i20showdown.py --refresh      # refetch the schedules instead of using cached pages
"""

####
# IMPORTS
####

import json
import os
import re
import shutil
from datetime import date, datetime
from html import escape
from string import Template
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw, ImageFont

from lib.common import copyMissingFiles

####
# SCRIPT VARIABLES
####

# Where the finished page is published; link previews need absolute URLs
SITE_URL = 'https://i20showdown.com'
# Athletics site every schedule is read from
SITE = 'https://latechsports.com'
# Where the finished page is written
OUT_DIR = 'html/i20showdown'
# The page skeleton and stylesheet this script fills in and copies next to the finished page
TEMPLATE_DIR = 'lib/html/i20showdown'
PAGE_TEMPLATE = os.path.join(TEMPLATE_DIR, 'index.html')
PAGE_CSS = os.path.join(TEMPLATE_DIR, 'style.css')
# Hand-made site files (images, fonts, favicon), copied to the page folder when missing
STATIC_DIR = os.path.join(TEMPLATE_DIR, 'static')
# 2026-27 was the inaugural year, so the default year never goes earlier
FIRST_SERIES = 2026
# The "Updated" time on the page is shown in Central time
TIMEZONE = ZoneInfo('America/Chicago')
# Schedule pages are cached here between runs, so repeated builds don't refetch the same pages
CACHE_DIR = 'tmp/i20showdown'
CACHE_HOURS = 6
# Requests identify as a normal desktop browser
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'}

# Names used for a sport's winner, plus the score that wins the series
TECH = 'Louisiana Tech'
ULM = 'ULM'
POINTS_TO_WIN = 6.5

####
# IMAGES
####

# Every image lives in html/i20showdown/img/ and is referenced by its page-relative path
IMG_DIR = 'img'
TECH_LOGO = f'{IMG_DIR}/latech.png'
ULM_LOGO = f'{IMG_DIR}/ulm.png'
# The gtpdd logo at the foot of the page, linking back home (a 480px copy of img/gtpdd_logo.png)
GTPDD_LOGO = f'{IMG_DIR}/gtpdd_logo.png'
GTPDD_HOME = 'https://gtpdd.dog'
# Browser-tab and home-screen icons, the same ones gtpdd.dog uses
GTPDD_ICON = f'{IMG_DIR}/gtpdd_icon_32.png'
GTPDD_ICON_LARGE = f'{IMG_DIR}/gtpdd_icon_192.png'
GTPDD_TOUCH_ICON = f'{IMG_DIR}/gtpdd_icon_180.png'
# The same icon at the site root (16/32/48px), for anything that only ever asks for /favicon.ico
FAVICON = 'favicon.ico'
# Interstate 20 shield, public domain, from Wikimedia Commons
I20_SHIELD = f'{IMG_DIR}/I-20.svg'
# The same shield as a PNG, since Pillow can't draw SVG (rendered once with macOS Quick Look)
I20_SHIELD_PNG = f'{IMG_DIR}/I-20.png'
# The link-preview card for X/Twitter and everyone else, redrawn with the score on every build
PREVIEW = 'preview.png'
PREVIEW_SIZE = (1200, 630)
# Sport icons are Material Design Icons (Apache-2.0), saved in img/ as mdi-<name>.svg
ICON_CREDIT = ('Material Design Icons', 'https://pictogrammers.com/library/mdi/')
I20_CREDIT = ('Wikimedia Commons', 'https://commons.wikimedia.org/wiki/File:I-20.svg')
# Overpass, an open-source take on the Highway Gothic lettering of interstate signs (SIL OFL 1.1)
ROAD_FONT = 'fonts/overpass-latin.woff2'
FONT_CREDIT = ('Overpass', 'https://github.com/RedHatOfficial/Overpass')
# Doto, a font drawn out of dots, for the message board (SIL OFL 1.1)
BOARD_FONT = 'fonts/doto-latin.woff2'
BOARD_FONT_CREDIT = ('Doto', 'https://github.com/oliverlalan/Doto')

####
# SPORTS
####

# One entry per point, fall to spring; kind 'h2h' scores games vs ULM, 'conf' scores a conference finish
SPORTS = [
    {'key': 'football', 'icon': 'football', 'name': 'Football', 'short': 'Football', 'slug': 'football', 'season': 'fall', 'kind': 'h2h'},
    {'key': 'volleyball', 'icon': 'volleyball', 'name': 'Volleyball', 'short': 'Volleyball', 'slug': 'womens-volleyball', 'season': 'fall', 'kind': 'h2h'},
    {'key': 'soccer', 'icon': 'soccer', 'name': "Women's Soccer", 'short': 'Soccer', 'slug': 'womens-soccer', 'season': 'fall', 'kind': 'h2h'},
    {'key': 'xc-men', 'icon': 'run', 'name': "Men's Cross Country", 'short': 'M. Cross Country', 'slug': 'cross-country', 'season': 'fall', 'kind': 'conf', 'gender': 'M'},
    {'key': 'xc-women', 'icon': 'run', 'name': "Women's Cross Country", 'short': 'W. Cross Country', 'slug': 'cross-country', 'season': 'fall', 'kind': 'conf', 'gender': 'W'},
    {'key': 'mbb', 'icon': 'basketball', 'name': "Men's Basketball", 'short': 'M. Basketball', 'slug': 'mens-basketball', 'season': 'winter', 'kind': 'h2h'},
    {'key': 'wbb', 'icon': 'basketball', 'name': "Women's Basketball", 'short': 'W. Basketball', 'slug': 'womens-basketball', 'season': 'winter', 'kind': 'h2h'},
    {'key': 'tf-men', 'icon': 'run-fast', 'name': "Men's Track & Field", 'short': 'M. Track & Field', 'slug': 'track-and-field', 'season': 'winter', 'kind': 'conf', 'gender': 'M'},
    {'key': 'tf-women', 'icon': 'run-fast', 'name': "Women's Track & Field", 'short': 'W. Track & Field', 'slug': 'track-and-field', 'season': 'winter', 'kind': 'conf', 'gender': 'W'},
    {'key': 'golf', 'icon': 'golf', 'name': "Men's Golf", 'short': 'Golf', 'slug': 'mens-golf', 'season': 'winter', 'kind': 'conf'},
    {'key': 'baseball', 'icon': 'baseball', 'name': 'Baseball', 'short': 'Baseball', 'slug': 'baseball', 'season': 'spring', 'kind': 'h2h'},
    {'key': 'softball', 'icon': 'baseball-bat', 'name': 'Softball', 'short': 'Softball', 'slug': 'softball', 'season': 'spring', 'kind': 'h2h'},
]

####
# CONFERENCE RESULTS (ENTERED BY HAND)
####

# Conference points entered by hand (the site lacks ULM's finish), by year and sport key, as in the example below
CONFERENCE_RESULTS = {
    # 2026: {'xc-men': {'winner': TECH, 'techFinish': '2nd', 'ulmFinish': '9th'}},
}


####
# SCHEDULE SCRAPING
####

def seasonSlug(season, year):
    # Fall seasons are named for their start year, winter both years, and spring their end year
    return {'fall': str(year),
            'winter': f'{year}-{str(year + 1)[-2:]}',
            'spring': str(year + 1)}[season]


def pageHtmlText(url, refresh=False):
    # A schedule page, from the cache when it's fresh enough, otherwise from the site
    name = re.sub(r'[^0-9A-Za-z]+', '_', url.split(SITE, 1)[-1]).strip('_') + '.html'
    path = os.path.join(CACHE_DIR, name)
    # A schedule barely changes within a day, so a few hours old is still good enough to build from
    if not refresh and os.path.isfile(path):
        age = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(path))).total_seconds()
        if age < CACHE_HOURS * 3600:
            with open(path) as f:
                return f.read(), True

    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(path, 'w') as f:
        f.write(r.text)
    return r.text, False


def nuxtPayload(url, refresh=False):
    # Sidearm nextgen pages embed their data as a Nuxt payload; rebuild it as plain dicts and lists
    text, cached = pageHtmlText(url, refresh)

    # The payload sits in a <script id="__NUXT_DATA__"> tag as one JSON array
    m = re.search(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', text, re.S)
    if not m:
        raise ValueError(f"{url} has no __NUXT_DATA__ payload; did the site change?")

    # Flat array: [{"game": 1}, {"opponent": 2}, "ULM"] unflattens to {"game": {"opponent": "ULM"}}
    flat = json.loads(m.group(1))

    # Vue state is wrapped as ["Reactive", <slot>]; these tags mean "use the value in that slot"
    wrappers = {'Reactive', 'ShallowReactive', 'Ref', 'ShallowRef', 'EmptyRef'}

    # Slots already rebuilt, so values shared across the page are built once and reused
    memo = {}

    def resolve(i):
        # If the slot value is not a number, return payload as is
        if not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < len(flat):
            return i

        # Reuse a slot that's been rebuilt before
        if i in memo:
            return memo[i]
        v = flat[i]

        if isinstance(v, list):
            # A wrapper tag: skip past it to the slot it wraps (EmptyRef has none, so it's None)
            if v and isinstance(v[0], str) and v[0] in wrappers:
                memo[i] = resolve(v[1]) if len(v) > 1 else None
                return memo[i]

            # A real list: memoize the empty list first so a list that contains itself can't loop
            out = memo[i] = []
            # Then swap each slot number in the list for the value it points to
            out.extend(resolve(x) for x in v)
            return out

        if isinstance(v, dict):
            # Same for an object: memoize it first, then resolve each field's slot number
            out = memo[i] = {}
            for k, x in v.items():
                out[k] = resolve(x)
            return out

        # Strings, numbers, true/false and null are stored directly in their slot
        return v

    # Start at the root in slot 0 and rebuild everything reachable from it
    return resolve(0), cached


def scheduleEvents(slug, season, refresh=False):
    # Every event on one schedule page, once each, in date order
    url = f'{SITE}/sports/{slug}/schedule/{season}'
    # Events keyed by their id, since the same event shows up in several parts of the page
    found = {}

    def walk(o):
        # Search the whole rebuilt payload, since events sit at different depths on each page
        if isinstance(o, dict):
            # Anything with these four fields is a scheduled event; keep it and stop descending
            if {'game_state', 'opponent', 'date', 'result'} <= o.keys():
                found[o.get('id')] = o
                return
            # Otherwise look inside each of the object's values
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            # And inside each item of a list
            for v in o:
                walk(v)

    payload, cached = nuxtPayload(url, refresh)
    walk(payload)
    # Dates are ISO strings, so sorting them as text puts them in calendar order
    events = sorted(found.values(), key=lambda e: e.get('date') or '')
    return url, events, cached


####
# EVENT FILTERS
####

def inAcademicYear(event, year):
    # An unposted season shows another season's schedule, so keep only July 1 through June 30
    try:
        when = datetime.fromisoformat(event['date']).date()
    except (TypeError, ValueError):
        # An event with a missing or unreadable date can't be placed in any year
        return False
    return date(year, 7, 1) <= when <= date(year + 1, 6, 30)


def isUlm(event):
    # A game against ULM, matched by any of the names the site uses or by ULM's website
    opp = event.get('opponent') or {}
    return (opp.get('title') or '').strip() in ('ULM', 'Louisiana-Monroe', 'UL Monroe', 'Louisiana Monroe') \
        or 'ulmwarhawks' in (opp.get('website') or '')


def isChampionship(event):
    # A conference championship; NCAA championships come after and don't count toward the series
    title = ((event.get('opponent') or {}).get('title') or '')
    return 'championship' in title.lower() and not title.lower().startswith('ncaa')


####
# GAME INFO
####

def resultOf(event):
    # A played event has a result dict; an unplayed one has -1 or nothing, so treat that as empty
    return event['result'] if isinstance(event.get('result'), dict) else {}


# The schedules mix 'Foley, AL' with 'Monroe, La.', so settle on AP state abbreviations
AP_STATES = {'AL': 'Ala.', 'AR': 'Ark.', 'FL': 'Fla.', 'GA': 'Ga.', 'KY': 'Ky.',
             'MS': 'Miss.', 'NC': 'N.C.', 'OK': 'Okla.', 'SC': 'S.C.', 'TN': 'Tenn.',
             'TX': 'Texas', 'VA': 'Va.', 'WV': 'W.Va.'}


def cityText(event):
    # The event's city as the page shows it
    city = (event.get('location') or '').strip()
    # Split "City, ST" into the city and the state, with or without a trailing period
    m = re.fullmatch(r'(.+?),\s*([A-Za-z]+)\.?', city)
    if not m:
        return city
    state = m.group(2).upper()
    # Both schools are in Louisiana, so a Louisiana city goes without its state
    if state in ('LA', 'LOUISIANA'):
        return m.group(1)
    # Other states get their AP abbreviation
    if state in AP_STATES:
        return f'{m.group(1)}, {AP_STATES[state]}'
    # A state not in the table is left the way the site wrote it
    return city


def gameRow(event):
    # One game against ULM, trimmed down to what the page shows
    res = resultOf(event)
    # W, L or T once the game is final; empty before then
    status = (res.get('status') or '').upper()
    # Text like "Canceled" or "Postponed" for a game that won't be played as scheduled
    noplay = (event.get('noplay_text') or '').strip()
    when = datetime.fromisoformat(event['date'])
    time = (event.get('time') or '').strip()
    # The box score link is site-relative, so it gets the site prepended below
    boxscore = (res.get('boxscore') or {}).get('url')
    return {
        # The raw ISO date, kept for sorting the sports into calendar order
        'start': event['date'],
        # e.g. "Sat, Oct 17"; the day is added separately so it has no leading zero
        'date': when.strftime('%a, %b ') + str(when.day),
        # A time of TBA is left off rather than printed
        'time': '' if time.upper() == 'TBA' else time,
        'city': cityText(event),
        # X marks a game that won't be played; empty means it's still to come
        'status': status if status in ('W', 'L', 'T') else ('X' if noplay else ''),
        # Tech's score first, joined with an en dash
        'score': f"{res.get('team_score')}–{res.get('opponent_score')}" if status in ('W', 'L', 'T') else '',
        # The cancellation text, or notes after the score like "(7 inn.)" or "OT"
        'note': noplay or (res.get('postscore_info') or '').strip(),
        'boxscore': SITE + boxscore if boxscore and boxscore.startswith('/') else boxscore,
    }


####
# CHAMPIONSHIP INFO
####

def conferenceFinish(events, gender):
    # Tech's place at each conference championship, one row per meet
    meets = {}
    for e in events:
        # Multi-day meets repeat on every day, so group the days by the meet's name
        title = e['opponent']['title']
        # The first day seen sets the meet's start date and city
        meet = meets.setdefault(title, {'first': e['date'], 'last': e['date'], 'place': '',
                                        'city': cityText(e)})
        # Events come in date order, so each later day moves the end date forward
        meet['last'] = e['date']
        # The place is posted on the final day, e.g. "M 10th; W 12th" or "T-8th"
        info = (resultOf(e).get('postscore_info') or '').strip()
        if not info:
            continue
        # Cross country and track list both teams on one line; keep just this gender's place
        if gender:
            m = re.search(rf'\b{gender}\s+(T-?\d+\w*|\d+\w*)', info)
            info = m.group(1) if m else ''
        if info:
            meet['place'] = info

    rows = []
    for title, meet in meets.items():
        first = datetime.fromisoformat(meet['first'])
        last = datetime.fromisoformat(meet['last'])
        # A one-day meet reads "Fri, Oct 30"
        span = first.strftime('%a, %b ') + str(first.day)
        # A longer meet reads "Apr 26–29", or "Feb 27–Mar 1" when it crosses into the next month
        if last.date() != first.date():
            span = first.strftime('%b ') + str(first.day) + '–' + \
                (str(last.day) if last.month == first.month else last.strftime('%b ') + str(last.day))
        rows.append({'title': title, 'start': meet['first'], 'date': span, 'place': meet['place'],
                     'city': meet['city']})
    return rows


####
# SCORING
####

def scoreHeadToHead(games):
    # Season series (or single game) standings and who, if anyone, has the point
    w = sum(g['status'] == 'W' for g in games)
    l = sum(g['status'] == 'L' for g in games)
    t = sum(g['status'] == 'T' for g in games)
    # Games still to be played; canceled games (X) aren't counted as left
    left = sum(g['status'] == '' for g in games)
    out = {'tech': w, 'ulm': l, 'ties': t, 'left': left}

    # No games against ULM posted yet
    if not games:
        return {**out, 'state': 'tba', 'winner': None}
    # Tech has more wins than ULM could reach by winning every game left
    if w > l + left:
        return {**out, 'state': 'final' if not left else 'clinched', 'winner': TECH}
    # The same for ULM
    if l > w + left:
        return {**out, 'state': 'final' if not left else 'clinched', 'winner': ULM}
    # Every game played and neither side ahead: the point is split
    if not left and w + l + t:
        return {**out, 'state': 'final', 'winner': 'Tie'}
    # Still undecided: in progress once a game is played, upcoming before that
    return {**out, 'state': 'live' if w + l + t else 'upcoming', 'winner': None}


def buildSeries(year, refresh=False):
    # Pull every sport and score it; any fetch failure stops the run rather than drop results
    manual = CONFERENCE_RESULTS.get(year, {})
    # Schedule pages already fetched, since cross country and track each serve two sports
    pages = {}
    sports = []
    for sport in SPORTS:
        # Fetch this sport's schedule page unless another sport already did
        season = seasonSlug(sport['season'], year)
        if (sport['slug'], season) not in pages:
            url, events, cached = scheduleEvents(sport['slug'], season, refresh)
            print(f"  {'cached' if cached else 'fetched'} {sport['slug']} {season}")
            pages[sport['slug'], season] = (url, events)
        url, events = pages[sport['slug'], season]
        events = [e for e in events if inAcademicYear(e, year)]
        # Start from the sport's settings and add what this year's schedule says
        row = {**sport, 'url': url}

        if sport['kind'] == 'h2h':
            # Head-to-head: every game against ULM, and the standings they add up to
            row['games'] = [gameRow(e) for e in events if isUlm(e)]
            row.update(scoreHeadToHead(row["games"]))
        else:
            # Conference finish: the point comes from CONFERENCE_RESULTS once it's entered
            entry = manual.get(sport['key']) or {}
            winner = entry.get('winner')
            # Catch a typo in the hand-entered winner before it quietly scores nobody
            if winner not in (None, TECH, ULM, 'Tie'):
                raise ValueError(f"CONFERENCE_RESULTS[{year}][{sport['key']!r}] winner "
                                 f"must be {TECH!r}, {ULM!r} or 'Tie', not {winner!r}")
            # The championship dates, cities and Tech's places come from the schedule
            row['meets'] = conferenceFinish([e for e in events if isChampionship(e)],
                                            sport.get('gender'))
            row['techFinish'] = entry.get('techFinish', '')
            row['ulmFinish'] = entry.get('ulmFinish', '')
            row['winner'] = winner
            row['state'] = 'final' if winner else ('upcoming' if row['meets'] else 'tba')
        sports.append(row)

    # The page runs in calendar order by each sport's first date; sports with no dates go last
    for s in sports:
        s['start'] = min((g['start'] for g in s.get('games', []) + s.get('meets', [])), default=None)
    sports.sort(key=lambda s: (s['start'] is None, s['start'] or ''))

    # A won point is worth 1 and a split point ½ to each school
    tech = sum(1 if s['winner'] == TECH else 0.5 if s['winner'] == 'Tie' else 0 for s in sports)
    ulm = sum(1 if s['winner'] == ULM else 0.5 if s['winner'] == 'Tie' else 0 for s in sports)
    h2h = [s for s in sports if s['kind'] == 'h2h']
    football = next(s for s in sports if s['key'] == 'football')

    # The first school to 6.5 points wins the series
    champion = None
    if tech >= POINTS_TO_WIN:
        champion = TECH
    elif ulm >= POINTS_TO_WIN:
        champion = ULM
    # If all 12 points end 6-6, the football winner takes the series
    elif all(s['winner'] for s in sports) and football['winner'] in (TECH, ULM):
        champion = football['winner']

    return {
        'year': year,
        # e.g. "2026–27"
        'label': f'{year}–{str(year + 1)[-2:]}',
        'sports': sports,
        'tech': tech,
        'ulm': ulm,
        'decided': sum(1 for s in sports if s['winner']),
        # Individual games won across every head-to-head sport
        'techGames': sum(s['tech'] for s in h2h),
        'ulmGames': sum(s['ulm'] for s in h2h),
        'tieGames': sum(s['ties'] for s in h2h),
        'champion': champion,
    }


####
# HTML HELPERS
####

def icon(name, cls='icon'):
    # A saved MDI icon placed inline, so CSS can color it to match what's around it
    with open(os.path.join(OUT_DIR, IMG_DIR, f'mdi-{name}.svg')) as f:
        svg = f.read()
    # Keep the file's own drawing area and shapes, and swap its outer tag for one of ours
    viewBox = re.search(r'viewBox="([^"]+)"', svg)
    body = re.search(r'<svg[^>]*>(.*)</svg>', svg, re.S)
    # currentColor fills the icon with the text color of whatever it sits in
    return (f'<svg class="{cls}" viewBox="{viewBox.group(1) if viewBox else "0 0 24 24"}" '
            f'fill="currentColor" aria-hidden="true">{body.group(1) if body else ""}</svg>')


def pts(x):
    # Points as the page prints them: 4 rather than 4.0, and 4.5 as is
    return str(int(x)) if float(x).is_integer() else f'{x:g}'


def owner(sport):
    # The CSS class for who holds a sport's point, which sets its colors
    return {TECH: 'tech', ULM: 'ulm', 'Tie': 'tie'}.get(sport['winner'], 'open')


def badge(sport):
    # Only a split point gets a badge; a won point already shows in the winner's colors
    return '<span class="badge">Split ½–½</span>' if sport['winner'] == 'Tie' else ''


def seriesLine(sport):
    # "Tech 1 – 1 ULM" under a head-to-head card's header, once a game has been played
    if sport['kind'] != 'h2h' or not sport['tech'] + sport['ulm'] + sport['ties']:
        return ''
    ties = f'<span class="ties">{sport["ties"]} tied</span>' if sport['ties'] else ''
    return (f'<p class="series"><span class="t">Tech {sport["tech"]}</span>'
            f'<span class="dash">–</span><span class="u">{sport["ulm"]} ULM</span>{ties}</p>')


####
# GAME TILES AND SPORT CARDS
####

def tileHtml(cls, city, when, result='', caption=''):
    # One game or meet, like a destination on a sign: city, then date and time, then the result
    caption = f'<span class="caption">{escape(caption)}</span>' if caption else ''
    result = f'<span class="result">{result}</span>' if result else ''
    return (f'<li class="game {cls}">{caption}'
            f'<span class="city">{escape(city)}</span><span class="when">{when}</span>{result}</li>')


def gameListHtml(sport):
    # The tiles inside a head-to-head card
    if not sport['games']:
        # No schedule yet: one placeholder tile with no place or date
        return tileHtml('pending tba', 'Location TBA', 'Date TBA')
    out = []
    for g in sport['games']:
        # The CSS class for how the game went, which colors its result
        cls = {'W': 'win', 'L': 'loss', 'T': 'tie', 'X': 'noplay'}.get(g['status'], 'pending')
        # The date, with the time on a smaller line under it when there is one
        when = escape(g['date']) + (f'<small>{escape(g["time"])}</small>' if g['time'] else '')
        if g['status'] in ('W', 'L', 'T'):
            # A played game: a colored W/L/T pill and the score
            result = f'<span class="pill {g["status"].lower()}">{g["status"]}</span> {escape(g["score"])}'
            # Add notes like "(7 inn.)" under the score
            if g['note']:
                result += f'<small>{escape(g["note"])}</small>'
            # Link the result to the box score
            if g['boxscore']:
                result = f'<a href="{escape(g["boxscore"], quote=True)}">{result}</a>'
        elif g['status'] == 'X':
            # A canceled or postponed game shows why
            result = f'<small>{escape(g["note"])}</small>'
        else:
            # A game still to come has no result line
            result = ''
        out.append(tileHtml(cls, g['city'] or 'Location TBA', when, result))
    return ''.join(out)


def meetListHtml(sport):
    # The tiles inside a conference-finish card, one per championship
    if not sport['meets']:
        # No championship on the schedule yet: one placeholder tile
        return tileHtml('meet pending tba', 'Location TBA', 'Date TBA')
    out = []
    for m in sport['meets']:
        # Hand-entered places go on the last meet listed
        last = m is sport['meets'][-1]
        # Tech's place from the schedule wins; the hand-entered one fills in until it's posted
        techPlace = m['place'] or (sport['techFinish'] if last else '')
        places = []
        if techPlace:
            places.append(f'<span class="place t">Tech {escape(techPlace)}</span>')
        if sport['ulmFinish'] and last:
            places.append(f'<span class="place u">ULM {escape(sport["ulmFinish"])}</span>')
        # Track has an indoor and an outdoor championship; say which is which
        season = re.search(r'\b(Indoor|Outdoor)\b', m['title'])
        out.append(tileHtml('meet ' + ('done' if places else 'pending'),
                            m['city'] or 'Location TBA', escape(m['date']), ''.join(places),
                            season.group(1) if season else ''))
    return ''.join(out)


def exitTabsHtml(sport, exitNumber):
    # One exit tab per game or meet, so a sport with two events gets 6A and 6B
    events = len(sport.get('games') or sport.get('meets') or [])
    # A single event (or a placeholder with none yet) keeps the plain number
    if events <= 1:
        labels = [str(exitNumber)]
    # Otherwise letter them in date order: A, B, C...
    else:
        labels = [f'{exitNumber}{chr(ord("A") + n)}' for n in range(events)]
    # CSS right-aligns each tab over its event, so A ends at the sign's center and B at its edge
    tabs = ''.join(f'<span class="exit">Exit {label}</span>' for label in labels)
    return f'<div class="exits">{tabs}</div>'


def sportCardHtml(sport, exitNumber):
    # One sport's card as an exit sign (tabs, sport name, events), wrapped so CSS can cap its width
    items = gameListHtml(sport) if sport['kind'] == 'h2h' else meetListHtml(sport)
    return f'''
        <article class="sport {owner(sport)}">
          {exitTabsHtml(sport, exitNumber)}
          <div class="sign">
            <header>
              <span class="marker">{icon(sport['icon'])}</span>
              <div class="heading">
                <h3><a href="{escape(sport['url'], quote=True)}">{escape(sport['name'])}</a></h3>
              </div>
              {badge(sport)}
            </header>
            {seriesLine(sport)}
            <ul class="games">{items}</ul>
          </div>
        </article>'''


####
# PAGE BUILD
####

def signPoints(x):
    # Points as the header and signs show them, with a half point as ½: 4.5 is "4½" and 0.5 is "½"
    whole = int(x)
    half = x - whole == 0.5
    return f'{whole if whole or not half else ""}{"½" if half else ""}'


def teamSignHtml(series, team):
    # One team's logo sign, like the blue "FOOD—EXIT 44" signs with a panel for each restaurant
    name = 'Louisiana Tech' if team == TECH else 'ULM'
    points = series['tech'] if team == TECH else series['ulm']
    # Every point this team won or split, already in date order, so the sign fills in over the year
    won = [s for s in series['sports'] if s['winner'] in (team, 'Tie')]
    # Start with 2 rows of 3, and add a row of 3 each time the panels run out (6, then 9, then 12)
    slots = max(6, -(-len(won) // 3) * 3)
    panels = []
    for s in won:
        # A split point goes on both signs with a ½ in the corner
        half = '<span class="half">½</span>' if s['winner'] == 'Tie' else ''
        split = ' split' if s['winner'] == 'Tie' else ''
        panels.append(f'<li class="panel{split}" title="{escape(s["name"], quote=True)}">{half}'
                      f'{icon(s["icon"], "panel-icon")}<span class="label">{escape(s["short"])}</span></li>')
    # The rest of the slots stay empty, each holding a faint white copy of the team's logo
    logo = TECH_LOGO if team == TECH else ULM_LOGO
    blank = f'<li class="panel empty"><img class="ghost" src="{logo}" alt="" width="200" height="200"></li>'
    panels += [blank] * (slots - len(won))
    cls = 'tech' if team == TECH else 'ulm'
    return (f'<section class="logo-sign {cls}" aria-label="{name}: {pts(points)} points">'
            f'<h2>{name}—{signPoints(points)}</h2><ul class="panels">{"".join(panels)}</ul></section>')


def statusLine(series):
    # The message on the overhead sign: the champion once there is one, otherwise the rule
    if series['champion']:
        return 'Tech wins' if series['champion'] == TECH else 'ULM wins'
    return f'First to {pts(POINTS_TO_WIN)} points wins'


def pageHtml(series, preview=None):
    # The finished page: the template with every placeholder filled in
    updated = datetime.now(TIMEZONE)
    # e.g. "September 17, 2026 at 9:58 AM CT", without leading zeros on the day or hour
    updatedText = updated.strftime('%B ') + str(updated.day) + updated.strftime(', %Y at ') + \
        updated.strftime('%I:%M %p').lstrip('0') + ' CT'
    # Sports are already in date order, so the exits count up through the season
    cards = ''.join(sportCardHtml(s, n) for n, s in enumerate(series['sports'], start=1))
    # The title and description also fill the link-preview tags
    title = f'I-20 Showdown {series["label"]}'
    description = (f'Louisiana Tech {pts(series["tech"])}, ULM {pts(series["ulm"])} in the '
                   f'{series["label"]} I-20 Showdown.')
    # X/Twitter keeps a card's image by its URL for days, so the build time rides along to fetch each new score
    previewUrl = f'{SITE_URL}/{preview}?v={updated:%Y%m%d%H%M}' if preview else ''
    # Plain text is escaped before it goes into the page; the HTML pieces above already are
    esc = lambda text: escape(str(text), quote=True)
    with open(PAGE_TEMPLATE) as f:
        template = Template(f.read())
    # substitute, not safe_substitute: an unfilled placeholder fails the run instead of shipping
    return template.substitute(
        title=esc(title),
        description=esc(description),
        season=esc(series['label']),
        shield=esc(I20_SHIELD),
        techSign=teamSignHtml(series, TECH),
        ulmSign=teamSignHtml(series, ULM),
        status=esc(statusLine(series)),
        cards=cards,
        site=esc(SITE),
        pageUrl=esc(SITE_URL + '/'),
        previewImage=esc(previewUrl),
        previewWidth=PREVIEW_SIZE[0],
        previewHeight=PREVIEW_SIZE[1],
        gtpddLogo=esc(GTPDD_LOGO),
        gtpddHome=esc(GTPDD_HOME),
        icon=esc(GTPDD_ICON),
        iconLarge=esc(GTPDD_ICON_LARGE),
        touchIcon=esc(GTPDD_TOUCH_ICON),
        updated=esc(updatedText),
        iconCredit=esc(ICON_CREDIT[0]),
        iconCreditUrl=esc(ICON_CREDIT[1]),
        shieldCredit=esc(I20_CREDIT[0]),
        shieldCreditUrl=esc(I20_CREDIT[1]),
        fontCredit=esc(FONT_CREDIT[0]),
        fontCreditUrl=esc(FONT_CREDIT[1]),
        boardFontCredit=esc(BOARD_FONT_CREDIT[0]),
        boardFontCreditUrl=esc(BOARD_FONT_CREDIT[1]),
    )


####
# LINK PREVIEW
####

def hexColor(h):
    # '#002F8B' -> (0, 47, 139)
    return tuple(int(h.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4))


def cardFont(path, size, weight):
    # One of the page's variable fonts, at a size and weight
    font = ImageFont.truetype(os.path.join(OUT_DIR, path), size)
    font.set_variation_by_axes([weight])
    return font


def spacedText(draw, center, text, font, fill, spacing=0):
    # Text centered on a point, with extra room between letters like the page's letter-spacing
    widths = [draw.textlength(c, font=font) for c in text]
    x = center[0] - (sum(widths) + spacing * (len(text) - 1)) / 2
    for c, w in zip(text, widths):
        draw.text((x, center[1]), c, font=font, fill=fill, anchor='lm')
        x += w + spacing


def cardSign(card, box, team, points):
    # A team's sign on the card: its color with an inset white outline, the logo on a white panel, and its points
    draw = ImageDraw.Draw(card)
    x0, y0, x1, y1 = box
    color = hexColor('#002F8B' if team == TECH else '#840029')
    draw.rounded_rectangle(box, 18, fill=color)
    draw.rounded_rectangle((x0 + 8, y0 + 8, x1 - 8, y1 - 8), 12, outline='white', width=3)
    name = 'LOUISIANA TECH' if team == TECH else 'ULM'
    spacedText(draw, ((x0 + x1) / 2, y0 + 46), name, cardFont(ROAD_FONT, 30, 700), 'white', 3)
    # Logo panel on the left, the points big on the right
    panel = (x0 + 34, y0 + 80, x0 + 204, y0 + 250)
    draw.rectangle(panel, fill='white')
    logo = Image.open(os.path.join(OUT_DIR, TECH_LOGO if team == TECH else ULM_LOGO)).convert('RGBA')
    logo.thumbnail((140, 140), Image.LANCZOS)
    card.alpha_composite(logo, (panel[0] + (170 - logo.width) // 2, panel[1] + (170 - logo.height) // 2))
    # A score with a ½ is wider, so it steps down in size until it clears the sign's outline
    score = signPoints(points) or '0'
    room = x1 - panel[2] - 50
    size = 150
    while draw.textlength(score, font=cardFont(ROAD_FONT, size, 800)) > room:
        size -= 6
    draw.text(((panel[2] + x1 - 8) / 2, (panel[1] + panel[3]) / 2 + 6), score,
              font=cardFont(ROAD_FONT, size, 800), fill='white', anchor='mm')


def writePreviewCard(series):
    # The link-preview card: the page's hero in miniature, with the current score on each sign
    W, H = PREVIEW_SIZE
    # The hero's blue-to-maroon sweep, left to right
    stops = [(0, '#001a52'), (0.42, '#002F8B'), (0.58, '#840029'), (1, '#4f0018')]
    strip = Image.new('RGB', (W, 1))
    for x in range(W):
        t = x / (W - 1)
        (t0, c0), (t1, c1) = next((a, b) for a, b in zip(stops, stops[1:]) if t <= b[0])
        f = (t - t0) / (t1 - t0)
        strip.putpixel((x, 0), tuple(round(a + (b - a) * f) for a, b in zip(hexColor(c0), hexColor(c1))))
    card = strip.resize((W, H)).convert('RGBA')
    draw = ImageDraw.Draw(card)

    # Title block
    spacedText(draw, (W / 2, 44), 'THE INAUGURAL', cardFont(ROAD_FONT, 22, 700), (255, 255, 255, 217), 4)
    spacedText(draw, (W / 2, 108), 'I-20 SHOWDOWN', cardFont(ROAD_FONT, 88, 800), 'white')
    spacedText(draw, (W / 2, 172), f"{series['label']} RIVALRY SERIES".upper(),
               cardFont(ROAD_FONT, 24, 700), '#f3dc8f', 4)

    # Both signs with the shield between them
    cardSign(card, (60, 210, 480, 486), TECH, series['tech'])
    cardSign(card, (W - 480, 210, W - 60, 486), ULM, series['ulm'])
    shield = Image.open(os.path.join(OUT_DIR, I20_SHIELD_PNG)).convert('RGBA')
    shield.thumbnail((170, 170), Image.LANCZOS)
    card.alpha_composite(shield, ((W - shield.width) // 2, 348 - shield.height // 2))

    # The overhead message board with the page's status line
    board = cardFont(BOARD_FONT, 36, 700)
    message = statusLine(series).upper()
    tw = draw.textlength(message, font=board)
    draw.rounded_rectangle((W / 2 - tw / 2 - 30, 500, W / 2 + tw / 2 + 30, 556), 6,
                           fill='#0a0a0b', outline='#8b8f96', width=5)
    draw.text((W / 2, 530), message, font=board, fill='#ffb703', anchor='mm')

    # A stretch of highway along the bottom: white edge lines, asphalt, dashed yellow center line
    draw.rectangle((0, H - 42, W, H), fill='white')
    draw.rectangle((0, H - 39, W, H - 3), fill='#2b2d31')
    for x in range(0, W, 58):
        draw.rectangle((x, H - 23, x + 34, H - 19), fill='#f2c230')

    card.convert('RGB').save(os.path.join(OUT_DIR, PREVIEW), optimize=True)
    return PREVIEW


####
# MAIN
####

def printStandings(series):
    # A summary in the terminal, so a run shows what it found without opening the page
    print(f"\nI-20 Showdown {series['label']}: Tech {pts(series['tech'])}, ULM {pts(series['ulm'])}"
          f" ({series['decided']}/12 decided; games {series['techGames']}-{series['ulmGames']}"
          f"{'-' + str(series['tieGames']) if series['tieGames'] else ''})")
    # Then one line per sport: who has the point (or its state) and what's on the schedule
    for s in series['sports']:
        detail = ''
        if s['kind'] == 'h2h':
            detail = f"{len(s['games'])} game(s), Tech {s['tech']}-{s['ulm']}" if s['games'] else 'no ULM games posted'
        else:
            detail = '; '.join(f"{m['title']} {m['date']} {m['place']}".strip() for m in s['meets']) or 'no championship posted'
        print(f"  {s['name']:<24} {(s['winner'] or s['state']):<14} {detail}")
    if series['champion']:
        print(f"  Champion: {series['champion']}")


def missingImages():
    # Every image (and the font) this build can reference that isn't saved in the page folder
    icons = {s['icon'] for s in SPORTS}
    paths = [TECH_LOGO, ULM_LOGO, GTPDD_LOGO, GTPDD_ICON, GTPDD_ICON_LARGE, GTPDD_TOUCH_ICON, FAVICON,
             I20_SHIELD, I20_SHIELD_PNG, ROAD_FONT, BOARD_FONT] + \
            [f'{IMG_DIR}/mdi-{name}.svg' for name in sorted(icons)]
    return [p for p in paths if not os.path.isfile(os.path.join(OUT_DIR, p))]


def i20showdown(year=None, dryRun=False, refresh=False, today=None):
    # Build the page for one academic year
    today = today or date.today()
    # With no year given, use the one in progress: July onward belongs to the new academic year
    if year is None:
        year = today.year if today.month >= 7 else today.year - 1
        year = max(year, FIRST_SERIES)

    # Restore any missing images and fonts (a dry run writes nothing)
    if not dryRun:
        copyMissingFiles(STATIC_DIR, OUT_DIR)

    # Check before fetching anything, so a missing file doesn't cost a full scrape
    missing = missingImages()
    if missing and not dryRun:
        raise FileNotFoundError(f"missing from {OUT_DIR}: {', '.join(missing)}")

    print(f"Building the {year}-{str(year + 1)[-2:]} I-20 Showdown")
    series = buildSeries(year, refresh)
    printStandings(series)
    # A dry run stops after printing, leaving the published page untouched
    if dryRun:
        print(f"\nDry run: {OUT_DIR} left alone.")
        return series

    # Copy the stylesheet over, draw the link-preview card, then write the filled-in page
    shutil.copyfile(PAGE_CSS, os.path.join(OUT_DIR, 'style.css'))
    preview = writePreviewCard(series)
    with open(os.path.join(OUT_DIR, 'index.html'), 'w') as f:
        f.write(pageHtml(series, preview))
    print(f"\nWrote {OUT_DIR}/index.html")
    return series


####
# COMMAND LINE
####

if __name__ == "__main__":
    import argparse

    # Command-line options: --year to pick the series, --dry-run to print without writing
    parser = argparse.ArgumentParser(
        description="Build the I-20 Showdown page in html/i20showdown/.")
    parser.add_argument("--year", type=int,
                        help="Academic year the series starts in, e.g. 2026 for 2026-27 "
                             "(default: the current one)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the standings without writing the page")
    parser.add_argument("--refresh", action="store_true",
                        help=f"Refetch every schedule instead of reusing pages cached in {CACHE_DIR}")
    args = parser.parse_args()

    i20showdown(year=args.year, dryRun=args.dry_run, refresh=args.refresh)
