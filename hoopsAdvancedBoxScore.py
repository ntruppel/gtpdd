# -*- coding: utf-8 -*-
"""
Graphic of Dean Oliver's four factors for Louisiana Tech's most recent basketball game.

Each factor (shooting, turnovers, rebounding, free throws) is shown for both offenses,
which covers all eight factors since one team's offense is the other's defense. Stats
come from ESPN's box score; the look is a 16-bit Genesis-era menu screen.

Basketballs rate each number against every D1-vs-D1 team-game of the previous season
(from CollegeBasketballData), one half ball per decile, so an average game is 2.5-3.

Run from the repo root:

    python hoopsAdvancedBoxScore.py
"""

####
# IMPORTS
####

import csv
import os
import time
from datetime import date, datetime, timedelta
from random import Random
from statistics import mean, quantiles
from zoneinfo import ZoneInfo

import cbbd
import requests
from dotenv import load_dotenv

from lib.fbCommon import LOGO_DIR
from lib.retroCommon import (BACKDROP, DIALOG_H, DIALOG_Y, FIELD_TOP, H, PANEL_W, PANEL_X, W,
                             distinctColor, drawCrowd, drawDialog, drawScoreboard, drawTable,
                             hexColors, newScreen, pixelLogo, rect, saveScreen)

# Pull the CFBD API key, which also works for CollegeBasketballData, from .env
load_dotenv()

####
# CONSTANTS
####

# ESPN endpoints and Tech's ids there
ESPN_TEAM = 'latech'
ESPN_TECH_ID = '2348'
ESPN_SCHEDULE_URL = ('https://site.api.espn.com/apis/site/v2/sports/basketball/'
                     'mens-college-basketball/teams/{}/schedule?season={}')
ESPN_SUMMARY_URL = ('https://site.api.espn.com/apis/site/v2/sports/basketball/'
                    'mens-college-basketball/summary?event={}')

# Game dates are shown in Central time
TIMEZONE = ZoneInfo('America/Chicago')

# File locations
FIG_PATH = 'out/hoopsAdvancedBoxScore.png'
BENCHMARK_PATH = 'csv/hoopsFourFactorsBenchmarks.csv'

# CollegeBasketballData caps each call at 3000 rows, so a season is pulled a week at a time
BENCHMARK_WINDOW_DAYS = 7
# Server errors get a few retries, a minute apart as the server asks
BENCHMARK_RETRIES = 4
BENCHMARK_RETRY_WAIT = 60
DECILES = [f"p{n}" for n in range(10, 100, 10)]

# Hardwood and court line colors
WOOD = [(226, 160, 96), (218, 150, 86), (232, 170, 106)]
WOOD_DARK = (198, 130, 74)
WOOD_LIGHT = (242, 186, 126)
COURT_LINE = (36, 22, 18)

# 11x11 basketball sprite: K outline, O leather, S seam, H shine; half cuts through the center seam
BALL = {
    'rows': [
        '...KKKKK...',
        '.KKHOSOOKK.',
        '.KHSOSOSOK.',
        'KHSOOSOOSOK',
        'KHSOOSOOSOK',
        'KSSSSSSSSSK',
        'KOSOOSOOSOK',
        'KOSOOSOOSOK',
        '.KOSOSOSOK.',
        '.KKOOSOOKK.',
        '...KKKKK...',
    ],
    'colors': {'K': (40, 16, 8), 'O': (232, 104, 24), 'S': (96, 36, 12), 'H': (252, 176, 96)},
    'step': 12,                    # sprite width plus a 1px gap
    'half': 6,
}

# Four rows, so each gets more height than the football table's five
ROW_H = 30

