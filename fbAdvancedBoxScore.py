# -*- coding: utf-8 -*-
"""
Graphic of Bill Connelly's five factors for one Louisiana Tech game.

Each factor (efficiency, explosiveness, drive finishing, field position, turnovers)
is shown for both teams from CFBD's advanced box score, with a postgame win expectancy
from CFBD (or a weighted stand-in from the five factors). The look is a 16-bit
Genesis-era menu screen, shared with hoopsAdvancedBoxScore through lib/retroCommon.py.

Footballs rate each number against every FBS-vs-FBS team-game of the previous season,
one half football per decile, so an average game is about 3.

Run from the repo root:

    python fbAdvancedBoxScore.py                  # Tech's most recent finished game
    python fbAdvancedBoxScore.py --week 4         # that week of this season
    python fbAdvancedBoxScore.py --year 2025 --week 14
    python fbAdvancedBoxScore.py --opponent LSU   # by opponent, this season
    python fbAdvancedBoxScore.py --game-id 401757314
"""

####
# IMPORTS
####

import csv
import os
from collections import defaultdict
from random import Random
from statistics import mean

import cfbd
from dotenv import load_dotenv

from lib.fbCommon import (ESPN_LOGO_URL, LOGO_DIR, cfbdApi, currentSeason, getGames,
                          getTeamInfo, localDateTime, resolveEspnId)
from lib.retroCommon import (BLACK, DIALOG_H, DIALOG_Y, FIELD_TOP, H, PANEL_W, PANEL_X, W, WHITE,
                             centerText, dialogFrame, distinctColor, drawCrowd, drawDialog,
                             drawScoreboard, drawShareBar, drawTable, hexColors, newScreen,
                             pixelLogo, rect, saveScreen)

# Pull the CFBD API key and other settings from .env
load_dotenv()

####
# CONSTANTS
####

# Team and file locations
TEAM = 'Louisiana Tech'
FIG_PATH = 'out/fbAdvancedBoxScore.png'
BENCHMARK_PATH = 'csv/fbAdvancedBoxScoreBenchmarks.csv'
BENCHMARK_FIELDS = ['season', 'gameId', 'team', 'opponent',
                    'efficiency', 'explosiveness', 'finishing', 'field', 'turnovers']

# Each factor's label, stat, which direction wins, and display format
FACTORS = [
    {'name': 'Efficiency', 'stat': 'Success %', 'key': 'efficiency', 'better': 'high',
     'fmt': '{:.1%}'},
    {'name': 'Explosive', 'stat': 'IsoPPP', 'key': 'explosiveness', 'better': 'high',
     'fmt': '{:.2f}'},
    {'name': 'Finishing', 'stat': 'Pts/Trip 40', 'key': 'finishing', 'better': 'high',
     'fmt': '{:.1f}'},
    {'name': 'Field Pos.', 'stat': 'Start (Own)', 'key': 'field', 'better': 'high',
     'fmt': '{:.1f}'},
    {'name': 'Turnovers', 'stat': 'Giveaways', 'key': 'turnovers', 'better': 'low',
     'fmt': '{:.0f}'},
]

# How strongly each factor correlates with winning; only used if CFBD has no win expectancy
FACTOR_WEIGHTS = {'explosiveness': 0.86, 'efficiency': 0.83, 'finishing': 0.75,
                  'field': 0.72, 'turnovers': 0.73}

# Mowed turf, five yards to a band, and its painted lines
TURF = [(60, 150, 60), (52, 136, 52)]
TURF_SPECKS = [(44, 120, 44), (76, 166, 68)]
FIELD_LINE = (236, 236, 236)
YARD_BAND = 30                     # pixels per five yards; the 50 sits at the center

# 11x7 football sprite: K outline, O leather, H shine, W laces; half cuts through the middle lace
FOOTBALL = {
    'rows': [
        '...KKKKK...',
        '.KKHHOOOKK.',
        'KOHOWOWOOOK',
        'KOOWWWWWOOK',
        'KOOOWOWOOOK',
        '.KKOOOOOKK.',
        '...KKKKK...',
    ],
    'colors': {'K': (56, 24, 8), 'O': (148, 76, 36), 'H': (196, 124, 72), 'W': (248, 248, 248)},
    'step': 12,                    # sprite width plus a 1px gap
    'half': 6,
}

# Five rows, so each is a bit shorter than the hoops table's four
ROW_H = 24


####
# GAME SELECTION
####

