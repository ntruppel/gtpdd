# -*- coding: utf-8 -*-
"""
Four factors graphic for the Lady Techsters' most recent game, the women's version of
hoopsAdvancedBoxScore.py, which supplies the factor math and drawing.

CollegeBasketballData has no women's games, so the basketball ratings use the previous
season's D1-vs-D1 team-games from sportsdataverse's ESPN team box score release instead.

Run from the repo root:

    python techstersAdvancedBoxScore.py
"""

####
# IMPORTS
####

import csv
import io
import os
from collections import Counter

import requests

from hoopsAdvancedBoxScore import (FACTORS, ballRating, buildGraphic, factorWinner, formatFactor,
                                   fourFactors, gameInfo, latestGame, loadBenchmarks)
from lib.retroCommon import saveScreen, setMenuBlue

####
# CONSTANTS
####

# ESPN's women's endpoints; Tech's team slug and id are the same as the men's
ESPN_SCHEDULE_URL = ('https://site.api.espn.com/apis/site/v2/sports/basketball/'
                     'womens-college-basketball/teams/{}/schedule?season={}')
ESPN_SUMMARY_URL = ('https://site.api.espn.com/apis/site/v2/sports/basketball/'
                    'womens-college-basketball/summary?event={}')

# File locations
FIG_PATH = 'out/techstersAdvancedBoxScore.png'
BENCHMARK_PATH = 'csv/techstersFourFactorsBenchmarks.csv'

# Season team box scores from sportsdataverse, named by the year the season ends
TEAM_BOX_URL = ('https://github.com/sportsdataverse/sportsdataverse-data/releases/download/'
                'espn_womens_college_basketball_team_boxscores/team_box_{}.csv')

# D1 teams play 25+ games in the file, non-D1 opponents only a handful
D1_MIN_GAMES = 15

# Lady Techsters script logo from Tech's brand site, cached apart from the men's state-T
TECHSTERS_LOGO_URL = ('https://brand.latech.edu/wp-content/uploads/sites/13/2024/03/'
                      'Lady-Techsters-Stacked-RGB-Web-WBB-150ppi.png')
TECHSTERS_LOGO_NAME = 'Lady Techsters'
# The script is wide and short, so it gets a bigger box to stay legible
TECHSTERS_LOGO_SCALE = 1.5

# Lady Techster Blue (PMS 292c) and Tech Red (PMS 1797) from brand.latech.edu
TECHSTERS_COLORS = [(105, 179, 231), (203, 51, 59)]


####
# BENCHMARKS
####

def boxFromRow(row, prefix=''):
    # A team box in the same shape as hoopsAdvancedBoxScore.teamBox, or None if anything's blank
    keys = {'fgm': 'field_goals_made', 'fga': 'field_goals_attempted',
            'tpm': 'three_point_field_goals_made', 'ftm': 'free_throws_made',
            'fta': 'free_throws_attempted', 'tov': 'total_turnovers',
            'orb': 'offensive_rebounds', 'drb': 'defensive_rebounds'}
    try:
        return {k: int(float(row[prefix + col])) for k, col in keys.items()}
    except (KeyError, ValueError):
        return None


def seasonFactors(season):
    # Four factors for every D1-vs-D1 team-game of a season, as {factor key: [values]}
    r = requests.get(TEAM_BOX_URL.format(season + 1), timeout=60)
    r.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(r.text)))

    # The file has no conferences, so D1 teams are the ones with a full schedule in it
    games = Counter(row['team_id'] for row in rows)
    d1 = {team for team, n in games.items() if n >= D1_MIN_GAMES}

    # Each row is one team-game, so its opponent's box is the other row of the same game
    byGame = {(row['game_id'], row['team_id']): row for row in rows}
    values = {f['key']: [] for f in FACTORS}
    for row in rows:
        # Games against non-D1 teams would skew the field
        if row['team_id'] not in d1 or row['opponent_team_id'] not in d1:
            continue
        oppRow = byGame.get((row['game_id'], row['opponent_team_id']))
        box = boxFromRow(row)
        oppBox = boxFromRow(oppRow) if oppRow else None
        if box is None or oppBox is None or not box['fga']:
            continue
        for key, value in fourFactors(box, oppBox).items():
            values[key].append(value)
    return values


####
# MAIN
####

def techstersAdvancedBoxScore(fig_path=FIG_PATH):
    # Find the latest game and print a header line for it
    gameId, season = latestGame(scheduleUrl=ESPN_SCHEDULE_URL)
    teams, where, order, neutral, when, status = gameInfo(gameId, summaryUrl=ESPN_SUMMARY_URL)
    tech, oppo = teams['tech'], teams['oppo']

    # Swap ESPN's state-T and Tech Blue for the Lady Techsters script and Lady Techster Blue
    tech.update({'location': TECHSTERS_LOGO_NAME, 'logo': TECHSTERS_LOGO_URL,
                 'logoScale': TECHSTERS_LOGO_SCALE, 'colors': TECHSTERS_COLORS})
    print(f"{when:%m/%d/%y}: Lady Techsters {tech['points']}, {oppo['name']} {oppo['points']} ({status})")

    # Balls are rated against the season before this game's
    bench = loadBenchmarks(season - 1, path=BENCHMARK_PATH, source=seasonFactors,
                           sourceName='sportsdataverse')

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
        won_by = {'tech': 'Lady Techsters', 'oppo': oppo['name']}.get(winner, 'even')
        balls = {side: ballRating(factor, values[side], bench) for side in values}
        print(f"  {factor['name']:<12} {formatFactor(factor, values['tech']):>7} ({balls['tech']:.1f})"
              f"  vs {formatFactor(factor, values['oppo']):>7} ({balls['oppo']:.1f})"
              f"   avg {formatFactor(factor, bench[factor['key']]['mean']):>6}   -> {won_by}")

    # Draw and save the graphic, with the menu panels in Lady Techster Blue too
    setMenuBlue(TECHSTERS_COLORS[0])
    img = buildGraphic(teams, order, neutral, when, status, factors, won, bench,
                       techName='TECHSTERS')
    path = saveScreen(img, fig_path)
    print(f"Wrote {path}")

    # One-line summary for posting alongside the graphic
    result = 'win' if tech['points'] > oppo['points'] else 'loss'
    status = (f"Four Factors from the Lady Techsters' {tech['points']}-{oppo['points']} {result} "
              f"{where} {oppo['name']}. Tech won {won} of the four factors.")
    print(status)
    return status


####
# COMMAND LINE
####

if __name__ == "__main__":
    techstersAdvancedBoxScore()