# Each factor's label, stat, Dean Oliver's weight, and which direction wins
FACTORS = [
    {'name': 'Shooting', 'stat': 'eFG%', 'key': 'efg', 'weight': 0.40, 'better': 'high'},
    {'name': 'Turnovers', 'stat': 'TOV%', 'key': 'tov', 'weight': 0.25, 'better': 'low'},
    {'name': 'Rebounding', 'stat': 'ORB%', 'key': 'orb', 'weight': 0.20, 'better': 'high'},
    {'name': 'Free Throws', 'stat': 'FT/FGA', 'key': 'ftr', 'weight': 0.15, 'better': 'high'},
]


####
# GAME DATA
####

def espnJson(url):
    # GETs an ESPN endpoint as JSON
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json()


def currentSeason(today=None):
    # Seasons are named for the year they start; July onward counts toward the coming one
    today = today or date.today()
    return today.year if today.month >= 7 else today.year - 1


def latestGame(season=None, scheduleUrl=ESPN_SCHEDULE_URL):
    # (ESPN id, season) of Tech's most recent finished game, looking back a season if needed
    season = season or currentSeason()
    for year in (season, season - 1):
        # ESPN names basketball seasons by the year they end
        schedule = espnJson(scheduleUrl.format(ESPN_TEAM, year + 1))
        done = [e for e in schedule.get('events', [])
                if e['competitions'][0]['status']['type']['completed']]
        if done:
            return max(done, key=lambda e: e['date'])['id'], year
    raise SystemExit("ESPN lists no finished Louisiana Tech games this season or last.")


def splitMadeAttempted(text):
    # '30-57' -> (30, 57)
    made, attempted = str(text).split('-')
    return int(made), int(attempted)


def teamBox(team):
    # Pulls the counting stats the four factors need out of one ESPN box score side
    stats = {s['name']: s['displayValue'] for s in team['statistics']}
    fgm, fga = splitMadeAttempted(stats['fieldGoalsMade-fieldGoalsAttempted'])
    tpm, _ = splitMadeAttempted(stats['threePointFieldGoalsMade-threePointFieldGoalsAttempted'])
    ftm, fta = splitMadeAttempted(stats['freeThrowsMade-freeThrowsAttempted'])
    # Total turnovers include team turnovers like shot clock violations
    tov = stats.get('totalTurnovers') or stats.get('turnovers') or 0
    return {'fgm': fgm, 'fga': fga, 'tpm': tpm, 'ftm': ftm, 'fta': fta, 'tov': int(tov),
            'orb': int(stats['offensiveRebounds']), 'drb': int(stats['defensiveRebounds'])}


def displayName(location):
    # ESPN calls ULL plain 'Louisiana', which reads like the whole state
    return 'Louisiana-Lafayette' if location == 'Louisiana' else location


def teamColors(team):
    # A team's primary and alternate ESPN colors as RGB
    return hexColors(team.get('color'), team.get('alternateColor'))


def gameInfo(gameId, summaryUrl=ESPN_SUMMARY_URL):
    # Both teams' names, logos, scores and box stats, keyed 'tech'/'oppo', plus game details
    summary = espnJson(summaryUrl.format(gameId))
    comp = summary['header']['competitions'][0]

    # Box score stats, logo and colors for each side
    teams = {}
    for side in summary['boxscore']['teams']:
        key = 'tech' if side['team']['id'] == ESPN_TECH_ID else 'oppo'
        teams[key] = {'location': side['team']['location'],
                      'name': displayName(side['team']['location']),
                      'short': side['team'].get('shortDisplayName') or side['team']['location'],
                      'logo': side['team'].get('logo'),
                      'colors': teamColors(side['team']),
                      'box': teamBox(side)}

    # Score and home/away come from the header
    home = False
    for c in comp['competitors']:
        key = 'tech' if c['id'] == ESPN_TECH_ID else 'oppo'
        teams[key]['points'] = int(c.get('score') or 0)
        if key == 'tech':
            home = c['homeAway'] == 'home'

    # Neutral-site games read as 'vs' and treat Tech as the home team
    neutral = bool(comp.get('neutralSite'))
    home = home or neutral
    where = 'vs' if home else 'at'
    # Road team on the left, home team on the right
    order = ('oppo', 'tech') if home else ('tech', 'oppo')
    # ESPN dates are UTC, so convert to Central for the date shown
    when = datetime.fromisoformat(comp['date'].replace('Z', '+00:00')).astimezone(TIMEZONE)
    status = comp['status']['type'].get('shortDetail') or 'Final'
    return teams, where, order, neutral, when, status.upper()