def resolveGame(team=TEAM, year=None, week=None, opponent=None, gameId=None):
    # Returns (game, season); defaults to the most recent finished game
    season = year or currentSeason()
    games = getGames(season, team)
    if not games:
        raise SystemExit(f"CFBD lists no {season} games for {team}.")

    # A game id wins over every other filter
    if gameId is not None:
        match = next((g for g in games if str(g.id) == str(gameId)), None)
        if match is None:
            # The id is only looked up within one season's schedule
            raise SystemExit(f"Game {gameId} isn't in {team}'s {season} schedule. "
                             "Pass --year for the season it was played in.")
        return match, season

    # Otherwise filter by week, then opponent, then fall back to the latest finished game
    if week is not None:
        match = next((g for g in games if g.week == week), None)
        if match is None:
            raise SystemExit(f"{team} has no week {week} game in {season}.")
    elif opponent is not None:
        wanted = opponent.strip().lower()
        match = next((g for g in games
                      if wanted in (g.home_team.lower(), g.away_team.lower())), None)
        if match is None:
            raise SystemExit(f"{team} didn't play '{opponent}' in {season}.")
    else:
        finished = [g for g in games if g.completed]
        if not finished:
            raise SystemExit(f"{team} hasn't finished a game in {season} yet.")
        match = finished[-1]

    # An unplayed game has no box score to chart
    if not match.completed:
        raise SystemExit(f"{team} vs {match.away_team if match.home_team == team else match.home_team}"
                         " hasn't been played yet.")
    return match, season


def gameLabel(game, team=TEAM):
    # Returns (opponent, 'vs'/'at', local kickoff, road/home order) for the header
    home = game.home_team == team
    opponent = game.away_team if home else game.home_team
    # Neutral-site games read as 'vs' and treat Tech as the home team
    home = home or bool(game.neutral_site)
    where = 'vs' if home else 'at'
    # Road team on the left, home team on the right
    order = ('oppo', 'tech') if home else ('tech', 'oppo')
    when = localDateTime(game.start_date) if game.start_date else None
    return opponent, where, when, order


def displayName(name):
    # CFBD and ESPN call ULL plain 'Louisiana', which reads like the whole state
    return 'Louisiana-Lafayette' if name == 'Louisiana' else name


####
# FACTOR STATS
####

def sideIndex(rows, team):
    # CFBD lists the two teams in no fixed order, so find Tech's row by name
    for i, row in enumerate(rows):
        if row.team == team:
            return i, 1 - i
    raise SystemExit(f"CFBD's box score doesn't mention {team}.")


def gameFactors(game, team=TEAM, season=None):
    # Returns the five factors as {'tech': ..., 'oppo': ...} per key, plus both scores
    api = cfbdApi(cfbd.GamesApi)
    adv = api.get_advanced_box_score(int(game.id))
    stats = api.get_game_team_stats(year=season or currentSeason(),
                                    id=int(game.id), team=team)

    # Explosiveness, efficiency and finishing come straight from the advanced box score
    tech, oppo = sideIndex(adv.teams.explosiveness, team)
    values = {
        'explosiveness': (adv.teams.explosiveness[tech].overall.total,
                          adv.teams.explosiveness[oppo].overall.total),
    }
    tech, oppo = sideIndex(adv.teams.success_rates, team)
    values['efficiency'] = (adv.teams.success_rates[tech].overall.total,
                            adv.teams.success_rates[oppo].overall.total)
    tech, oppo = sideIndex(adv.teams.scoring_opportunities, team)
    values['finishing'] = (adv.teams.scoring_opportunities[tech].points_per_opportunity,
                           adv.teams.scoring_opportunities[oppo].points_per_opportunity)
    # CFBD counts yards to the opponent's goal; flip to own yard line so higher is better
    tech, oppo = sideIndex(adv.teams.field_position, team)
    values['field'] = (100 - float(adv.teams.field_position[tech].average_start),
                       100 - float(adv.teams.field_position[oppo].average_start))

    # Score and turnovers come from the regular team game stats
    tech, oppo = sideIndex(stats[0].teams, team)
    points = (stats[0].teams[tech].points, stats[0].teams[oppo].points)
    values['turnovers'] = (teamTurnovers(stats[0].teams[tech]),
                           teamTurnovers(stats[0].teams[oppo]))

    # Treat missing values as zero
    factors = {k: {'tech': float(v[0] or 0), 'oppo': float(v[1] or 0)}
               for k, v in values.items()}
    return factors, int(points[0] or 0), int(points[1] or 0)


