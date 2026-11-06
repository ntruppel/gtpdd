# -*- coding: utf-8 -*-
"""
Odds on who wins each Sun Belt division, from ESPN's FPI game projections.

Simulates the rest of the conference schedule many times and settles every tied
race with the Sun Belt's tie-breakers. Each run updates html/stats/fbSunBeltPredictor.html
(stats.gtpdd.dog/fbSunBeltPredictor.html), which keeps every run of the season, with its
files in html/stats/fbSunBeltPredictor/; re-running on the same day replaces that day's run.
The run history is kept in csv/fbSunBeltPredictorRuns.js; page templates live in
lib/html/fbSunBeltPredictor/.

Tie-breakers: https://sunbeltsports.org/sports/2018/8/30/FB_Tie-Breakers.aspx
The composite computer ranking is stood in for by FPI, nudged by simulated results.

Run from the repo root:

    python fbSunBeltPredictor.py                 # this season, PNG + page
    python fbSunBeltPredictor.py --cfp JMU=18    # a Sun Belt team in the CFP rankings
    python fbSunBeltPredictor.py --no-html       # just the PNG
"""

####
# IMPORTS
####

import json
import os
from itertools import permutations, product
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from string import Template

import matplotlib.pyplot as plt
import numpy as np
import requests
from html import escape as html_escape
from PIL import Image

from lib.fbCommon import (LOGO_DIR, TEAM_COLORS_CSV, assetSlug, currentSeason, downloadLogo,
                          gameDateTime, getTeamInfo, loadTeamColorsCsv, previewMetaTags,
                          publishAsset, readJsGlobal, trimmedLogo,
                          writeJsGlobal)

####
# CONSTANTS
####

CONFERENCE_ID = "37"                   # Sun Belt, on ESPN
TEAM_ID = "2348"                       # Louisiana Tech, highlighted on the page
SIMS = 20000                           # simulated seasons per run
RESULT_WEIGHT = 3.0                    # FPI points a team's computer ranking moves per surprise win
SWING_FLOOR = 0.005                    # smallest title-odds swing a remaining game reports
ELIM_SEARCH_LIMIT = 2_000_000          # scenarios tried before an elimination check gives up and calls a team alive
DISPLAY_NAMES = {'309': 'Louisiana-Lafayette'}  # ESPN just calls ULL "Louisiana"
DISPLAY_ABBRS = {'309': 'ULL'}         # ...and abbreviates it "UL"
MIN_WHITE_CONTRAST = 1.5               # team colors paler than this vanish on the white chart card
ALTERNATE_PENALTY = 2.0                # color distance given up to keep a team on its primary color

# ESPN endpoints
ESPN_STANDINGS_URL = 'https://site.api.espn.com/apis/v2/sports/football/college-football/standings?group={}&season={}'
ESPN_SCHEDULE_URL = 'https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams/{}/schedule?season={}'
ESPN_SUMMARY_URL = 'http://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event={}'
ESPN_CONF_LOGO_URL = 'https://a.espncdn.com/i/teamlogos/ncaa_conf/500/{}.png'
ESPN_FPI_URL = 'https://site.web.api.espn.com/apis/fitt/v3/sports/football/college-football/powerindex?region=us&lang=en&season={}&limit=500'

# Tie-breaker steps, in the order the page lists how ties were settled
STEP_NAMES = ['Head-to-head', 'Division record', 'Record vs. standings',
              'Common opponents', 'CFP ranking', 'Computer rankings', 'Coin toss']

# Site and file locations
HOME_URL = "https://gtpdd.dog"
SITE_URL = "https://stats.gtpdd.dog"   # the published root of html/stats/
TWITTER_HANDLE = "@gotechplsdntdie"

HTML_DIR = "html/stats"                # shared by several gtpdd stat pages
ASSET_DIR_NAME = 'fbSunBeltPredictor'  # this page's own files, grouped beside it
ASSET_DIR = os.path.join(HTML_DIR, ASSET_DIR_NAME)
WEB_IMG_DIR = os.path.join(ASSET_DIR, 'img')
GTPDD_LOGO = 'img/gtpdd_logo.png'      # the nav logo, published alongside the page
CONF_LOGO_NAME = 'Sun Belt'            # the conference logo's name in the shared logo cache
CONF_LOGO_HEIGHT = 112                 # the title's conference logo, at 2x its drawn height
LOGO_HEIGHT = 56                       # published at 2x the height the table draws
HERO_LOGO_HEIGHT = 240                 # the predicted-championship logos, at 2x their drawn height
MATCHUPS = 5                           # most likely title-game matchups kept per run
PAGE_FILENAME = 'fbSunBeltPredictor.html'
CSS_FILENAME = 'fbSunBeltPredictor.css'
JS_FILENAME = 'fbSunBeltPredictor.js'
STARBURST_FILENAME = 'starburst.svg'   # the matchup card's background, from the Sun Belt logo
RUNS_FILENAME = 'runs.js'              # every run of every season, as a script
RUNS_PATH = 'csv/fbSunBeltPredictorRuns.js'  # tracked master copy of the run history, copied to the site
JS_GLOBAL = 'GTPDD_SUNBELT_RUNS'
FIG_PATH = 'out/fbSunBeltPredictor.png'
PREVIEW_FILENAME = 'preview.jpg'
PREVIEW_SIZE = (1200, 630)             # a summary_large_image card
PREVIEW_BG = (255, 255, 255)           # behind the chart, when the preview falls back to it
PREVIEW_SCALE = 2                      # the page is shot at 2x and scaled down, for crisp text
PREVIEW_SHOT = 'out/fbSunBeltPredictorPreview.png'  # the raw browser screenshot
# Chrome or Chromium, wherever this machine keeps it
BROWSERS = ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '/Applications/Chromium.app/Contents/MacOS/Chromium',
            'google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome']