####
# FOUR FACTORS
####

def fourFactors(box, oppBox):
    # One team's offensive four factors; its rebounding needs the opponent's defensive boards
    fga = box['fga']
    possessions = fga + 0.44 * box['fta'] + box['tov']
    boards = box['orb'] + oppBox['drb']
    return {
        'efg': (box['fgm'] + 0.5 * box['tpm']) / fga if fga else 0.0,
        'tov': box['tov'] / possessions if possessions else 0.0,
        'orb': box['orb'] / boards if boards else 0.0,
        'ftr': box['ftm'] / fga if fga else 0.0,
    }


def formatFactor(factor, value):
    # Rates read as percentages, except free throw rate which is conventionally .xxx
    if factor['key'] == 'ftr':
        return f"{value:.3f}".lstrip('0') if value < 1 else f"{value:.2f}"
    return f"{value:.1%}" if value < 0.9995 else "100%"


def factorWinner(factor, values):
    # Returns 'tech', 'oppo', or None for a tie at display precision
    tech, oppo = values['tech'], values['oppo']
    if formatFactor(factor, tech) == formatFactor(factor, oppo):
        return None
    better = tech > oppo if factor['better'] == 'high' else tech < oppo
    return 'tech' if better else 'oppo'


def ballRating(factor, value, bench):
    # Half a ball to start, plus half for each of last season's decile cut points the value beats
    cuts = bench[factor['key']]['cuts']
    if factor['better'] == 'high':
        beaten = sum(value > c for c in cuts)
    else:
        beaten = sum(value < c for c in cuts)
    return 0.5 * (beaten + 1)


####
# BENCHMARKS
####

def cbbdApi(apiClass):
    # Returns a CollegeBasketballData client, e.g. cbbdApi(cbbd.GamesApi), using cfbdAuth
    token = os.environ.get('cfbdAuth')
    if not token:
        raise RuntimeError("No cfbdAuth in the environment or in .env at the repo root.")
    return apiClass(cbbd.ApiClient(cbbd.Configuration(access_token=token)))


def withRetries(call, tries=BENCHMARK_RETRIES):
    # Runs an API call, waiting and retrying when the server is briefly overloaded
    for attempt in range(1, tries + 1):
        try:
            return call()
        except cbbd.exceptions.ServiceException as e:
            if attempt == tries:
                raise
            print(f"CollegeBasketballData returned {e.status}; retrying in {BENCHMARK_RETRY_WAIT}s...")
            time.sleep(BENCHMARK_RETRY_WAIT)


def cbbdBox(stats):
    # A CollegeBasketballData team box in the same shape as teamBox, or None if anything's missing
    try:
        box = {'fgm': stats.field_goals.made, 'fga': stats.field_goals.attempted,
               'tpm': stats.three_point_field_goals.made,
               'ftm': stats.free_throws.made, 'fta': stats.free_throws.attempted,
               'tov': stats.turnovers.total,
               'orb': stats.rebounds.offensive, 'drb': stats.rebounds.defensive}
    except AttributeError:
        return None
    return box if all(v is not None for v in box.values()) else None