def teamTurnovers(side):
    # CFBD returns every stat as a string, so parse the turnovers count
    for stat in side.stats:
        if stat.category == 'turnovers':
            try:
                return float(stat.stat)
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def factorWinner(factor, values):
    # Returns 'tech', 'oppo', or None for a tie
    tech, oppo = values['tech'], values['oppo']
    # Compare at display precision so two identical printed numbers count as a tie
    if factor['fmt'].format(tech) == factor['fmt'].format(oppo):
        return None
    better = tech > oppo if factor['better'] == 'high' else tech < oppo
    return 'tech' if better else 'oppo'


def factorShare(factor, values):
    # Tech's share of a factor on 0..1, pulled toward the middle for the weighted stand-in
    winner = factorWinner(factor, values)
    if winner is None:
        return 0.5
    if factor['key'] == 'turnovers':
        return 1.0 if winner == 'tech' else 0.0   # winning turnovers counts fully
    total = abs(values['tech']) + abs(values['oppo'])
    if total == 0:
        return 0.5
    # Every factor reaching here is higher-is-better, so the winner holds the larger value
    lead = min(max(values['tech'], values['oppo']) / total + 0.4, 1.0)
    return lead if winner == 'tech' else 1 - lead


def winExpectancy(game, factors, team=TEAM):
    # Returns (Tech's postgame win expectancy, source note)
    postgame = (game.home_postgame_win_probability if game.home_team == team
                else game.away_postgame_win_probability)
    # Prefer CFBD's published number
    if postgame is not None:
        return float(postgame), ''

    # Otherwise build a weighted average of the five factor shares
    weighted = sum(FACTOR_WEIGHTS[f['key']] * factorShare(f, factors[f['key']])
                   for f in FACTORS)
    return weighted / sum(FACTOR_WEIGHTS.values()), 'weighted from the five factors'


####
# BENCHMARKS
####

def seasonDrives(season):
    # Field position and finishing for every offense's game, built from CFBD's drive log
    api = cfbdApi(cfbd.DrivesApi)
    starts, trips, points = defaultdict(list), defaultdict(int), defaultdict(int)
    for season_type in ('regular', 'postseason'):
        for d in api.get_drives(year=season, season_type=season_type):
            key = (d.game_id, d.offense)
            starts[key].append(d.start_yards_to_goal)
            # A scoring opportunity is any drive that gets inside the opponent's 40
            if d.end_yards_to_goal is not None and d.end_yards_to_goal <= 40:
                trips[key] += 1
                points[key] += (d.end_offense_score or 0) - (d.start_offense_score or 0)
    # Same definitions as the advanced box score: own yard line, and points per trip (0 with none)
    return {key: {'field': 100 - mean(s),
                  'finishing': points[key] / trips[key] if trips[key] else 0.0}
            for key, s in starts.items() if s}


def seasonTurnovers(season, weeks):
    # Turnovers for every team's game, pulled one week of team stats at a time
    api = cfbdApi(cfbd.GamesApi)
    turnovers = {}
    for season_type, week in sorted(weeks):
        for game in api.get_game_team_stats(year=season, week=week, season_type=season_type):
            for side in game.teams:
                turnovers[(game.id, side.team)] = teamTurnovers(side)
    return turnovers


def seasonTeamGames(season):
    # The five factors for every FBS-vs-FBS team-game of a season, as rows for the benchmark CSV
    fbs = {t.school for t in cfbdApi(cfbd.TeamsApi).get_fbs_teams(year=season)}
    # Efficiency and explosiveness for the whole season come in one call
    adv = [a for a in cfbdApi(cfbd.StatsApi).get_advanced_game_stats(year=season)
           if a.team in fbs and a.opponent in fbs]
    drives = seasonDrives(season)
    turnovers = seasonTurnovers(season, {(a.season_type.value, a.week) for a in adv})

    # Keep team-games that every source covers
    rows = []
    for a in adv:
        key = (a.game_id, a.team)
        if key not in drives or key not in turnovers or a.offense is None:
            continue
        rows.append({'season': season, 'gameId': a.game_id, 'team': a.team,
                     'opponent': a.opponent,
                     'efficiency': round(a.offense.success_rate or 0, 4),
                     'explosiveness': round(a.offense.explosiveness or 0, 4),
                     'finishing': round(drives[key]['finishing'], 4),
                     'field': round(drives[key]['field'], 4),
                     'turnovers': turnovers[key]})
    return rows