# Comment block written at the top of runs.js
RUNS_JS_HEADER = """\
// Every run of the Sun Belt predictor, oldest first within a season. One entry per
// run: each team's division title odds, how tied races were settled, and the
// remaining conference games with how much each one swings the races.
//
// Generated by fbSunBeltPredictor.py -- rerun it to add today's run."""

# Page skeleton, stylesheet, script and starburst live in lib/html/fbSunBeltPredictor/
TEMPLATE_DIR = 'lib/html/fbSunBeltPredictor'
PAGE_TEMPLATE = os.path.join(TEMPLATE_DIR, 'page.html')
PAGE_CSS = os.path.join(TEMPLATE_DIR, CSS_FILENAME)
PAGE_JS = os.path.join(TEMPLATE_DIR, JS_FILENAME)
PAGE_STARBURST = os.path.join(TEMPLATE_DIR, STARBURST_FILENAME)


####
# ESPN FEEDS
####

def espnJson(url):
    # GETs an ESPN endpoint and returns the parsed JSON
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json()


def teamLogoUrl(team):
    # Returns ESPN's standard (light-background) logo URL for a team
    logos = team.get('logos') or []
    for wanted in ('default', 'dark'):
        for logo in logos:
            if wanted in (logo.get('rel') or []) and logo.get('href'):
                return logo['href']
    return logos[0].get('href') if logos else None


def conferenceTeams(season):
    # Returns every Sun Belt team with its division, from ESPN's conference standings
    x = espnJson(ESPN_STANDINGS_URL.format(CONFERENCE_ID, season))
    teams = []
    for child in x.get('children', []):
        # 'Sun Belt - East' -> 'East'
        division = child.get('name', '').split(' - ')[-1]
        for entry in (child.get('standings') or {}).get('entries', []):
            t = entry['team']
            teams.append({
                'id': str(t['id']),
                'espnName': t.get('location') or t.get('displayName'),
                'name': DISPLAY_NAMES.get(str(t['id']), t.get('location') or t.get('displayName')),
                'abbr': DISPLAY_ABBRS.get(str(t['id']), t.get('abbreviation', '')),
                'division': division,
                'logoUrl': teamLogoUrl(t),
            })
    return teams


def powerIndex(season):
    # Returns team ID -> (FPI rating, ESPN's own division title odds)
    x = espnJson(ESPN_FPI_URL.format(season))
    out = {}
    for t in x.get('teams', []):
        cat = next((c for c in t.get('categories', []) if c.get('name') == 'fpi'), None)
        names = next((c.get('names') for c in x.get('categories', []) if c.get('name') == 'fpi'), [])
        if not cat or 'fpi' not in names:
            continue
        values = cat.get('values') or []
        fpi = values[names.index('fpi')]
        # ESPN reports the division odds as a percentage
        div = values[names.index('probwindiv')] / 100 if 'probwindiv' in names else None
        out[str(t['team']['id'])] = (float(fpi), div)
    return out


def conferenceGames(teams, season):
    # Returns every regular-season game between two Sun Belt teams, oldest first
    ids = {t['id'] for t in teams}
    games = {}
    for t in teams:
        x = espnJson(ESPN_SCHEDULE_URL.format(t['id'], season))
        for event in x.get('events', []):
            comp = (event.get('competitions') or [{}])[0]
            sides = {c.get('homeAway'): c for c in comp.get('competitors', [])}
            home, away = sides.get('home'), sides.get('away')
            # Both sides must be Sun Belt teams, and skip the title game
            if not home or not away or str(event.get('id')) in games:
                continue
            if str(home['team']['id']) not in ids or str(away['team']['id']) not in ids:
                continue
            notes = ' '.join(n.get('headline', '') for n in comp.get('notes') or [])
            if (event.get('seasonType') or {}).get('type') not in (None, 2) or 'Championship' in notes:
                continue

            completed = bool(((comp.get('status') or {}).get('type') or {}).get('completed'))
            hs = (home.get('score') or {}).get('value')
            vs = (away.get('score') or {}).get('value')
            games[str(event['id'])] = {
                'gameID': str(event['id']),
                'startDate': comp.get('date') or event.get('date'),
                # TBD kickoffs sit at midnight Eastern, so read their day in Eastern time
                'timezone': None if comp.get('timeValid') else 'America/New_York',
                'week': (event.get('week') or {}).get('number'),
                'home': str(home['team']['id']),
                'away': str(away['team']['id']),
                'completed': completed,
                # Unplayed games show 0-0, so only read the score once the game is final
                'homeScore': int(hs) if completed and hs is not None else None,
                'awayScore': int(vs) if completed and vs is not None else None,
            }
    return sorted(games.values(), key=lambda g: g['startDate'] or '')


def getPrediction(gameID):
    # Returns the home team's FPI win percentage for a game, or None if ESPN has no projection
    try:
        predictor = espnJson(ESPN_SUMMARY_URL.format(gameID))['predictor']
        return float(predictor['homeTeam']['gameProjection'])
    except Exception as e:
        print(f"  No FPI for game {gameID} ({type(e).__name__}: {e}).")
        return None


def gameOdds(games):
    # Sets each game's home win odds (1/0 if played, FPI otherwise) and its source for the page
    for g in games:
        if g['completed'] and g['homeScore'] is not None and g['awayScore'] is not None:
            g['homeOdds'] = 1.0 if g['homeScore'] > g['awayScore'] else 0.0
            g['source'] = 'final'
            continue
        projection = getPrediction(g['gameID'])
        if projection is None:
            # No FPI: count it as a coin flip rather than dropping it from the schedule
            g['homeOdds'], g['source'] = 0.5, 'even'
        else:
            g['homeOdds'], g['source'] = round(projection / 100, 4), 'fpi'
    return games