def seasonFactors(season):
    # Four factors for every D1-vs-D1 team-game of a season, as {factor key: [values]}
    api = cbbdApi(cbbd.GamesApi)
    values = {f['key']: [] for f in FACTORS}
    seen = set()
    # November through mid-April covers the regular season and every tournament
    start, end = datetime(season, 11, 1), datetime(season + 1, 4, 15)
    while start < end:
        stop = start + timedelta(days=BENCHMARK_WINDOW_DAYS)
        rows = withRetries(lambda: api.get_game_teams(start_date_range=start, end_date_range=stop))
        # A full page means the window was too wide and some games were cut off
        if len(rows) >= 3000:
            print(f"Week of {start:%m/%d/%y} hit the 3000-row cap; some games are missing.")
        for row in rows:
            # Games against non-D1 teams have no conference and would skew the field
            if not row.conference or not row.opponent_conference:
                continue
            # Windows share their edges, so skip any team-game already counted
            if (row.game_id, row.team_id) in seen:
                continue
            seen.add((row.game_id, row.team_id))
            box, oppBox = cbbdBox(row.team_stats), cbbdBox(row.opponent_stats)
            if box is None or oppBox is None or not box['fga']:
                continue
            for key, value in fourFactors(box, oppBox).items():
                values[key].append(value)
        start = stop
    return values


def loadBenchmarks(season, path=BENCHMARK_PATH, source=None, sourceName='CollegeBasketballData'):
    # Mean and decile cut points per factor for a season, built once from source (CBBD by default)
    rows = []
    if os.path.isfile(path):
        with open(path, newline='') as f:
            rows = list(csv.DictReader(f))
    bench = {r['factor']: {'mean': float(r['mean']), 'cuts': [float(r[d]) for d in DECILES]}
             for r in rows if int(r['season']) == season}
    if len(bench) == len(FACTORS):
        return bench

    # Not cached yet, so pull the whole season and work out each factor's deciles
    print(f"Building {season}-{str(season + 1)[-2:]} benchmarks from {sourceName}...")
    values = (source or seasonFactors)(season)
    fresh = []
    for factor in FACTORS:
        vals = values[factor['key']]
        if len(vals) < 100:
            raise SystemExit(f"Only {len(vals)} {season} team-games found; can't build benchmarks.")
        cuts = quantiles(vals, n=10)
        fresh.append({'season': season, 'factor': factor['key'], 'games': len(vals),
                      'mean': round(mean(vals), 4),
                      **{d: round(c, 4) for d, c in zip(DECILES, cuts)}})

    # Keep other seasons' rows, replacing this one's
    rows = [r for r in rows if int(r['season']) != season] + fresh
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['season', 'factor', 'games', 'mean'] + DECILES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {path}")
    return {r['factor']: {'mean': r['mean'], 'cuts': [r[d] for d in DECILES]} for r in fresh}


####
# BACKGROUND
####