def loadBenchmarks(season, path=BENCHMARK_PATH):
    # Every team-game value per factor for a season, built from CFBD once and cached
    rows = []
    if os.path.isfile(path):
        with open(path, newline='') as f:
            rows = list(csv.DictReader(f))
    games = [r for r in rows if int(r['season']) == season]

    # Not cached yet, so pull the whole season and add it to the file
    if not games:
        print(f"Building {season} benchmarks from CFBD...")
        games = seasonTeamGames(season)
        if len(games) < 100:
            raise SystemExit(f"Only {len(games)} {season} team-games found; can't build benchmarks.")
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=BENCHMARK_FIELDS)
            writer.writeheader()
            writer.writerows(rows + games)
        print(f"Wrote {len(games)} team-games to {path}")
    return {f['key']: sorted(float(g[f['key']]) for g in games) for f in FACTORS}


def ballRating(factor, value, bench):
    # Half a football per decile of last season's team-games this value beats; ties count half
    vals = bench[factor['key']]
    below = sum(v < value for v in vals)
    above = sum(v > value for v in vals)
    beaten = below if factor['better'] == 'high' else above
    share = (beaten + 0.5 * (len(vals) - below - above)) / len(vals)
    return 0.5 + 0.5 * min(int(share * 10), 9)


####
# TEAMS
####

def teamInfo(name, points):
    # Display names, score, ESPN colors and logo location for one team
    espn_id = resolveEspnId(name)
    colors = None
    # Look up the team's two colors from ESPN
    if espn_id is not None:
        try:
            _, color1, color2 = getTeamInfo(str(espn_id))
            colors = hexColors(color1, color2)
        except Exception as e:
            print(f"Could not fetch ESPN colors for '{name}' ({type(e).__name__}: {e}).")
    return {'name': displayName(name), 'short': name, 'points': points,
            'colors': colors or hexColors(None),
            'logoPath': os.path.join(LOGO_DIR, f"{name}.png"),
            'logoUrl': ESPN_LOGO_URL.format(espn_id) if espn_id else None, 'cfbd': name}


def teamLogo(team, box):
    # Pixel version of a team's ESPN logo, cached under its CFBD name
    return pixelLogo(team['logoPath'], team['logoUrl'], team['cfbd'], box)


####
# DRAWING
####