def publishTeamLogo(team):
    # Caches a team's logo and publishes table and matchup sizes; returns {'logo', 'logoLarge'} links within ASSET_DIR
    name, url = team['espnName'], team.get('logoUrl')
    if not name or not url:
        return {}
    slug = assetSlug(name)
    src = os.path.join(LOGO_DIR, f"{name}.png")
    if not os.path.isfile(src) and not downloadLogo(url, src, name):
        return {}
    img = trimmedLogo(src)
    if img is None:
        return {}
    links = {}
    # One copy per size, allowing wide wordmarks up to 2.5x the height
    for key, folder, height in (('logo', 'logo', LOGO_HEIGHT),
                                ('logoLarge', 'logo/large', HERO_LOGO_HEIGHT)):
        sized = img.copy()
        sized.thumbnail((round(height * 2.5), height), Image.LANCZOS)
        os.makedirs(os.path.join(ASSET_DIR, folder), exist_ok=True)
        sized.save(os.path.join(ASSET_DIR, folder, slug + '.png'))
        links[key] = folder + '/' + slug + '.png'
    return links


def publishConferenceLogo():
    # Publishes the Sun Belt logo for the page title; returns its link within ASSET_DIR, or None
    src = os.path.join(LOGO_DIR, f"{CONF_LOGO_NAME}.png")
    if not os.path.isfile(src) and not downloadLogo(ESPN_CONF_LOGO_URL.format(CONFERENCE_ID),
                                                    src, CONF_LOGO_NAME):
        return None
    img = trimmedLogo(src)
    if img is None:
        return None
    img.thumbnail((CONF_LOGO_HEIGHT * 3, CONF_LOGO_HEIGHT), Image.LANCZOS)
    os.makedirs(WEB_IMG_DIR, exist_ok=True)
    img.save(os.path.join(WEB_IMG_DIR, 'sunbelt_logo.png'))
    return 'img/sunbelt_logo.png'


####
# TEAM COLORS
####