def drawCourt(draw, rng, top=FIELD_TOP):
    # Hardwood planks with random grain streaks
    for y in range(top, H):
        draw.line((0, y, W - 1, y), fill=WOOD[(y // 4) % len(WOOD)])
    for _ in range(420):
        x, y = rng.randrange(W), rng.randrange(top, H)
        length = rng.randrange(6, 22)
        draw.line((x, y, x + length, y), fill=rng.choice((WOOD_DARK, WOOD_LIGHT)))

    # Sideline and a three-point arc on each end
    rect(draw, 0, top + 3, W, 2, COURT_LINE)
    draw.arc((-150, 100, 110, 360), -90, 90, fill=COURT_LINE, width=2)
    draw.arc((250, 100, 510, 360), 90, 270, fill=COURT_LINE, width=2)


####
# DRAWING
####

def teamLogo(team, box):
    # Pixel version of a team's ESPN logo, cached under its ESPN location name
    path = os.path.join(LOGO_DIR, f"{team['location']}.png")
    # Wide logos like a script wordmark can ask for a bigger box via logoScale
    box = round(box * team.get('logoScale', 1))
    return pixelLogo(path, team['logo'], team['location'], box)


def factorRows(factors, bench):
    # One table row per factor, with each team's value, balls, and whether it won the factor
    rows = []
    for factor in FACTORS:
        values = factors[factor['key']]
        winner = factorWinner(factor, values)
        rows.append({'name': factor['name'], 'sub': factor['stat'], 'cells': {
            side: {'text': formatFactor(factor, values[side]),
                   'rating': ballRating(factor, values[side], bench), 'won': winner == side}
            for side in values}})
    return rows


def buildGraphic(teams, order, neutral, when, status, factors, won, bench, techName='TECH'):
    # Draws the whole screen at console resolution
    img, draw = newScreen()

    # Same crowd and wood grain every run; the home team is second in order
    rng = Random(2348)
    drawCrowd(draw, rng, teams[order[1]]['colors'], teams[order[0]]['colors'])
    drawCourt(draw, rng)

    # Big logos for the scoreboard, small ones over the table columns
    big = {side: teamLogo(teams[side], 42) for side in teams}
    small = {side: teamLogo(teams[side], 24) for side in teams}

    drawScoreboard(img, draw, teams, order, neutral, when, status, big)
    # Each team's factor wins are highlighted in its own color, skipping any that vanish on the backdrop
    colors = {side: distinctColor(teams[side]['colors'], BACKDROP) for side in teams}
    drawTable(img, draw, ['FOUR', 'FACTORS'], factorRows(factors, bench), order, small, BALL, ROW_H,
              colors)

    # Dialog box with how many factors Tech won
    count = 'ALL' if won == len(FACTORS) else str(won)
    drawDialog(draw, PANEL_X, DIALOG_Y, PANEL_W, DIALOG_H,
               (f'{techName} WON', count, 'OF THE FOUR FACTORS'))
    return img


####
# MAIN
####

def hoopsAdvancedBoxScore(fig_path=FIG_PATH):
    # Find the latest game and print a header line for it
    gameId, season = latestGame()
    teams, where, order, neutral, when, status = gameInfo(gameId)
    tech, oppo = teams['tech'], teams['oppo']
    print(f"{when:%m/%d/%y}: Louisiana Tech {tech['points']}, {oppo['name']} {oppo['points']} ({status})")

    # Balls are rated against the season before this game's
    bench = loadBenchmarks(season - 1)

    # Each side's offensive factors; Tech's defensive ones are the opponent's offense
    techFactors = fourFactors(tech['box'], oppo['box'])
    oppoFactors = fourFactors(oppo['box'], tech['box'])
    factors = {k: {'tech': techFactors[k], 'oppo': oppoFactors[k]} for k in techFactors}

    # Print a text summary of each factor, its balls, last season's average, and who won it
    won = 0
    for factor in FACTORS:
        values = factors[factor['key']]
        winner = factorWinner(factor, values)
        won += winner == 'tech'
        won_by = {'tech': 'Louisiana Tech', 'oppo': oppo['name']}.get(winner, 'even')
        balls = {side: ballRating(factor, values[side], bench) for side in values}
        print(f"  {factor['name']:<12} {formatFactor(factor, values['tech']):>7} ({balls['tech']:.1f})"
              f"  vs {formatFactor(factor, values['oppo']):>7} ({balls['oppo']:.1f})"
              f"   avg {formatFactor(factor, bench[factor['key']]['mean']):>6}   -> {won_by}")

    # Draw and save the graphic
    img = buildGraphic(teams, order, neutral, when, status, factors, won, bench)
    path = saveScreen(img, fig_path)
    print(f"Wrote {path}")

    # One-line summary for posting alongside the graphic
    result = 'win' if tech['points'] > oppo['points'] else 'loss'
    status = (f"Four Factors from Tech's {tech['points']}-{oppo['points']} {result} {where} "
              f"{oppo['name']}. Tech won {won} of the four factors.")
    print(status)
    return status


####
# COMMAND LINE
####

if __name__ == "__main__":
    hoopsAdvancedBoxScore()