def drawField(draw, rng, top=FIELD_TOP):
    # Turf mowed in five-yard bands, with grass specks
    for x in range(W):
        draw.line((x, top, x, H - 1), fill=TURF[(x // YARD_BAND) % len(TURF)])
    for _ in range(900):
        draw.point((rng.randrange(W), rng.randrange(top, H)), fill=rng.choice(TURF_SPECKS))

    # Sideline, a yard line every five yards, and one-yard ticks along the sideline
    rect(draw, 0, top + 3, W, 2, FIELD_LINE)
    for x in range(0, W + 1, YARD_BAND):
        rect(draw, x - 1, top + 5, 2, H - top - 5, FIELD_LINE)
    for x in range(0, W, YARD_BAND // 5):
        rect(draw, x, top + 6, 1, 3, FIELD_LINE)


def factorRows(factors, bench):
    # One table row per factor, with each team's value, footballs, and whether it won the factor
    rows = []
    for factor in FACTORS:
        values = factors[factor['key']]
        winner = factorWinner(factor, values)
        rows.append({'name': factor['name'], 'sub': factor['stat'], 'cells': {
            side: {'text': factor['fmt'].format(values[side]),
                   'rating': ballRating(factor, values[side], bench), 'won': winner == side}
            for side in values}})
    return rows


def buildGraphic(teams, order, neutral, when, factors, won, share, source, bench):
    # Draws the whole screen at console resolution
    img, draw = newScreen()

    # Same crowd and turf every run; the home team is second in order
    rng = Random(2348)
    drawCrowd(draw, rng, teams[order[1]]['colors'], teams[order[0]]['colors'])
    drawField(draw, rng)

    # Big logos for the scoreboard, small ones over the table columns
    big = {side: teamLogo(teams[side], 42) for side in teams}
    small = {side: teamLogo(teams[side], 24) for side in teams}

    drawScoreboard(img, draw, teams, order, neutral, when, 'FINAL', big)
    drawTable(img, draw, ['FIVE', 'FACTORS'], factorRows(factors, bench), order, small,
              FOOTBALL, ROW_H)

    # Two dialog boxes: factors Tech won, and its postgame win expectancy
    boxW = (PANEL_W - 8) // 2
    count = 'ALL' if won == len(FACTORS) else str(won)
    drawDialog(draw, PANEL_X, DIALOG_Y, boxW, DIALOG_H, ('TECH WON', count, 'OF THE 5 FACTORS'))
    drawWinBar(draw, PANEL_X + PANEL_W - boxW, DIALOG_Y, boxW, teams, order, share, source)
    return img


def drawWinBar(draw, x, y, w, teams, order, share, source):
    # Dialog box with Tech's win expectancy as a stacked bar in both teams' colors
    dialogFrame(draw, x, y, w, DIALOG_H)
    centerText(draw, x + w / 2, y + 8, 'ESTIMATED WIN EXP.' if source else 'POSTGAME WIN EXP.',
               WHITE, shadow=BLACK)
    # Tech's primary color, and whichever opponent color doesn't look like it
    techColor = teams['tech']['colors'][0]
    oppoColor = distinctColor(teams['oppo']['colors'], techColor)
    # Show a decimal near 0% or 100% so a blowout never reads as a flat 100%
    label = '{:.0%}'.format(share) if 0.01 <= share <= 0.99 else '{:.1%}'.format(share)
    drawShareBar(draw, x + 8, y + 20, w - 16, 26, share, techColor, oppoColor,
                 order[0] == 'tech', label)


####
# MAIN
####

def fbAdvancedBoxScore(team=TEAM, year=None, week=None, opponent=None, gameId=None,
                       fig_path=FIG_PATH):
    # Find the game and print a header line for it
    game, season = resolveGame(team, year, week, opponent, gameId)
    oppo_name, where, when, order = gameLabel(game, team)
    date_text = f"{when:%m/%d/%y}" if when else ''
    print(f"{season} week {game.week}: {team} {where} {oppo_name} ({date_text})")

    # Pull the stats, work out win expectancy, and load last season's benchmarks
    factors, tech_pts, oppo_pts = gameFactors(game, team, season)
    share, source = winExpectancy(game, factors, team)
    bench = loadBenchmarks(season - 1)

    # Print a text summary of each factor, its footballs, last season's average, and who won it
    won = 0
    for factor in FACTORS:
        values = factors[factor['key']]
        winner = factorWinner(factor, values)
        won += winner == 'tech'
        won_by = {'tech': team, 'oppo': oppo_name}.get(winner, 'even')
        balls = {side: ballRating(factor, values[side], bench) for side in values}
        average = factor['fmt'].format(mean(bench[factor['key']]))
        print(f"  {factor['name']:<11} {factor['fmt'].format(values['tech']):>6} ({balls['tech']:.1f})"
              f"  vs {factor['fmt'].format(values['oppo']):>6} ({balls['oppo']:.1f})"
              f"   avg {average:>6}   -> {won_by}")
    print(f"  {'Win expectancy':<16} {share:>9.1%}   ({source or 'CFBD'})")

    # Gather per-team names, scores, colors and logos, then draw and save the graphic
    teams = {'tech': teamInfo(team, tech_pts), 'oppo': teamInfo(oppo_name, oppo_pts)}
    img = buildGraphic(teams, order, bool(game.neutral_site), when, factors, won, share, source,
                       bench)
    path = saveScreen(img, fig_path)
    print(f"Wrote {path}")

    # One-line summary for posting alongside the graphic
    status = (f"Advanced box score from Tech's game {where} {oppo_name}. Based on how "
              f"the game was played, Tech wins it {share:.1%} of the time.")
    print(status)
    return status


####
# COMMAND LINE
####

if __name__ == "__main__":
    import argparse

    # Every option is optional; with none, the most recent finished game is charted
    parser = argparse.ArgumentParser(
        description="Five-factor advanced box score for a Louisiana Tech game "
                    "(defaults to the most recent finished one).")
    parser.add_argument("--year", type=int, help="Season (default: the current one)")
    parser.add_argument("--week", type=int, help="Week of that season")
    parser.add_argument("--opponent", help="Opponent name, e.g. 'LSU'")
    parser.add_argument("--game-id", dest="gameId", help="CFBD game id, if you have it")
    args = parser.parse_args()

    fbAdvancedBoxScore(year=args.year, week=args.week, opponent=args.opponent,
                       gameId=args.gameId)