def hexToOklab(hex_color):
    # Converts '#rrggbb' to OKLab, where distance tracks how different two colors look
    rgb = [int(hex_color.lstrip('#')[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    r, g, b = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return np.array([0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
                     1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
                     0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s])


def colorDistance(a, b):
    # OKLab distance x100: under ~10 is hard to tell apart, 20+ is clearly different
    return 100 * float(np.linalg.norm(hexToOklab(a) - hexToOklab(b)))


def whiteContrast(hex_color):
    # WCAG contrast ratio of a color against white
    rgb = [int(hex_color.lstrip('#')[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lum = sum(w * (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
              for w, c in zip((0.2126, 0.7152, 0.0722), rgb))
    return 1.05 / (lum + 0.05)


def teamColorOptions(team, saved):
    # A team's (primary, alternate) colors: the saved fbPlaychart pair if there is one, else ESPN's
    entry = saved.get(team['espnName'].lower())
    if entry and entry.get('pass') and entry.get('run'):
        pair = [entry['pass'], entry['run']]
        # Saved pairs are darkest first, so put ESPN's primary back in front
        try:
            primary = '#' + str(getTeamInfo(team['id'])[1]).lower().lstrip('#')
            pair.sort(key=lambda c: c.lower() != primary)
        except Exception:
            pass
    else:
        try:
            pair = ['#' + str(c).lower().lstrip('#') for c in getTeamInfo(team['id'])[1:]]
        except Exception as e:
            print(f"Could not fetch ESPN colors for {team['name']} ({type(e).__name__}: {e}).")
            pair = []
    # Drop anything too pale to show on the white chart card
    usable = [c for c in pair if len(c) == 7 and whiteContrast(c) >= MIN_WHITE_CONTRAST]
    return usable or ['#6f6d68']


def divisionColors(teams):
    # Picks one of each team's own colors per division, as far apart as possible, and a stacking order
    saved = loadTeamColorsCsv(TEAM_COLORS_CSV)
    colors, order = {}, {}
    for div in sorted({t['division'] for t in teams}):
        members = [t for t in teams if t['division'] == div]
        options = [teamColorOptions(t, saved) for t in members]

        # Every mix of primary/alternate: keep the one whose closest pair is furthest apart
        def score(choice):
            picked = [opts[k] for opts, k in zip(options, choice)]
            closest = min((colorDistance(a, b) for i, a in enumerate(picked) for b in picked[i + 1:]),
                          default=100)
            return closest - ALTERNATE_PENALTY * sum(choice)
        best = max(product(*[range(len(o)) for o in options]), key=score)
        picked = {t['id']: opts[k] for t, opts, k in zip(members, options, best)}

        # Stack so bands that touch are as different as possible, ties broken by name
        ids = sorted(picked, key=lambda i: next(t['name'] for t in members if t['id'] == i))
        dist = {(a, b): colorDistance(picked[a], picked[b]) for a in ids for b in ids if a != b}
        stack = max(permutations(ids), key=lambda p: (min(dist[a, b] for a, b in zip(p, p[1:])),
                                                     sum(dist[a, b] for a, b in zip(p, p[1:]))))
        colors.update(picked)
        order[div] = list(stack)
    return colors, order


####
# TIE-BREAKERS
####

class TieBreaker:
    # Applies the Sun Belt's division tie-breakers to one simulated season at a time

    def __init__(self, teams, games, cfpRanks):
        self.division = [t['division'] for t in teams]
        self.cfp = cfpRanks                              # team index -> CFP rank
        self.home = [g['h'] for g in games]
        # Each team's games as (game index, opponent index, played at home)
        self.schedule = [[] for _ in teams]
        for gi, g in enumerate(games):
            self.schedule[g['h']].append((gi, g['a'], True))
            self.schedule[g['a']].append((gi, g['h'], False))
        # The game each team plays on the final weekend of the regular season
        self.lastGame = [max(s, key=lambda x: games[x[0]]['startDate'] or '')[0] if s else None
                         for s in self.schedule]

    def load(self, homeWon, pct, rating, rng):
        # Points the tie-breaker at one simulated season
        self.homeWon, self.pct, self.rating, self.rng = homeWon, pct, rating, rng

    def won(self, t, gi):
        # True if team t won game gi in this season
        return bool(self.homeWon[gi]) == (self.home[gi] == t)

    def pctVs(self, t, opps):
        # Team t's winning percentage against a set of opponents, or None if it never played them
        wins = games = 0
        for gi, opp, home in self.schedule[t]:
            if opp in opps:
                games += 1
                wins += bool(self.homeWon[gi]) == home
        return wins / games if games else None

    def best(self, group, values):
        # Keeps the teams with the top value; a team with no value means the step can't compare them
        if any(v is None for v in values):
            return group
        top = max(values)
        return [t for t, v in zip(group, values) if v == top]

    def headToHead(self, group):
        # Record in games among the tied teams
        return self.best(group, [self.pctVs(t, set(group) - {t}) for t in group])

    def divisionRecord(self, group):
        # Record against the rest of the division
        div = self.division[group[0]]
        rivals = {i for i, d in enumerate(self.division) if d == div}
        return self.best(group, [self.pctVs(t, rivals - {t}) for t in group])

    def vsStandings(self, group):
        # Record against the next-best team in the division, working down; tied teams count as one group
        div = self.division[group[0]]
        others = [i for i, d in enumerate(self.division) if d == div and i not in group]
        for level in sorted({self.pct[i] for i in others}, reverse=True):
            opps = {i for i in others if self.pct[i] == level}
            kept = self.best(group, [self.pctVs(t, opps) for t in group])
            # A cut to two teams goes back to the start, so hand it back right away
            if len(kept) <= 2 and len(kept) < len(group):
                return kept
            group = kept
        return group

    def commonOpponents(self, group):
        # Combined record against cross-division conference opponents every tied team played
        div = self.division[group[0]]
        common = set.intersection(*[{opp for _, opp, _ in self.schedule[t]
                                     if self.division[opp] != div} for t in group])
        if not common:
            return group
        return self.best(group, [self.pctVs(t, common) for t in group])

    def cfpRanking(self, group):
        # The highest CFP-ranked tied team is champion if it wins on the final weekend
        ranked = sorted((self.cfp[t], t) for t in group if t in self.cfp)
        if ranked:
            top = ranked[0][1]
            if self.lastGame[top] is not None and self.won(top, self.lastGame[top]):
                return [top]
        return group

    def computerRankings(self, group):
        # The composite computer ranking, stood in for by FPI nudged by simulated results
        return self.best(group, [self.rating[t] for t in group])

    def canWin(self, group, t):
        # True unless a step settled by game results knocks team t out; rankings and coin tosses could go its way
        steps = [self.headToHead, self.divisionRecord, self.vsStandings, self.commonOpponents]
        step = 0
        while len(group) > 1 and step < len(steps):
            kept = steps[step](group)
            if t not in kept:
                return False
            if len(kept) == 1:
                return True
            # Same reversion as champion(): a multi-team tie cut to two starts over
            step = 0 if len(kept) == 2 and len(group) > 2 else step + 1
            group = kept
        return True

    def champion(self, group):
        # Runs the tied teams through the steps; returns (champion, deciding step)
        steps = [self.headToHead, self.divisionRecord, self.vsStandings,
                 self.commonOpponents, self.cfpRanking, self.computerRankings]
        step = 0
        while len(group) > 1 and step < len(steps):
            kept = steps[step](group)
            if len(kept) == 1:
                return kept[0], STEP_NAMES[step]
            # A multi-team tie cut to two starts the two-team steps over from the top
            step = 0 if len(kept) == 2 and len(group) > 2 else step + 1
            group = kept
        # Still tied after every step: the Commissioner's coin toss
        return group[self.rng.integers(len(group))], STEP_NAMES[-1]


def canStillWin(breaker, teams, games, t, fixed):
    # True if any results of the undecided games make team t division champion; fixed maps game index -> home won
    G = len(games)
    div = teams[t]['division']
    rivals = {i for i, x in enumerate(teams) if x['division'] == div}
    decided = dict(fixed)
    # t wins every game still open to it: a title path with a loss there still works with a win
    for gi, g in enumerate(games):
        if gi not in decided and t in (g['h'], g['a']):
            decided[gi] = g['h'] == t

    # Wins so far; t's total is now final and no rival may pass it
    wins = np.zeros(len(teams), dtype=int)
    for gi, homeWon in decided.items():
        wins[games[gi]['h'] if homeWon else games[gi]['a']] += 1
    cap = wins[t]
    if any(wins[r] > cap for r in rivals):
        return False

    # Only games touching this division matter; tightest rivals first so dead ends show up early
    free = [gi for gi, g in enumerate(games) if gi not in decided and (g['h'] in rivals or g['a'] in rivals)]
    slack = lambda i: cap - wins[i] if i in rivals else 99
    free.sort(key=lambda gi: min(slack(games[gi]['h']), slack(games[gi]['a'])))
    homeWon = np.zeros(G, dtype=bool)
    for gi, hw in decided.items():
        homeWon[gi] = hw
    played = np.bincount([g['h'] for g in games] + [g['a'] for g in games], minlength=len(teams))
    tried = [0]

    def search(i):
        # Fill in game free[i] both ways, skipping any result that lifts a rival past t
        tried[0] += 1
        if tried[0] > ELIM_SEARCH_LIMIT:
            raise TimeoutError
        if i == len(free):
            # Every result set: t wins unless a tie-breaker settled by results knocks it out
            group = [r for r in rivals if wins[r] == cap]
            breaker.load(homeWon, wins / np.maximum(played, 1), None, None)
            return breaker.canWin(group, t)
        gi = free[i]
        g = games[gi]
        # Try the result that hands the win to the side with more room first
        for hw in sorted((True, False), key=lambda hw: -slack(g['h'] if hw else g['a'])):
            winner = g['h'] if hw else g['a']
            if winner in rivals and wins[winner] + 1 > cap:
                continue
            wins[winner] += 1
            homeWon[gi] = hw
            if search(i + 1):
                return True
            wins[winner] -= 1
        return False

    try:
        return search(0)
    except TimeoutError:
        # Too many scenarios to rule out: only call a team eliminated when it's proven
        print(f"  Elimination check for {teams[t]['name']} hit its limit; treating it as alive.")
        return True


####
# SIMULATION
####

def simulate(teams, games, fpi, cfpRanks, sims=SIMS, seed=None):
    # Plays out the season sims times; returns (champion index per sim and division, tie-break counts, outcomes)
    rng = np.random.default_rng(seed)
    T, G = len(teams), len(games)
    home = np.array([g['h'] for g in games])
    away = np.array([g['a'] for g in games])
    p = np.array([g['homeOdds'] for g in games])
    unplayed = np.array([g['source'] != 'final' for g in games])

    # One row per simulated season, one column per game: True if the home team won
    homeWon = rng.random((sims, G)) < p

    # Conference wins and games for every team in every season
    wins = np.zeros((sims, T))
    np.add.at(wins.T, home, homeWon.T)
    np.add.at(wins.T, away, ~homeWon.T)
    played = np.bincount(np.concatenate([home, away]), minlength=T)
    pct = wins / np.maximum(played, 1)

    # Wins in unplayed games above or below expectation move a team's computer ranking
    remWins = np.zeros((sims, T))
    np.add.at(remWins.T, home[unplayed], homeWon[:, unplayed].T)
    np.add.at(remWins.T, away[unplayed], ~homeWon[:, unplayed].T)
    expected = np.zeros(T)
    np.add.at(expected, home[unplayed], p[unplayed])
    np.add.at(expected, away[unplayed], 1 - p[unplayed])
    rating = np.array([fpi.get(t['id'], (0.0, None))[0] for t in teams]) \
        + RESULT_WEIGHT * (remWins - expected)

    breaker = TieBreaker(teams, games, cfpRanks)
    divisions = sorted({t['division'] for t in teams})
    champs = np.zeros((sims, len(divisions)), dtype=int)
    steps = {d: {} for d in divisions}
    for di, div in enumerate(divisions):
        members = np.array([i for i, t in enumerate(teams) if t['division'] == div])
        sub = pct[:, members]
        tied = sub == sub.max(axis=1, keepdims=True)
        # Outright winners need no tie-breaker
        champs[:, di] = members[np.argmax(tied, axis=1)]
        # Settle every tied race with the tie-breakers
        for s in np.flatnonzero(tied.sum(axis=1) > 1):
            breaker.load(homeWon[s], pct[s], rating[s], rng)
            champ, how = breaker.champion(list(members[tied[s]]))
            champs[s, di] = champ
            steps[div][how] = steps[div].get(how, 0) + 1
    return divisions, champs, steps, homeWon, wins


def gameSwings(teams, games, champs, homeWon):
    # For each unplayed game, every team's title odds if the home team wins and if it loses
    T = len(teams)
    breaker = TieBreaker(teams, games, {})
    played = {gi: g['homeOdds'] == 1.0 for gi, g in enumerate(games) if g['source'] == 'final'}
    swings = []
    for gi, g in enumerate(games):
        if g['source'] == 'final':
            continue
        hw = homeWon[:, gi]
        moved = []
        # Only report a split once both outcomes come up in the simulations
        if hw.any() and (~hw).any():
            for t in range(T):
                won = (champs == t).any(axis=1)
                ifHome, ifAway = won[hw].mean(), won[~hw].mean()
                if abs(ifHome - ifAway) >= SWING_FLOOR:
                    # A result no simulated season survived gets an exact check for elimination
                    elim = [int(odds == 0 and not canStillWin(breaker, teams, games, t, {**played, gi: hw}))
                            for odds, hw in ((ifHome, True), (ifAway, False))]
                    moved.append([teams[t]['id'], round(float(ifHome), 4), round(float(ifAway), 4)] + elim)
        # Biggest swings first
        moved.sort(key=lambda m: -abs(m[1] - m[2]))
        swings.append((g, moved))
    return swings


####
# CHART & LABELS
####

def gameDayText(game):
    # Kickoff date as 'Sep 5', or blank if unknown
    when = gameDateTime(game)
    return '' if when is None else f"{when:%b} {when.day}"


def runLabel(games):
    # Names a run by the week it comes before ('Before Week 9'), as shown in the run selector
    upcoming = [g for g in games if g['source'] != 'final']
    if not upcoming:
        return 'Final'
    week = upcoming[0].get('week')
    return f"Before Week {week}" if week else f"Before {gameDayText(upcoming[0])}"


def drawChart(divisions, teamRows, figPath, datestring):
    # Draws the posted PNG: one panel of title odds per division, Louisiana Tech in red
    fig, axes = plt.subplots(1, len(divisions), figsize=(16, 8.4))
    for ax, div in zip(np.atleast_1d(axes), divisions):
        rows = sorted((r for r in teamRows if r['division'] == div), key=lambda r: r['odds'])
        names = [r['name'] for r in rows]
        odds = [r['odds'] for r in rows]
        colors = ['#cb333b' if r['id'] == TEAM_ID else '#003087' for r in rows]
        ax.barh(names, odds, color=colors, height=0.62)
        # Odds at the end of each bar
        for y, v in enumerate(odds):
            ax.text(v + 0.012, y, f"{v:.1%}", va='center', fontsize=15, color='#0b0b0b')
        # Same scale in both panels so bars compare across divisions
        ax.set_xlim(0, 1.12)
        ax.set_title(f"{div} Division", fontsize=24, fontweight='bold', loc='left')
        ax.tick_params(axis='y', labelsize=16, length=0)
        ax.set_xticks([])
        for side in ('top', 'right', 'bottom'):
            ax.spines[side].set_visible(False)
    fig.suptitle("Sun Belt Division Title Odds", fontsize=36, fontweight='bold', x=0.02, ha='left')
    fig.text(0.02, 0.9, f"Using ESPN's FPI | {datestring}", fontsize=18, color='#52514e')
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    os.makedirs(os.path.dirname(figPath) or '.', exist_ok=True)
    fig.savefig(figPath, dpi=100, facecolor='white')
    plt.close(fig)
    return figPath


def findBrowser():
    # Returns the path to a Chrome or Chromium binary, or None
    for name in BROWSERS:
        path = name if os.path.isfile(name) else shutil.which(name)
        if path:
            return path
    return None


def renderPreview(page_path, dest):
    # Screenshots the top of the page (logo through the championship card) as the link-preview image
    browser = findBrowser()
    if browser is None:
        print("No Chrome or Chromium found; the preview falls back to the chart.")
        return None
    W, H = PREVIEW_SIZE
    os.makedirs(os.path.dirname(PREVIEW_SHOT) or '.', exist_ok=True)
    # '?preview' trims the page to its top and fits it to the card
    url = Path(page_path).resolve().as_uri() + '?preview'
    # A throwaway profile, so a Chrome that's already open doesn't get in the way
    with tempfile.TemporaryDirectory() as profile:
        cmd = [browser, '--headless=new', '--disable-gpu', '--hide-scrollbars',
               f'--user-data-dir={profile}', f'--window-size={W},{H}',
               f'--force-device-scale-factor={PREVIEW_SCALE}',
               f'--screenshot={os.path.abspath(PREVIEW_SHOT)}', url]
        try:
            subprocess.run(cmd, check=True, timeout=60, capture_output=True)
            img = Image.open(PREVIEW_SHOT).convert('RGB')
        except Exception as e:
            print(f"Could not screenshot the page ({type(e).__name__}: {e}); the preview falls back to the chart.")
            return None
    # Back down to card size from the 2x shot
    img = img.resize(PREVIEW_SIZE, Image.LANCZOS)
    os.makedirs(os.path.dirname(dest) or '.', exist_ok=True)
    img.save(dest, quality=88, optimize=True)
    return os.path.basename(dest)


def writePreviewCard(png_path, dest):
    # Fallback link-preview card: the whole chart centered on a white card
    try:
        img = Image.open(png_path).convert('RGB')
    except Exception as e:
        print(f"Could not read {png_path} ({type(e).__name__}: {e}); the page gets no preview image.")
        return None
    W, H = PREVIEW_SIZE
    scale = min(W / img.width, H / img.height)
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    card = Image.new('RGB', PREVIEW_SIZE, PREVIEW_BG)
    card.paste(img, ((W - img.width) // 2, (H - img.height) // 2))
    os.makedirs(os.path.dirname(dest) or '.', exist_ok=True)
    card.save(dest, quality=88, optimize=True)
    return os.path.basename(dest)


####
# RUN HISTORY
####

def snapshot(teams, games, fpi, divisions, champs, steps, homeWon, wins, when, logos, colors):
    # Packages one run (team odds, tie-break counts and remaining games) as the page reads it
    sims = len(champs)
    breaker = TieBreaker(teams, games, {})
    played = {gi: g['homeOdds'] == 1.0 for gi, g in enumerate(games) if g['source'] == 'final'}
    teamRows = []
    # One row per team: current conference record, projected wins and title odds
    for i, t in enumerate(teams):
        w = sum(1 for g in games if g['source'] == 'final'
                and ((g['h'] == i and g['homeOdds'] == 1) or (g['a'] == i and g['homeOdds'] == 0)))
        l = sum(1 for g in games if g['source'] == 'final' and i in (g['h'], g['a'])) - w
        rating, espnOdds = fpi.get(t['id'], (None, None))
        row = {'id': t['id'], 'name': t['name'], 'abbr': t['abbr'], 'division': t['division'],
               'record': f"{w}-{l}", 'expectedWins': round(float(wins[:, i].mean()), 2),
               'odds': round(float((champs == i).any(axis=1).mean()), 4),
               'espnOdds': None if espnOdds is None else round(espnOdds, 4),
               'fpi': None if rating is None else round(rating, 1)}
        row.update(logos.get(t['id']) or {})
        # A team no simulated season crowned gets the exact check: out for good, or just a long shot
        if row['odds'] == 0 and not canStillWin(breaker, teams, games, i, played):
            row['eliminated'] = True
        if colors[0].get(t['id']):
            row['color'] = colors[0][t['id']]
        teamRows.append(row)

    # Share of races that needed a tie-breaker, and which step settled them
    tiebreaks = {}
    for div in divisions:
        total = sum(steps[div].values())
        tiebreaks[div] = {'share': round(total / sims, 4),
                          'steps': {k: round(v / max(total, 1), 4)
                                    for k, v in sorted(steps[div].items(), key=lambda kv: -kv[1])}}

    # Most likely title-game matchups, one team per division in division order
    pairs, counts = np.unique(champs, axis=0, return_counts=True)
    matchups = [{'teams': [teams[i]['id'] for i in pair], 'odds': round(float(c / sims), 4)}
                for pair, c in sorted(zip(pairs, counts), key=lambda pc: -pc[1])[:MATCHUPS]]

    # Remaining games with how each result moves the races
    remaining = []
    for g, moved in gameSwings(teams, games, champs, homeWon):
        remaining.append({'date': gameDayText(g), 'home': teams[g['h']]['id'],
                          'away': teams[g['a']]['id'], 'homeOdds': g['homeOdds'],
                          'week': g.get('week'), 'source': g['source'], 'swing': moved})

    return {
        'date': when.strftime('%Y-%m-%d'),
        'label': runLabel(games),
        'dateLabel': f"{when:%B} {when.day}, {when.year}",
        'sims': sims,
        'divisions': divisions,
        'teams': teamRows,
        'tiebreaks': tiebreaks,
        'matchups': matchups,
        'flowOrder': colors[1],
        'games': remaining,
    }


def runsJs(data):
    # Formats runs.js by hand, one line per team and game, so it stays readable and diffs cleanly
    out = ['{', '  "years": ' + json.dumps(data['years']) + ',', '  "runs": {']
    years = sorted(data['runs'], key=int)
    for yi, year in enumerate(years):
        runs = data['runs'][year]
        out.append('    "%s": [' % year)
        for ri, r in enumerate(runs):
            out += ['      {',
                    '        "date": %s, "label": %s, "dateLabel": %s, "sims": %s,'
                    % (json.dumps(r['date']), json.dumps(r['label']),
                       json.dumps(r['dateLabel']), json.dumps(r['sims'])),
                    '        "divisions": ' + json.dumps(r['divisions']) + ',',
                    '        "tiebreaks": ' + json.dumps(r['tiebreaks']) + ',',
                    '        "matchups": ' + json.dumps(r.get('matchups', [])) + ',',
                    '        "flowOrder": ' + json.dumps(r.get('flowOrder', {})) + ',']
            # One line per team, then one per remaining game
            for key in ('teams', 'games'):
                out.append('        "%s": [' % key)
                for i, item in enumerate(r[key]):
                    out.append('          ' + json.dumps(item) + (',' if i < len(r[key]) - 1 else ''))
                out.append('        ]' + (',' if key == 'teams' else ''))
            out.append('      }' + (',' if ri < len(runs) - 1 else ''))
        out.append('    ]' + (',' if yi < len(years) - 1 else ''))
    out += ['  }', '}']
    return '\n'.join(out)


def saveRun(season, run, path=None):
    # Adds this run to the run history, replacing any run from the same day
    path = path or RUNS_PATH
    stored = readJsGlobal(path, JS_GLOBAL) or {}
    runs = {str(y): list(v) for y, v in (stored.get('runs') or {}).items()}

    # Drop any run from the same date, then add this one in date order
    season_runs = [r for r in runs.get(str(season), []) if r.get('date') != run['date']]
    replaced = len(season_runs) < len(runs.get(str(season), []))
    season_runs.append(run)
    season_runs.sort(key=lambda r: r['date'])
    runs[str(season)] = season_runs

    # Rewrite runs.js with seasons newest first
    years = sorted((int(y) for y in runs), reverse=True)
    writeJsGlobal(path, JS_GLOBAL, {'years': years, 'runs': runs},
                  header=RUNS_JS_HEADER, dumps=runsJs)
    print(f"{'Replaced' if replaced else 'Added'} the {run['date']} run in {path}: "
          f"{len(season_runs)} runs on file for {season}")
    return path


####
# WEB PAGE
####

def writeSite(season, run, figPath):
    # Writes the page into html/stats/ and its files into html/stats/fbSunBeltPredictor/
    os.makedirs(ASSET_DIR, exist_ok=True)
    shutil.copyfile(PAGE_CSS, os.path.join(ASSET_DIR, CSS_FILENAME))
    shutil.copyfile(PAGE_JS, os.path.join(ASSET_DIR, JS_FILENAME))
    shutil.copyfile(PAGE_STARBURST, os.path.join(ASSET_DIR, STARBURST_FILENAME))
    # Publish the run history the page draws from
    if os.path.isfile(RUNS_PATH):
        shutil.copyfile(RUNS_PATH, os.path.join(ASSET_DIR, RUNS_FILENAME))

    # Links from the page into its asset folder
    asset = lambda name: ASSET_DIR_NAME + '/' + name
    # gtpdd logo for the footer and the browser tab icon
    gtpdd_href = publishAsset(GTPDD_LOGO, WEB_IMG_DIR, ASSET_DIR_NAME + '/')
    # The Sun Belt logo beside the page title
    conf_href = publishConferenceLogo()
    conf_href = asset(conf_href) if conf_href else None
    conf_img = ("<img class='conflogo' src='" + html_escape(conf_href, quote=True)
                + "' alt=''>") if conf_href else ""
    # The logo closes out the page, linking home, as on i20showdown
    footer_logo = ("<img src='" + html_escape(gtpdd_href, quote=True)
                   + "' alt='gtpdd' width='160'>") if gtpdd_href else "gtpdd"
    icon = ("<link rel='icon' href='" + html_escape(gtpdd_href, quote=True) + "'>\n"
            if gtpdd_href else "")

    # Link-preview title and description, led by each division's favorite
    card_title = f"Sun Belt Division Predictor | {season}"
    favorites = []
    for div in run['divisions']:
        top = max((t for t in run['teams'] if t['division'] == div), key=lambda t: t['odds'])
        favorites.append(f"{top['name']} {top['odds']:.0%} in the {div}")
    card_description = ("ESPN's FPI and the Sun Belt tie-breakers make it "
                        + ", ".join(favorites) + ". Odds for every team, run by run.")
    page_url = f"{SITE_URL}/{PAGE_FILENAME}"
    card_image = f"{SITE_URL}/{asset(PREVIEW_FILENAME)}"

    # Fill the page template, escaping plain text
    esc = lambda text: html_escape(str(text), quote=True)
    with open(PAGE_TEMPLATE) as f:
        template = Template(f.read())
    # substitute, not safe_substitute: an unfilled placeholder fails the run instead of shipping
    page = template.substitute(
        title=esc(card_title),
        headLinks=(previewMetaTags(card_title, card_description, page_url, card_image,
                                   twitter_handle=TWITTER_HANDLE) + icon).rstrip('\n'),
        cssHref=esc(asset(CSS_FILENAME)),
        homeUrl=esc(HOME_URL),
        footerLogo=footer_logo,
        confLogo=conf_img,
        highlightId=esc(TEAM_ID),
        assetBase=esc(ASSET_DIR_NAME + '/'),
        runsSrc=esc(asset(RUNS_FILENAME)),
        jsSrc=esc(asset(JS_FILENAME)),
    )
    html_path = os.path.join(HTML_DIR, PAGE_FILENAME)
    with open(html_path, 'w') as f:
        f.write(page)
    print(f"Wrote {html_path}")

    # The link-preview image is a shot of the page just written, or the chart if no browser can take one
    preview_path = os.path.join(ASSET_DIR, PREVIEW_FILENAME)
    if renderPreview(html_path, preview_path) is None:
        writePreviewCard(figPath, preview_path)
    print(f"Wrote {preview_path}")
    return html_path


####
# MAIN
####

def fbSunBeltPredictor(year=None, html=True, sims=SIMS, cfp=None, seed=None):
    # Pull the conference, its schedule and every game's odds
    season = int(year or currentSeason())
    teams = conferenceTeams(season)
    if not teams:
        print(f"ESPN lists no Sun Belt teams for {season}; nothing to predict.")
        return None
    index = {t['id']: i for i, t in enumerate(teams)}
    games = conferenceGames(teams, season)
    print(f"{season}: {len(teams)} teams, {len(games)} conference games")
    for g in games:
        g['h'], g['a'] = index[g['home']], index[g['away']]
    gameOdds(games)
    fpi = powerIndex(season)

    # CFP ranks given by abbreviation (JMU=18) become team index -> rank
    abbrs = {t['abbr'].upper(): i for i, t in enumerate(teams)}
    cfpRanks = {}
    for abbr, rank in (cfp or {}).items():
        if abbr.upper() not in abbrs:
            raise SystemExit(f"--cfp: no Sun Belt team abbreviated '{abbr}' "
                             f"(choices: {', '.join(sorted(abbrs))})")
        cfpRanks[abbrs[abbr.upper()]] = rank

    # Print each remaining game's odds
    for g in games:
        if g['source'] != 'final':
            print(f"  {gameDayText(g):>7}  {teams[g['a']]['name'][:22]:>22} at "
                  f"{teams[g['h']]['name'][:22]:<22} home {g['homeOdds']:.1%}"
                  + ('' if g['source'] == 'fpi' else ' (no FPI, held even)'))

    # Play out the rest of the season and package the run
    divisions, champs, steps, homeWon, wins = simulate(teams, games, fpi, cfpRanks, sims, seed)
    logos = {t['id']: publishTeamLogo(t) for t in teams} if html else {}
    now = datetime.now()
    colors = divisionColors(teams)
    run = snapshot(teams, games, fpi, divisions, champs, steps, homeWon, wins, now, logos, colors)

    # Print the odds, division by division
    for div in divisions:
        print(f"{div} ({run['tiebreaks'][div]['share']:.1%} of races needed a tie-breaker)")
        for t in sorted((t for t in run['teams'] if t['division'] == div), key=lambda t: -t['odds']):
            espn = '' if t['espnOdds'] is None else f"   ESPN {t['espnOdds']:.1%}"
            print(f"  {t['name']:<22} {t['record']:>5}  {t['odds']:6.1%}{espn}")

    # Posted PNG
    drawChart(divisions, run['teams'], FIG_PATH, f"{now:%B} {now.day}, {now.year}")
    print(f"Wrote {FIG_PATH}")

    # File this run and rebuild the page
    if html:
        saveRun(season, run)
        writeSite(season, run, FIG_PATH)
    return run


####
# COMMAND LINE
####

if __name__ == "__main__":
    import argparse

    def cfpArg(text):
        # Parses 'JMU=18' into ('JMU', 18)
        abbr, _, rank = text.partition('=')
        if not abbr or not rank.isdigit():
            raise argparse.ArgumentTypeError("use ABBR=RANK, e.g. JMU=18")
        return abbr, int(rank)

    parser = argparse.ArgumentParser(
        description="Odds on who wins each Sun Belt division, as a PNG and a page "
                    "that keeps every run of the season.")
    parser.add_argument("--year", type=int,
                        help="Season to run (default: the current season)")
    parser.add_argument("--sims", type=int, default=SIMS,
                        help=f"Simulated seasons (default: {SIMS})")
    parser.add_argument("--cfp", type=cfpArg, action="append", default=[],
                        help="A Sun Belt team in the latest CFP rankings, as ABBR=RANK; repeatable")
    parser.add_argument("--seed", type=int, help="Random seed, for repeatable runs")
    parser.add_argument("--no-html", action="store_true",
                        help="Only draw the PNG; leave the page and runs.js alone")
    args = parser.parse_args()

    fbSunBeltPredictor(year=args.year, html=not args.no_html, sims=args.sims,
                       cfp=dict(args.cfp), seed=args.seed)
