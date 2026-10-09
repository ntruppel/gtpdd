# -*- coding: utf-8 -*-
"""
Created on Wed Nov  2 18:06:08 2022

@author: ntrup

Every play of a Louisiana Tech game drawn on a football field, saved as a PNG and
an interactive HTML page for playcharts.gtpdd.dog. Page templates live in
lib/html/fbPlaychart/.

Run from the repo root:

    python fbPlaychart.py --year 2025 --week 4                  # from the cached CSV
    python fbPlaychart.py --year 2025 --week 4 --refresh-data   # re-pull from CFBD
"""

####
# IMPORTS
####

import json
import os
import re
import shutil
from html import escape as html_escape
from string import Template

import cfbd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.patheffects as path_effects
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Rectangle
from matplotlib.path import Path
from matplotlib.textpath import TextPath
import numpy as np
import pandas as pd
from dotenv import load_dotenv

from lib.common import copyMissingFiles
from lib.fbCommon import (LOGO_DIR, TEAM_COLORS_CSV, assetSlug, cfbdApi, downloadLogo,
                          gameDateTime, getGames, kickoffText, loadColors, loadVenues,
                          loadYears, lookupEspnId, previewMetaTags, publishAsset,
                          teamColors, teamLogo, trimmedLogo, writeJsGlobal)

# Pull the CFBD API key and other settings from .env
load_dotenv()

####
# CONSTANTS
####

BACKGROUND_COLOR = "#d6e8cf"  # muted light green

# Site, file and logo locations
HOME_URL = "https://gtpdd.dog"
SITE_URL = "https://playcharts.gtpdd.dog"  # the published root of html/fbPlaychart/
SITE_TITLE = "gtpdd's Football Playcharts"
TWITTER_HANDLE = "@gotechplsdntdie"
PREVIEW_DIR = 'previewImages'      # one link-preview card per page, beside the pages
PREVIEW_WIDTH = 1200               # a summary_large_image card is 1200x600
HTML_DIR = "html/fbPlaychart"
PBP_DIR = "csv/fbPlaychartPBP"
ESPN_CONF_LOGO_URL = "https://a.espncdn.com/i/teamlogos/ncaa_conf/500/{}.png"
ESPN_CONFERENCE_IDS_CSV = "csv/espnConferenceIDs.csv"
LOGO_DRAW_PX = 72                 # logos are shrunk to this before drawing
# html/fbPlaychart/ is the site root, so everything a page links to must live under it
SITE_DIR = HTML_DIR
WEB_LOGO_DIR = os.path.join(SITE_DIR, 'logo')
WEB_IMG_DIR = os.path.join(SITE_DIR, 'img')
PAGE_TO_ROOT = '../'              # pages sit at <root>/<year>/
GTPDD_LOGO = 'img/gtpdd_logo.png'  # the nav logo, published alongside the charts

# Drive headers: logos sized by height, with a width cap so wordmarks don't run long
SCOREBOARD_LOGO_H = 4.2           # yards tall for a logo in the drive header
SCOREBOARD_LOGO_W = 7.0           # yards wide at most
SCOREBOARD_GAP = 1.8              # yards between the pieces of a drive header
POSSESSION_GAP = 2.0              # yards below the logo row for the clock/possession line
# Clock and possession arrow share a line under the logos
SCOREBOARD_SUBLINE = SCOREBOARD_LOGO_H / 2 + POSSESSION_GAP
CLOCK_FONTSIZE = 8               # smaller than the score above it
HEADER_TEXT_COLOR = 'black'       # the logos carry the team colors, so the text stays neutral
POSSESSION_ARROW_H = 2 / 3        # arrow height as a fraction of its length
POSSESSION_ARROW_PT = 8           # arrow length in points

# Vertical spacing of plays, dividers and drives
PLAY_GAP = 4                      # vertical pitch from one play row to the next
DIVIDER_GAP = 6                   # clear yards on each side of a divider, centering it between plays
DRIVE_GAP = 14                    # vertical room reserved above a drive for its header
DRIVE_HEADER_Y = 9.0              # header sits this far above the drive's first play

# Final scoreboard, a drive header at FINAL_SCALE times the size
FINAL_SCALE = 2
FINAL_LOGO_PX = LOGO_DRAW_PX * FINAL_SCALE  # re-read the logos bigger rather than upscaling
FINAL_FONTSIZE = 24
FINAL_LABEL = "Final"
FINAL_SUBLINE = SCOREBOARD_LOGO_H * FINAL_SCALE / 2 + POSSESSION_GAP

# Venue/kickoff/attendance block between the top yard numbers and the first drive
GAME_INFO_TOP = -2.0              # first info line, just below the top yard numbers
GAME_INFO_LINE_GAP = 3.6
GAME_INFO_FONTSIZE = 9
# Conference wordmarks are much wider than tall, so they get their own size limits
GAME_INFO_LOGO_H = 4.0            # yards tall at most
GAME_INFO_LOGO_W = 20.0           # yards wide at most
GAME_INFO_LOGO_PX = 300           # raster size, so a wide wordmark doesn't come out soft
GAME_INFO_BOTTOM_GAP = 6.0        # clear yards between the last info line and the first drive header

# Arrow key beside the info header: one column per team, pointing the way it drives
KEY_ROWS = (('run', 'Run'), ('pass', 'Pass'), ('penalty', 'Penalty'))
KEY_ARROW_LEN = 7.0               # yards from the tail to the tip of a sample arrow
KEY_ROW_GAP = 5.0                 # vertical pitch between key rows
KEY_LABEL_PAD = 1.2               # yards between an arrow and its label
KEY_FONTSIZE = 8
KEY_LOGO_H = 3.6                  # the team logo that heads each key
KEY_LOGO_W = 6.5
KEY_LOGO_GAP = 5.0                # room under the logo before the first row
KEY_INSET = 2.0                   # yards inside the goal line, so a key clears the endzone
# Logo center to last row center, the same measure gameInfoHeight reports
KEY_HEIGHT = KEY_LOGO_H / 2 + KEY_LOGO_GAP + (len(KEY_ROWS) - 1) * KEY_ROW_GAP

# Colors that don't come from either team
DIVIDER_COLOR = 'black'           # halftime and overtime rules, with their labels
QUARTER_DIVIDER_COLOR = 'dimgray' # quarter breaks are the same rule, a shade lighter
NON_TEAM_COLORS = {'penalty': 'white', 'safety': 'navy', 'fumble': 'navy'}

# Play type -> which team color its arrow uses
PLAY_COLOR_KEYS = {
    'Pass Reception': 'pass',
    'Passing Touchdown': 'pass',
    'Pass Incompletion': 'pass',
    'Rush': 'run',
    'Rushing Touchdown': 'run',
    'Penalty': 'penalty',
    'Sack': 'run',                       # sacks reuse the run color
    'Pass Interception Return': 'pass',   # interceptions reuse the pass color
    'Interception Return Touchdown': 'pass',
    'Safety': 'safety',
    'Fumble Recovery (Opponent)': 'run',
    'FG Recovery (Opponent)': 'run',       # a blocked kick the defense picks up
    'Fumble Return Touchdown': 'run',

}

# Turnovers drawn as a hatched arrow, with the label shown below the head
FUMBLE_TURNOVER_LABELS = {
    'Fumble Recovery (Opponent)': ' Fumble! ',
    'FG Recovery (Opponent)': ' Block FG Return! ',
}
FUMBLE_TURNOVER_TYPES = tuple(FUMBLE_TURNOVER_LABELS)

# CFBD writes kick and punt distances two different ways ("kickoff 65" / "kickoff for 65")
KICKOFF_YARDS_RE = re.compile(r'kickoff\s+(?:for\s+)?(\d+)', re.IGNORECASE)
PUNT_YARDS_RE = re.compile(r'punt\s+(?:for\s+)?(\d+)', re.IGNORECASE)
RETURN_YARDS_RE = re.compile(r'return(?:ed|s)?\s+(?:for\s+)?(\d+)', re.IGNORECASE)

KICKOFF_TYPES = ('Kickoff', 'Kickoff Return (Offense)')
# A punt return TD is one row like any other punt, split the same way
PUNT_TYPES = ('Punt', 'Punt Return', 'Punt Return Touchdown')


####
# PLAY-BY-PLAY DATA
####

def pbpDir(year):
    # Cached play-by-play is grouped by season, e.g. 2025 -> 'csv/fbPlaychartPBP/2025'
    return os.path.join(PBP_DIR, str(year))


def getPBPData(year=2024, week=1, team='Louisiana Tech'):
    # Pulls a week's plays from CFBD, cleans them up, and caches each game as a CSV
    api_response = cfbdApi(cfbd.PlaysApi).get_plays(year, week=week, team=team)

    dictList = []
    for play in api_response:
        # Yard lines are flipped so Tech always drives toward x=100
        start = play.yardline
        if start is not None and play.home != team:
            start = 100 - start
        # Treat a bare "Interception" identically to a "Pass Interception Return"
        play_type = 'Pass Interception Return' if play.play_type == 'Interception' else play.play_type
        # "Pass Completion" is the same thing as "Pass Reception"
        if play_type == 'Pass Completion':
            play_type = 'Pass Reception'
        dictList.append({
            'game_id': play.game_id,
            'offense': play.offense,
            'clock': f"Q{play.period} {play.clock.minutes}:{play.clock.seconds}",
            'down': play.down,
            'distance': play.distance,
            'type': play_type,
            'start': start,
            'gained': play.yards_gained,
            'text': play.play_text,
            'id': play.id,
            'offense_score': play.offense_score,
            'defense_score': play.defense_score,
        })

    # Remove duplicate plays (identical apart from their id)
    seen, deduped = set(), []
    for d in dictList:
        key = tuple(v for k, v in d.items() if k != 'id')
        if key not in seen:
            seen.add(key)
            deduped.append(d)
    dictList = deduped

    # Separate games if CFBD mixed two into one week's pull (G1 2025)
    games = {}
    for d in dictList:
        games.setdefault(d['game_id'], []).append(d)
    built = [buildGame(plays, team, week, year) for plays in games.values()]
    # Stop and ask for a rename when more than one game came back
    if len(built) > 1:
        print(f"\nWARNING: the Week {week} pull returned {len(built)} games (the data source merged them):")
        for g_df, g_opp in built:
            path = os.path.join(pbpDir(year), f"fbPlaychartPBP_{gameSlug(week, g_opp)}.csv")
            print(f"  - vs {g_opp}: {len(g_df)} plays -> {path}")
        print(f"Each was split into its own CSV (all named wk{week}). Rename the extra game(s)\n"
              "to the correct week, then re-run with refreshData=False for the game you want.\n")
        raise SystemExit(1)
    return built[0][0]


# Penalty yards come unsigned, so direction comes from the text's spots ("from TECH20 to TECH25")
PENALTY_SPOT_RE = re.compile(
    r'\byards?\s+from\s+([A-Za-z]+)\s*(\d{1,2})\s+to\s+([A-Za-z]+)\s*(\d{1,2})\b')


def penaltySides(df):
    # Returns team abbreviation -> 0 or 100, the end of the field its yard numbers count from
    sides = {}
    # Settled per game, since a spot at the 50 can't tell the two halves apart
    for row in df.itertuples():
        if getattr(row, 'type', None) != 'Penalty' or pd.isna(row.start):
            continue
        m = PENALTY_SPOT_RE.search(str(row.text or ''))
        if not m:
            continue
        abbr, yards, start = m.group(1).upper(), int(m.group(2)), float(row.start)
        if yards == 50 or abbr in sides:
            continue
        # The 'from' spot is where the play started, which the row already states
        if abs(yards - start) <= 1:
            sides[abbr] = 0
        elif abs((100 - yards) - start) <= 1:
            sides[abbr] = 100
    return sides


def spotX(abbr, yards, sides):
    # Converts a '<ABBR><yards>' spot to an x on the 0-100 field, or None if unknown
    if abbr in sides:
        return yards if sides[abbr] == 0 else 100 - yards
    # With only two teams, an unplaced abbreviation is whichever half the other isn't
    halves = set(sides.values())
    if len(halves) == 1:
        return yards if 100 in halves else 100 - yards
    return None


def fixPenaltyYards(df, team):
    # Re-signs every penalty's yards from its play text; safe to run more than once
    if 'type' not in df.columns or 'gained' not in df.columns:
        return df
    sides = penaltySides(df)
    gains = list(df['gained'])
    for i, row in enumerate(df.itertuples()):
        if row.type != 'Penalty' or pd.isna(row.start):
            continue
        m = PENALTY_SPOT_RE.search(str(row.text or ''))
        if not m:
            continue  # a declined or offsetting flag spells out no spots
        from_x = spotX(m.group(1).upper(), int(m.group(2)), sides)
        to_x = spotX(m.group(3).upper(), int(m.group(4)), sides)
        # Keep CFBD's number if the 'from' spot doesn't match the play's start
        if from_x is None or to_x is None or abs(from_x - float(row.start)) > 1:
            continue
        gains[i] = (to_x - from_x) if row.offense == team else (from_x - to_x)
    df['gained'] = gains
    return df


def buildGame(plays, team, week, year):
    # Turns one game's raw plays into chart rows and saves them as a CSV; returns (df, opponent)
    opponent = next((d['offense'] for d in plays if d['offense'] and d['offense'] != team), team)

    processed = []
    for d in plays:
        text = str(d.get('text') or '')

        # Kickoff touchback: CFBD credits the kicking team, so flip it to the receiver
        if d['type'] in KICKOFF_TYPES and 'touchback' in text.lower():
            d['offense'] = opponent if d['offense'] == team else team
            d['type'] = 'Kickoff'
            d['gained'] = -65
            processed.append(d)

            touchback = dict(d)
            touchback['type'] = 'Touchback'
            touchback['start'] = 0 if touchback['offense'] == team else 100
            touchback['gained'] = 25
            processed.append(touchback)

        # Every other kickoff, plus a return row when the text has return yards
        elif d['type'] in KICKOFF_TYPES:
            d['offense'] = opponent if d['offense'] == team else team
            d['type'] = 'Kickoff'
            ko_match = KICKOFF_YARDS_RE.search(text)
            if ko_match:
                d['gained'] = -int(ko_match.group(1))
            processed.append(d)

            return_match = RETURN_YARDS_RE.search(text)
            if return_match:
                catch = d['start'] + d['gained'] if d['offense'] == team else d['start'] - d['gained']
                kick_return = dict(d)
                kick_return['type'] = 'Kickoff Return (Offense)'
                kick_return['start'] = catch
                kick_return['gained'] = int(return_match.group(1))
                processed.append(kick_return)

        # Punts: distance comes from the text, then a touchback or return row for the receiver
        elif d['type'] in PUNT_TYPES:
            return_type = ('Punt Return Touchdown' if d['type'] == 'Punt Return Touchdown'
                           else 'Punt Return')
            d['type'] = 'Punt'
            punt_match = PUNT_YARDS_RE.search(text)
            if punt_match:
                d['gained'] = int(punt_match.group(1))
            processed.append(d)

            if 'touchback' in text.lower():
                receiving = opponent if d['offense'] == team else team
                touchback = dict(d)
                touchback['type'] = 'Touchback'
                touchback['offense'] = receiving
                touchback['start'] = 0 if receiving == team else 100
                touchback['gained'] = 20
                processed.append(touchback)
            else:
                return_match = RETURN_YARDS_RE.search(text)
                if return_match:
                    # Tech's punts travel toward x=100, the opponent's toward x=0
                    catch = d['start'] + d['gained'] if d['offense'] == team else d['start'] - d['gained']
                    punt_return = dict(d)
                    punt_return['type'] = return_type
                    punt_return['offense'] = opponent if d['offense'] == team else team
                    punt_return['start'] = catch
                    punt_return['gained'] = int(return_match.group(1))
                    # Scores swap with possession so the next drive header reads them the right way round
                    punt_return['offense_score'] = d['defense_score']
                    punt_return['defense_score'] = d['offense_score']
                    processed.append(punt_return)

        # Interception into the endzone becomes a touchback
        elif 'Interception' in d['type'] and 'touchback' in text.lower():
            processed.append(d)
            intercepting = opponent if d['offense'] == team else team
            touchback = dict(d)
            touchback['type'] = 'Touchback'
            touchback['offense'] = intercepting
            touchback['start'] = 0 if intercepting == team else 100
            touchback['gained'] = 20
            processed.append(touchback)

        else:
            processed.append(d)

    df = pd.DataFrame(processed)

    # CFBD can return plays out of order, so sort by quarter, clock, then play id
    clock_parts = df['clock'].str.extract(r'Q(\d+)\s+(\d+):(\d+)').astype(float)
    df['_period'] = clock_parts[0]
    df['_secs_remaining'] = clock_parts[1] * 60 + clock_parts[2]
    df['_id'] = pd.to_numeric(df['id'], errors='coerce')
    df = (df.sort_values(['_period', '_secs_remaining', '_id'], ascending=[True, False, True], kind='stable')
            .drop(columns=['_period', '_secs_remaining', '_id'])
            .reset_index(drop=True))

    # CFBD's yards are wrong for interception returns and unreturned kicks, so end those at the next play
    stop_types = {'End Period', 'End of Half', 'Timeout', 'End of Game'}
    starts, types, offs, gains = (list(df[c]) for c in ('start', 'type', 'offense', 'gained'))
    for i in range(len(df)):
        if pd.isna(starts[i]):
            continue
        # Find the next real play, skipping clock stoppages
        j = i + 1
        while j < len(df) and types[j] in stop_types:
            j += 1
        if types[i] == 'Pass Interception Return':
            pass  # always redraw an interception return to the next play
        elif types[i] == 'Punt' and (j >= len(df) or
                                     types[j] not in ('Punt Return', 'Punt Return Touchdown', 'Touchback')):
            pass  # a punt with no return/touchback: end the arrow at the next play
        elif types[i] == 'Kickoff' and (j >= len(df) or types[j] not in ('Kickoff Return (Offense)', 'Touchback')):
            pass  # a kickoff with no return/touchback: end the line at the next play
        else:
            continue
        if j >= len(df) or pd.isna(starts[j]):
            continue
        end_x, start_i = starts[j], starts[i]
        gains[i] = (end_x - start_i) if offs[i] == team else (start_i - end_x)
    df['gained'] = gains

    # Give the punt before a punt return TD the pre-return score, so the TD doesn't show a play early
    for i in range(2, len(df)):
        if df.at[i, 'type'] != 'Punt Return Touchdown' or df.at[i - 1, 'type'] != 'Punt':
            continue
        before = df.loc[i - 2]
        if pd.isna(before['offense_score']) or pd.isna(before['defense_score']):
            continue
        same = before['offense'] == df.at[i - 1, 'offense']
        df.at[i - 1, 'offense_score'] = before['offense_score' if same else 'defense_score']
        df.at[i - 1, 'defense_score'] = before['defense_score' if same else 'offense_score']

    fixPenaltyYards(df, team)

    # Per-game CSV: csv/fbPlaychartPBP/<year>/fbPlaychartPBP_wk<week>_<opponent>.csv
    df = df.drop(columns=['game_id'], errors='ignore')
    csv_dir = pbpDir(year)
    os.makedirs(csv_dir, exist_ok=True)
    df.to_csv(os.path.join(csv_dir, f"fbPlaychartPBP_{gameSlug(week, opponent)}.csv"))
    return df, opponent


####
# GAME INFO HEADER
####

def gameInfoPath(year, week, opponent):
    # Cached game record: csv/fbPlaychartPBP/<year>/fbPlaychartGame_wk<week>_<opponent>.json
    return os.path.join(pbpDir(year), f"fbPlaychartGame_{gameSlug(week, opponent)}.json")


def fetchGameInfo(year, week, team, opponent):
    # Returns the CFBD game record, flattened to the fields the header shows
    games = getGames(year, team)
    if not games:
        return None

    # Match on opponent, preferring the requested week if there are two meetings
    want = str(opponent).strip().lower()
    matches = [g for g in games
               if want in (str(g.home_team).strip().lower(), str(g.away_team).strip().lower())]
    if not matches:
        print(f"CFBD has no {year} {team} game against '{opponent}'; the info header is skipped.")
        return None
    game = next((g for g in matches if g.week == week), matches[0])

    venue = loadVenues().get(game.venue_id, {})
    conference = game.home_conference if game.home_team == team else game.away_conference
    return {
        'venue': game.venue,
        'city': venue.get('city'),
        'state': venue.get('state'),
        'timezone': venue.get('timezone'),
        'capacity': venue.get('capacity'),
        'attendance': game.attendance,
        'startDate': game.start_date.isoformat() if game.start_date else None,
        'startTimeTbd': bool(game.start_time_tbd),
        'neutralSite': bool(game.neutral_site),
        'conferenceGame': bool(game.conference_game),
        'conference': conference,
        'notes': game.notes,
        'homeTeam': game.home_team,
        'awayTeam': game.away_team,
    }


def gameInfo(year, week, team, opponent, refresh=False):
    # Returns the cached game record, pulling it from CFBD the first time
    path = gameInfoPath(year, week, opponent)
    if not refresh and os.path.isfile(path):
        try:
            with open(path) as f:
                return json.load(f)
        except (ValueError, OSError):
            pass  # unreadable cache: pull a fresh copy below
    info = fetchGameInfo(year, week, team, opponent)
    if info is not None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(info, f, indent=2)
        print(f"Wrote {path}")
    return info


def gameInfoRows(info):
    # Returns the info header's lines: text, or ('logo', array, link) for a conference logo
    rows = []
    notes = str(info.get('notes') or '').strip()
    if notes:
        rows.append(notes)  # bowl or championship game name

    # Matchup line
    home, away = info.get('homeTeam'), info.get('awayTeam')
    conference = info.get('conference') if info.get('conferenceGame') else None
    if home and away:
        matchup = f"{away} vs. {home}" if info.get('neutralSite') else f"{away} at {home}"
        if info.get('neutralSite'):
            matchup += " (neutral site)"
        rows.append(matchup)

    # League games are marked with the conference logo, or its name if there's no logo
    if conference:
        logo = conferenceLogo(conference, GAME_INFO_LOGO_PX)
        rows.append(('logo', logo, publishLogo(conference)) if logo is not None
                    else f"{conference} game")

    # Kickoff, venue and attendance lines
    kickoff = kickoffText(info)
    if kickoff:
        rows.append(kickoff)

    where = ', '.join(x for x in (info.get('city'), info.get('state')) if x)
    venue = ' • '.join(x for x in (info.get('venue'), where) if x)
    if venue:
        rows.append(venue)

    attendance, capacity = info.get('attendance'), info.get('capacity')
    if attendance:
        line = f"Attendance: {attendance:,}"
        if capacity:
            line += f" ({attendance / capacity:.0%} of {capacity:,})"
        rows.append(line)
    return rows


def gameInfoHeight(rows):
    # Yards from the first info line to the last, by drawGameInfo's own spacing
    total = sum(fitLogo(row[1], GAME_INFO_LOGO_W, GAME_INFO_LOGO_H)[1] if isinstance(row, tuple)
                else GAME_INFO_LINE_GAP for row in rows)
    return max(total - GAME_INFO_LINE_GAP, 0.0)


def drawGameInfo(ax, rows, top=GAME_INFO_TOP):
    # Draws the info header down the middle of the field; returns the y of its last row
    y = top
    first_text = True
    for row in rows:
        # A conference logo takes up as much room as its own height needs
        if isinstance(row, tuple):
            size = fitLogo(row[1], GAME_INFO_LOGO_W, GAME_INFO_LOGO_H)
            y += (size[1] - GAME_INFO_LINE_GAP) / 2
            drawLogo(ax, row[1], 50, y, size=size, href=row[2])
            y += (size[1] + GAME_INFO_LINE_GAP) / 2
            continue
        # The first text line is bold and a point larger
        ax.text(50, y, row, fontsize=GAME_INFO_FONTSIZE + (1 if first_text else 0),
                fontweight='bold' if first_text else 'normal',
                va='center', ha='center', color=HEADER_TEXT_COLOR)
        first_text = False
        y += GAME_INFO_LINE_GAP
    return y - GAME_INFO_LINE_GAP


def drawColorKey(ax, colors, top, logo, team, side, href=None):
    # Draws one team's arrow key (side=1 left goal line, -1 right); returns its bottom y
    tail = KEY_INSET if side > 0 else 100 - KEY_INSET
    label_x = tail + side * (KEY_ARROW_LEN + KEY_LABEL_PAD)
    ha = 'left' if side > 0 else 'right'
    widest = max(textWidthYards(text, KEY_FONTSIZE, weight='normal') for _, text in KEY_ROWS)
    center = tail + side * (KEY_ARROW_LEN + KEY_LABEL_PAD + widest) / 2

    # The logo sits in a fixed-height band so both columns' rows line up
    if logo is not None:
        drawLogo(ax, logo, center, top + KEY_LOGO_H / 2,
                 size=fitLogo(logo, KEY_LOGO_W, KEY_LOGO_H), href=href)
    else:
        # No logo, so name the team instead
        ax.text(center, top + KEY_LOGO_H / 2, team, fontsize=KEY_FONTSIZE,
                fontweight='bold', va='center', ha='center', color=HEADER_TEXT_COLOR)

    # One sample arrow and label per key row
    y = top + KEY_LOGO_H + KEY_LOGO_GAP
    for key, text in KEY_ROWS:
        drawArrow(ax, tail, y, side * KEY_ARROW_LEN, colors[key], penalty=(key == 'penalty'))
        ax.text(label_x, y, text, fontsize=KEY_FONTSIZE, va='center', ha=ha,
                color=HEADER_TEXT_COLOR)
        y += KEY_ROW_GAP
    return y - KEY_ROW_GAP


####
# LOGOS & LAYOUT HELPERS
####

# Inches of figure per data unit, equal on both axes so the play arrows keep their shape
UNITS_PER_INCH = 13.0
X_RANGE = 126  # xlim spans -13 .. 113


def readLogo(path, draw_px):
    # Loads a cached logo as an RGBA array, trimmed and shrunk to chart size
    from PIL import Image as PILImage
    img = trimmedLogo(path)
    if img is None:
        return None
    img.thumbnail((draw_px, draw_px), PILImage.LANCZOS)
    return np.asarray(img)


def publishLogo(name, gray=False):
    # Publishes a cached logo under the site root and returns its page-relative link
    src = os.path.join(LOGO_DIR, f"{name}.png")
    if not os.path.isfile(src):
        return None
    img = trimmedLogo(src)
    if img is None:
        return None
    filename = assetSlug(name) + ('_gray' if gray else '') + '.png'
    # Grayscale copy for the losing team on the final scoreboard
    if gray:
        from PIL import Image as PILImage
        img = PILImage.merge('RGBA', (*([img.convert('L')] * 3), img.split()[3]))
    os.makedirs(WEB_LOGO_DIR, exist_ok=True)
    img.save(os.path.join(WEB_LOGO_DIR, filename))
    return PAGE_TO_ROOT + 'logo/' + filename


def writePreviewCard(png_path, html_dir, html_filename):
    # Saves the top 2:1 slice of the chart (matchup, info and opening drive) as the link-preview image
    from PIL import Image as PILImage
    try:
        img = PILImage.open(png_path).convert('RGB')
    except Exception as e:
        print(f"Could not read {png_path} ({type(e).__name__}: {e}); the page gets no preview image.")
        return None
    card = img.crop((0, 0, img.width, min(img.height, img.width // 2)))
    card = card.resize((PREVIEW_WIDTH, round(PREVIEW_WIDTH * card.height / card.width)),
                       PILImage.LANCZOS)
    preview_dir = os.path.join(html_dir, PREVIEW_DIR)
    os.makedirs(preview_dir, exist_ok=True)
    filename = html_filename[:-len('.html')] + '.png'
    card.save(os.path.join(preview_dir, filename))
    return filename


def conferenceLogo(conference, draw_px=LOGO_DRAW_PX):
    # Loads a conference's ESPN logo, downloading it into logo/ the first time
    path = os.path.join(LOGO_DIR, f"{conference}.png")
    if not os.path.isfile(path):
        conf_id = lookupEspnId(conference, ESPN_CONFERENCE_IDS_CSV)
        if conf_id is None:
            print(f"No ESPN id for '{conference}' in {ESPN_CONFERENCE_IDS_CSV}; "
                  "the info header will name the conference instead.")
            return None
        if not downloadLogo(ESPN_CONF_LOGO_URL.format(conf_id), path, conference):
            return None
    return readLogo(path, draw_px)


def textWidthYards(text, fontsize, weight='bold'):
    # Width of a rendered string in field yards, so header pieces can be laid out by hand
    if not text:
        return 0.0
    path = TextPath((0, 0), text, size=fontsize, prop=FontProperties(weight=weight))
    return path.get_extents().width / 72.0 * UNITS_PER_INCH


def possessionArrow(direction):
    # Marker triangle pointing the way this offense drives, flattened vertically
    tip, base, half = 0.5 * direction, -0.5 * direction, POSSESSION_ARROW_H / 2
    return Path([(base, -half), (tip, 0.0), (base, half), (base, -half)],
                [Path.MOVETO, Path.LINETO, Path.LINETO, Path.CLOSEPOLY])


def fitLogo(logo, max_w, max_h):
    # Drawn (width, height) in yards: the logo's own aspect ratio, inside a box
    height_px, width_px = logo.shape[0], logo.shape[1]
    scale = min(max_h / height_px, max_w / width_px)
    return width_px * scale, height_px * scale


def logoSize(logo, scale=1.0):
    # Drive-header size for a team's logo
    return fitLogo(logo, SCOREBOARD_LOGO_W * scale, SCOREBOARD_LOGO_H * scale)


def grayscaleLogo(logo):
    # Luminance copy of a logo, transparency untouched, for the team that lost
    gray = logo[..., :3].astype(float) @ np.array([0.299, 0.587, 0.114])
    out = logo.copy()
    out[..., :3] = gray[..., None].astype(logo.dtype)
    return out


# SVG gid -> published logo link, so externalLogos() can swap out the embedded base64 copies
LOGO_HREFS = {}


def logoGid(href):
    # Registers a published logo link and returns the gid to tag its drawn image with
    gid = f"logo{len(LOGO_HREFS)}"
    LOGO_HREFS[gid] = href
    return gid


def drawLogo(ax, logo, x, y, scale=1.0, size=None, href=None):
    # Draws a logo centered on (x, y), at drive-header size unless a size is given
    width, height = size if size is not None else logoSize(logo, scale)
    image = ax.imshow(logo, extent=(x - width / 2, x + width / 2, y + height / 2, y - height / 2),
                      aspect='auto', zorder=6, interpolation='antialiased')
    if href:
        image.set_gid(logoGid(href))


####
# SCOREBOARDS & FIELD
####

def drawScoreboard(ax, y, clock_text, poss_text, tech_score, oppo_score,
                   techLogo, oppoLogo, color, fallback_text, techHasBall, fontsize=12,
                   logoFiles=None):
    # Draws a drive header: logos around the score, with the clock and possession arrow below
    ax.text(50, y + SCOREBOARD_SUBLINE, clock_text, fontsize=CLOCK_FONTSIZE,
            fontweight='bold', va='center', ha='center', color=HEADER_TEXT_COLOR)

    if techLogo is None or oppoLogo is None:
        # No logos to point at, so name the team that has the ball instead
        ax.text(50, y, f"{fallback_text} | {poss_text}", fontsize=fontsize,
                fontweight='bold', va='center', ha='center', color=color)
        return

    # Score in the middle, each team's logo beside it
    score_text = f"{tech_score} - {oppo_score}"
    score_half = textWidthYards(score_text, fontsize) / 2
    tech_width, oppo_width = logoSize(techLogo)[0], logoSize(oppoLogo)[0]

    tech_x = 50 - score_half - SCOREBOARD_GAP - tech_width / 2
    oppo_x = 50 + score_half + SCOREBOARD_GAP + oppo_width / 2
    ax.text(50, y, score_text, fontsize=fontsize, fontweight='bold',
            va='center', ha='center', color=HEADER_TEXT_COLOR)
    logoFiles = logoFiles or {}
    drawLogo(ax, techLogo, tech_x, y, href=logoFiles.get('tech'))
    drawLogo(ax, oppoLogo, oppo_x, y, href=logoFiles.get('oppo'))

    # Possession arrow under the team with the ball
    arrow_x = tech_x if techHasBall else oppo_x
    arrow_half = POSSESSION_ARROW_PT / 72.0 * UNITS_PER_INCH / 2
    # Pad the clock width (TextPath measures a bit narrow) and push the arrow clear of it
    clear = textWidthYards(clock_text, CLOCK_FONTSIZE) * 1.1 / 2 + arrow_half + SCOREBOARD_GAP
    if abs(arrow_x - 50) < clear:
        arrow_x = 50 + clear * (1 if arrow_x >= 50 else -1)
    ax.plot([arrow_x], [y + SCOREBOARD_SUBLINE],
            marker=possessionArrow(1 if techHasBall else -1), markersize=POSSESSION_ARROW_PT,
            color=color, alpha=0.75, linestyle='None', zorder=6)


def drawFinalScoreboard(ax, y, tech_score, oppo_score, techLogo, oppoLogo,
                        techWon, oppoWon, color, fallback_text, logoFiles=None):
    # Draws the final score: a drive header at twice the size, with the loser's logo in gray
    if techLogo is None or oppoLogo is None:
        # No logos to gray out, so name the winner in its own color
        ax.text(50, y, fallback_text, fontsize=18, fontweight='bold',
                va='center', ha='center', color=color)
        return

    score_text = f"{tech_score} - {oppo_score}"
    score_half = textWidthYards(score_text, FINAL_FONTSIZE) / 2
    tech_width = logoSize(techLogo, FINAL_SCALE)[0]
    oppo_width = logoSize(oppoLogo, FINAL_SCALE)[0]
    gap = SCOREBOARD_GAP * FINAL_SCALE

    ax.text(50, y, score_text, fontsize=FINAL_FONTSIZE, fontweight='bold',
            va='center', ha='center', color=HEADER_TEXT_COLOR)
    logoFiles = logoFiles or {}
    drawLogo(ax, techLogo if techWon else grayscaleLogo(techLogo),
             50 - score_half - gap - tech_width / 2, y, FINAL_SCALE,
             href=logoFiles.get('tech' if techWon else 'tech_gray'))
    drawLogo(ax, oppoLogo if oppoWon else grayscaleLogo(oppoLogo),
             50 + score_half + gap + oppo_width / 2, y, FINAL_SCALE,
             href=logoFiles.get('oppo' if oppoWon else 'oppo_gray'))
    ax.text(50, y + FINAL_SUBLINE, FINAL_LABEL, fontsize=CLOCK_FONTSIZE * FINAL_SCALE,
            fontweight='bold', va='center', ha='center', color=HEADER_TEXT_COLOR)


def drawYardNumbers(ax, y, upside_down):
    # Draws the yard numbers across the field, upside down for the far sideline
    rotation = 180 if upside_down else 0
    for yard in range(10, 100, 10):
        digits = list(str(min(yard, 100 - yard)))  # e.g. ['4', '0']
        if upside_down:
            digits = digits[::-1]
        left, right = digits
        for digit, dx in ((left, -1.1), (right, 1.1)):
            ax.text(yard + dx, y, digit, color='white', fontsize=11, fontweight='bold',
                    va='center', ha='center', rotation=rotation, zorder=2)

        # Small triangle pointing toward the nearest goal line
        if yard != 50:
            marker, mx = ('<', yard - 3.2) if yard < 50 else ('>', yard + 3.2)
            ax.plot([mx], [y], marker=marker, markersize=3, color='white',
                    linestyle='None', zorder=2)


def setupChart(techColor, oppoColor):
    # Creates the figure with the field, endzones, yard lines and top yard numbers
    plt.rcParams['image.composite_image'] = False  # keep logos as separate images so each keeps its gid
    fig, ax = plt.subplots()
    fig.patch.set_facecolor(BACKGROUND_COLOR)
    ax.set_facecolor(BACKGROUND_COLOR)
    ax.set_xlim(-13, 113)

    # Endzones: Tech's color on the left (-13..0), opponent's on the right (100..113)
    ax.axvspan(-13, 0, color=techColor, zorder=-1)
    ax.axvspan(100, 113, color=oppoColor, zorder=-1)

    # White yard lines every 10 from 0 to 100; 0/50/100 drawn thicker
    for yard in range(0, 101, 10):
        lw = 3 if yard in (0, 50, 100) else 1
        ax.axvline(yard, color='white', linewidth=lw, zorder=0)

    # Yard numbers along the top, upside down (far-sideline view from above)
    drawYardNumbers(ax, -6, upside_down=True)

    return fig, ax


####
# PLAYS
####

def formatClock(clock):
    # Zero-pads the seconds, e.g. 'Q1 5:7' -> 'Q1 5:07'
    try:
        head, secs = str(clock).rsplit(':', 1)
        return f"{head}:{int(secs):02d}"
    except (ValueError, AttributeError):
        return str(clock)


def finalScore(df, team):
    # Returns (tech score, opponent score) from the last row that carries a score
    for row in reversed(list(df.itertuples())):
        if pd.isna(row.offense_score) or pd.isna(row.defense_score):
            continue
        if row.offense == team:
            return int(row.offense_score), int(row.defense_score)
        return int(row.defense_score), int(row.offense_score)
    return None


def quarterOf(clock):
    # Period number from a clock string like 'Q5 0:19'; None if it doesn't parse
    m = re.match(r'\s*Q(\d+)', str(clock))
    return int(m.group(1)) if m else None


def overtimeLabel(period):
    # Periods past the 4th are overtimes: Q5 -> 'OT1', Q6 -> 'OT2', ...
    return f"OT{period - 4}"


def drawDivider(ax, y, label, color=DIVIDER_COLOR):
    # Full-width rule with a boxed label, used for halftime, quarter breaks and each overtime
    ax.axhline(y, color=color, linewidth=3, zorder=5)
    ax.text(50, y, f" {label} ", fontsize=12, fontweight='bold',
            va='center', ha='center', color=color,
            bbox=dict(facecolor=BACKGROUND_COLOR, edgecolor=color, pad=3), zorder=6)


def periodBreak(row):
    # Returns (label, color) for the divider at the end of a period, or None
    period = quarterOf(row.clock)
    if row.type == 'End of Half' or period == 2:
        return 'Halftime', DIVIDER_COLOR
    if period in (1, 3):
        return f"Start Q{period + 1}", QUARTER_DIVIDER_COLOR
    return None


def playColor(playType, colors):
    # Returns the team color for a play type
    key = PLAY_COLOR_KEYS.get(playType)
    if key:
        return colors[key]
    print(playType)
    return 'green'  # Catchall for unlisted. If we see green, there's a problem


def shortenArrow(disp):
    # Pulls an arrow's length in so its head ends on the spot rather than past it
    sign = 1 if disp >= 0 else -1
    return sign * max(abs(disp) - 1.9, 0.6)


def playGeometry(row, team, techColors, oppoColors):
    # Returns colors and directions for drawing a play, mirrored by which team has the ball
    gained = row.gained
    if row.offense == team:
        dx = shortenArrow(gained)  # tech drives toward x=100
        return {
            'colors': techColors,
            'pos_gained': dx,
            'neg_gained': dx,
            'fg_yards': 200,
            'oppo_endzone': 0,
            'oppo_endzone_mid': -7,
            'endzone': 100,
            'endzone_mid': 107,
            'marker': '>',
            'ha': 'left',
            'zha': 'right',
            'direction': 1,
        }
    else:
        dx = shortenArrow(-gained)  # opponent drives toward x=0
        return {
            'colors': oppoColors,
            'pos_gained': dx,
            'neg_gained': dx,
            'fg_yards': -100,
            'oppo_endzone': 100,
            'oppo_endzone_mid': 107,
            'endzone': 0,
            'endzone_mid': -7,
            'marker': '<',
            'ha': 'right',
            'zha': 'left',
            'direction': -1,
        }


# Special-teams and non-scrimmage rows get no first-down line or down label
NO_FIRST_DOWN_TYPES = {
    'Kickoff', 'Onside Kickoff', 'Kickoff Return (Offense)', 'Return Touchdown', 'Touchback',
    'Punt', 'Punt Return', 'Punt Return Touchdown',
    'Field Goal Good', 'Field Goal Missed', 'Blocked Field Goal',
}

# Any kickoff starts a new drive
KICKOFF_DRIVE_TYPES = ('Kickoff', 'Onside Kickoff')


def ordinalDown(down):
    # Down number as the label text: 1 -> '1', 2 -> '2', ...; blank if not 1-4
    return {1: '1', 2: '2', 3: '3', 4: '4'}.get(int(down), '')


# Yards of clearance between the flat tail of the arrow and the down label
DOWN_LABEL_PAD = 0.8


# Interceptions get a white hatch so they stand out whatever the team color
INTERCEPTION_HATCH = '///'
INTERCEPTION_HATCH_COLOR = 'white'
# Penalties get a goldenrod hatch so they don't blend into gold team colors (e.g. LSU)
PENALTY_HATCH = '/////'
PENALTY_HATCH_COLOR = 'goldenrod'


def drawArrow(ax, x, y, dx, color, interception=False, penalty=False, fumble=False):
    # Draws a play arrow, with a hatch overlay for turnovers and penalties
    ax.arrow(x, y, dx, 0, width=3.5, head_width=3.5, head_length=0.9,
             facecolor=color, edgecolor='black', linewidth=0.5)
    if interception or fumble:  # fumble turnovers reuse the interception hatch
        ax.arrow(x, y, dx, 0, width=3.5, head_width=3.5, head_length=0.9,
                 facecolor='none', edgecolor=INTERCEPTION_HATCH_COLOR,
                 linewidth=0, hatch=INTERCEPTION_HATCH, zorder=3)
    if penalty:
        ax.arrow(x, y, dx, 0, width=3.5, head_width=3.5, head_length=0.9,
                 facecolor='none', edgecolor=PENALTY_HATCH_COLOR,
                 linewidth=0, hatch=PENALTY_HATCH, zorder=3)


def drawPlay(ax, row, i, geo):
    # Draws one play at row height i, styled by its play type
    start = row.start
    playType = row.type

    # Faint orange first-down line: "distance" yards downfield from the start
    if playType not in NO_FIRST_DOWN_TYPES and pd.notna(row.distance):
        first_down = start + geo['direction'] * row.distance
        ax.plot([first_down, first_down], [i - 1.8, i + 1.8],
                color='orange', alpha=0.2, linewidth=2, zorder=1)

    # Small black down label just behind the arrow's tail, off the team-color fill
    if playType not in NO_FIRST_DOWN_TYPES and pd.notna(row.down):
        if row.gained == 0:
            arrow_sign = geo['direction']
        else:
            arrow_sign = 1 if geo['pos_gained'] >= 0 else -1
        label = ax.text(start - arrow_sign * DOWN_LABEL_PAD, i, ordinalDown(row.down),
                        fontsize=6, color='black', va='center',
                        ha='right' if arrow_sign > 0 else 'left', zorder=6)
        # Thin white halo for when the label lands on an endzone
        label.set_path_effects([path_effects.withStroke(linewidth=0.8, foreground='white')])

    # Kickoff, drawn as a dashed line like a punt
    if playType == 'Kickoff':
        ko_marker = '<' if geo['marker'] == '>' else '>'
        ax.text(start, i+0.5, " Kickoff ", fontsize=8, va='top', ha=geo['zha'])
        ax.plot([start, start + geo['pos_gained']], [i, i], '--', marker=ko_marker, markersize=1, linewidth=2, color='black')

    # Onside kickoff
    elif playType == 'Onside Kickoff':
        dx = geo['pos_gained']
        ko_marker = '>' if dx >= 0 else '<'
        ax.text(start, i+0.5, " Kickoff ", fontsize=8, va='top', ha=geo['zha'])
        ax.plot([start, start + dx], [i, i], '--', marker=ko_marker, markersize=1, linewidth=2, color='black')
        ax.text(start + dx, i+0.5, " Onside! ", fontsize=8, fontweight='bold', va='top',
                ha='right' if dx < 0 else 'left')

    # Kickoff return
    elif playType == 'Kickoff Return (Offense)':
        ax.text(start, i+0.5, " Return ", fontsize=8, va='top', ha=geo['ha'])
        ax.plot([start, start + geo['pos_gained']], [i, i], '--', marker=geo['marker'], markersize=1, linewidth=2, color='black')

    # Kick or punt returned for a touchdown
    elif playType in ('Return Touchdown', 'Punt Return Touchdown'):
        ax.text(start, i+0.5, " Return ", fontsize=8, va='top', ha=geo['ha'])
        ax.plot([start, start + geo['pos_gained']], [i, i], '--', marker=geo['marker'], markersize=1, linewidth=2, color='black')

        text_obj=ax.text(geo['endzone_mid'], i, "  TD!  ", weight='bold', fontsize=20, color='white', va='center', ha='center')

        text_obj.set_path_effects([
            path_effects.PathPatchEffect(offset=(2, -2), hatch='xxxx', facecolor='gray'),
            path_effects.withStroke(linewidth=1, foreground="black")
        ])

    # Touchback
    elif playType == 'Touchback':
            ax.text(start, i+0.5, " Touchback ", fontsize=8, va='top', ha=geo['ha'])
            ax.plot([start, start + geo['pos_gained']], [i, i], '--', marker=geo['marker'], markersize=1, linewidth=2, color='black')

    # Field goal good
    elif playType == 'Field Goal Good':
        ax.plot([start, geo['fg_yards']], [i, i], '--', marker='P', markersize=8, linewidth=4, color='green')
        text_obj = ax.text(geo['endzone_mid'], i, " FG! ", weight='bold', fontsize=20, color='white', va='center', ha='center')

        text_obj.set_path_effects([
                        path_effects.PathPatchEffect(offset=(2, -2), hatch='xxxx', facecolor='gray'),
                        path_effects.withStroke(linewidth=1, foreground="black")
                    ])

    # Field goal missed or blocked
    elif playType in ('Field Goal Missed', 'Blocked Field Goal'):
        ax.plot([start, start + geo['fg_yards']], [i, i], '--', marker='X', markersize=8, linewidth=4, color='gray')
        ax.text(start, i+1, " FG Miss! ", weight='bold', fontsize=10, color='black', va='top', ha=geo['ha'])

    # Punt
    elif playType == 'Punt':
        ax.text(start, i+0.5, " Punt ", fontsize=8, va='top', ha=geo['ha'])
        ax.plot([start, start + geo['pos_gained']], [i, i], '--', marker=geo['marker'], markersize=1, linewidth=2, color='black')

    # Punt return
    elif playType == 'Punt Return':
        ax.text(start, i+0.5, " Return ", fontsize=8, va='top', ha=geo['ha'])
        ax.plot([start, start + geo['pos_gained']], [i, i], '--', marker=geo['marker'], markersize=1, linewidth=2, color='black')

    # Bare interception (normally renamed to 'Pass Interception Return' on pull)
    elif playType == 'Interception':
        ax.text(start, i, 'INTERCEPTION', color='purple', fontsize='40', ha=geo['ha'])

    # Interception returned for a touchdown: hatched arrow into the far endzone
    elif playType == 'Interception Return Touchdown':
        color = playColor(playType, geo['colors'])
        drawArrow(ax, start, i, -1 * (start - geo['oppo_endzone']), color, interception=True)
        ax.text(start, i+2, " Interception! ", fontsize=8, va='top', ha=geo['zha'])
        text_obj=ax.text(geo['oppo_endzone_mid'], i, "  TD!  ", weight='bold', fontsize=20, color='white', va='center', ha='center')

        text_obj.set_path_effects([
            path_effects.PathPatchEffect(offset=(2, -2), hatch='xxxx', facecolor='gray'),
            path_effects.withStroke(linewidth=1, foreground="black")
        ])

    # Fumble returned for a touchdown, drawn like an interception-return TD
    elif playType == 'Fumble Return Touchdown':
        color = playColor(playType, geo['colors'])
        drawArrow(ax, start, i, -1 * (start - geo['oppo_endzone']), color, fumble=True)
        ax.text(start, i+2, " Fumble! ", fontsize=8, va='top', ha=geo['zha'])
        text_obj=ax.text(geo['oppo_endzone_mid'], i, "  TD!  ", weight='bold', fontsize=20, color='white', va='center', ha='center')

        text_obj.set_path_effects([
            path_effects.PathPatchEffect(offset=(2, -2), hatch='xxxx', facecolor='gray'),
            path_effects.withStroke(linewidth=1, foreground="black")
        ])

    # Every scrimmage play: an arrow in the play's color, plus any label
    else:
        if playType == 'Fumble Recovery (Own)':
            # Own fumble recovered: color by run or pass from the text (a sack defaults to run)
            color = geo['colors']['pass' if 'pass' in str(row.text).lower() else 'run']
        else:
            color = playColor(playType, geo['colors'])
        is_int = 'Interception' in playType
        is_pen = playType == 'Penalty'
        is_fum = playType in FUMBLE_TURNOVER_TYPES
        # Gains and losses get an arrow; no gain gets a short vertical tick
        if row.gained > 0:
            drawArrow(ax, start, i, geo['pos_gained'], color, interception=is_int, penalty=is_pen, fumble=is_fum)
        elif row.gained < 0:
            drawArrow(ax, start, i, geo['neg_gained'], color, interception=is_int, penalty=is_pen, fumble=is_fum)
        else:
            ax.plot([start, start], [i - 1.75, i + 1.75], color=color, linewidth=1)

        if is_fum:
            # Turnover, hatched like an interception and labeled below the arrow
            ax.text(start, i+2, FUMBLE_TURNOVER_LABELS[playType], fontsize=8, va='top', ha=geo['zha'])
        elif 'Touchdown' in playType:
            text_obj=ax.text(geo['endzone_mid'], i, "  TD!  ", weight='bold', fontsize=20, color='white', va='center', ha='center')

            text_obj.set_path_effects([
                path_effects.PathPatchEffect(offset=(2, -2), hatch='xxxx', facecolor='gray'),
                path_effects.withStroke(linewidth=1, foreground="black")
            ])
        elif 'Sack' in playType:
            ax.text(start+geo['neg_gained'], i, '  Sack!  ', color='black', fontsize='8', ha=geo['zha'], va='top')

        elif 'Interception' in playType:
            # Labeled below the arrow, matching the interception-return TD
            ax.text(start, i+2, " Interception! ", fontsize=8, va='top', ha=geo['zha'])

        elif 'Safety' in playType:
            ax.text(geo['int_endzone'], i, " Safety! ", color="white", fontsize=10, va='center', ha=geo['zha'])

        elif 'Fumble Recovery' in playType:
            # Small label below the arrow's head, like "Sack!"
            ax.text(start+geo['neg_gained'], i, '  Fumble!  ', color='black', fontsize='8', ha=geo['zha'], va='top')

    return 0


####
# HTML PAGE
####

# A strict CSP blocks inline CSS/JS, so those ship as files and the SVG's styles become attributes
CSS_FILENAME = 'fbPlaychart.css'
JS_FILENAME = 'fbPlaychart.js'
MANIFEST_FILENAME = 'manifest.js'   # the year/game lists, as a script rather than JSON
STYLE_ELEMENT_RE = re.compile(r'<style[^>]*>(.*?)</style>', re.DOTALL)
STYLE_ATTR_RE = re.compile(r'\sstyle="([^"]*)"')
SVG_OPEN_TAG_RE = re.compile(r'<svg\b[^>]*>')
HOVER_GROUP_RE = re.compile(r'<g id="(pbp\d+)">')
# <image> elements matplotlib tagged with a logo gid, and the embedded data they carry
LOGO_IMAGE_RE = re.compile(r'<image\b[^>]*\bid="(logo\d+)"[^>]*>')
LOGO_DATA_HREF_RE = re.compile(r'\s*xlink:href="data:image/png;base64,[^"]*"')
# Matplotlib stores images upside down with a flip transform, which relinking has to undo
FLIP_TRANSFORM_RE = re.compile(r'\s*transform="scale\(1 -1\) translate\(0 -[\d.]+\)"')
Y_ATTR_RE = re.compile(r'\sy="(-?[\d.]+(?:e[-+]?\d+)?)"')


# Page skeleton, stylesheet and script live in lib/html/fbPlaychart/
TEMPLATE_DIR = 'lib/html/fbPlaychart'
PAGE_TEMPLATE = os.path.join(TEMPLATE_DIR, 'page.html')
PAGE_CSS = os.path.join(TEMPLATE_DIR, CSS_FILENAME)
PAGE_JS = os.path.join(TEMPLATE_DIR, JS_FILENAME)
# Hand-made site files (403/404 pages, robots.txt), copied to the site root when missing
STATIC_DIR = os.path.join(TEMPLATE_DIR, 'static')


def styleToAttributes(declarations):
    # 'fill: none; stroke-width: 0.8' -> ' fill="none" stroke-width="0.8"'
    out = []
    for declaration in declarations.split(';'):
        prop, sep, value = declaration.partition(':')
        prop, value = prop.strip(), value.strip()
        if sep and prop and value:
            out.append(' {}="{}"'.format(prop, html_escape(value, quote=True)))
    return ''.join(out)


def cspSafeSvg(svg):
    # Rewrites matplotlib's inline styles as SVG attributes, which a strict CSP doesn't block
    defaults = []

    def hoistStyleElement(match):
        # Moves the '*' rule's chart-wide defaults onto the root <svg> so they inherit
        rule = re.search(r'\*\s*{([^}]*)}', match.group(1))
        if rule:
            defaults.append(styleToAttributes(rule.group(1)))
        return ''

    svg = STYLE_ELEMENT_RE.sub(hoistStyleElement, svg)
    svg = STYLE_ATTR_RE.sub(lambda m: styleToAttributes(m.group(1)), svg)
    if defaults:
        svg = SVG_OPEN_TAG_RE.sub(lambda m: m.group(0)[:-1] + ''.join(defaults) + '>', svg, count=1)
    return svg


def externalLogos(svg):
    # Points each drawn logo at its published file instead of the embedded base64 copy, cutting page weight
    def relink(match):
        # Relinks one <image> tag, undoing matplotlib's vertical flip
        tag, gid = match.group(0), match.group(1)
        href = LOGO_HREFS.get(gid)
        if not href or not FLIP_TRANSFORM_RE.search(tag):
            # Placed without the usual flip, so keep the embedded copy rather than risk a mirrored logo
            return tag
        # Dropping the flip mirrors the box's y, so mirror y back
        tag = FLIP_TRANSFORM_RE.sub('', tag)
        tag = Y_ATTR_RE.sub(lambda m: ' y="{:.6g}"'.format(-float(m.group(1))), tag, count=1)
        return LOGO_DATA_HREF_RE.sub(' xlink:href="{}"'.format(html_escape(href, quote=True)), tag)
    return LOGO_IMAGE_RE.sub(relink, svg)


def injectHoverText(svg, hover_texts):
    # Puts each play's text on its hover target, so the page needs no inline data script
    def addText(match):
        # Adds data-text to one play's <g> tag
        gid = match.group(1)
        text = hover_texts.get(gid)
        if not text:
            return match.group(0)
        return '<g id="{}" data-text="{}">'.format(gid, html_escape(text, quote=True))
    return HOVER_GROUP_RE.sub(addText, svg)


def gameSlug(week, opponent):
    # Shared 'wk<week>_<opponent>' slug for a game's output files
    opp = re.sub(r'[^0-9A-Za-z]+', '_', opponent).strip('_')
    return f"wk{week}_{opp}"


def gameFilename(info, week, opponent):
    # Page filename for a game, e.g. Southern Miss on Sept 20 -> '09_20_Southern_Miss.html'
    opp = re.sub(r'[^0-9A-Za-z]+', '_', opponent).strip('_')
    when = gameDateTime(info)
    # No CFBD record for the game: fall back to the week the chart was built for
    return f"{when:%m_%d}_{opp}.html" if when else f"wk{week}_{opp}.html"


# Page filenames: MM_DD_<opponent>.html, or wk<week>_<opponent>.html without a date
GAME_FILE_RE = re.compile(r'(?:(\d{2})_(\d{2})|wk(\d+))_(.+)\.html$')


def gameEntry(filename):
    # One game-selector entry: '09_20_Southern_Miss.html' -> '09/20 | Southern Miss'
    m = GAME_FILE_RE.match(filename)
    if not m:
        return None
    month, day, week, opponent = m.groups()
    opponent = opponent.replace('_', ' ')
    if week:  # dateless fallback page: sort it past the dated ones, by week
        return {'label': f"Wk {int(week)} | {opponent}", 'href': filename,
                'sort': (99, int(week))}
    # A season runs August into January, so a January bowl follows December
    order = int(month) if int(month) >= 3 else int(month) + 12
    return {'label': f"{month}/{day} | {opponent}", 'href': filename,
            'sort': (order, int(day))}


def htmlDir(year):
    # Pages are grouped by season, e.g. 2025 -> 'html/fbPlaychart/2025'
    return os.path.join(HTML_DIR, str(year))


def findPbpCsv(year, week):
    # Path to the cached play-by-play CSV for a week of a season
    prefix = f"fbPlaychartPBP_wk{week}_"
    csv_dir = pbpDir(year)
    if os.path.isdir(csv_dir):
        for fn in sorted(os.listdir(csv_dir)):
            if fn.startswith(prefix) and fn.endswith('.csv'):
                return os.path.join(csv_dir, fn)
    return None


def loadGames(html_dir, current=None):
    # Builds the game-selector list by scanning html_dir for game pages
    games = {}
    listing = os.listdir(html_dir) if os.path.isdir(html_dir) else []
    for fn in listing:
        entry = gameEntry(fn)
        if entry:
            games[fn] = entry
    if current:  # the page being written isn't on disk yet
        games[current] = gameEntry(current)
    return [{'label': g['label'], 'href': g['href']}
            for g in sorted(games.values(), key=lambda g: g['sort'])]


def writeManifest(base_dir, year, current_href=None):
    # Writes every season's game list to one script all pages share, so switching years needs no request
    years = loadYears(base_dir, current=year)
    games = {str(y): loadGames(os.path.join(base_dir, str(y)),
                               current=current_href if y == year else None)
             for y in years}
    return writeJsGlobal(os.path.join(base_dir, MANIFEST_FILENAME), 'GTPDD_PLAYCHARTS',
                         {'years': years, 'games': games})


####
# MAIN
####

def fbPlaychart(team='Louisiana Tech', techColorPath='lib/fbPlaychartColorsTech.txt',
                 teamColorsCsv=TEAM_COLORS_CSV, refreshData=False, year=2025, week=4):
    # Load the week's plays, from CFBD or the cached CSV
    if refreshData:
        df = getPBPData(year, week, team)
    else:
        csv_path = findPbpCsv(year, week)
        if csv_path is None:
            raise FileNotFoundError(
                f"No cached play-by-play CSV for week {week} in {pbpDir(year)}/. "
                "Run with refreshData=True first.")
        df = pd.read_csv(csv_path)

    fixPenaltyYards(df, team)

    opponent = next((o for o in df['offense'].dropna().unique() if o != team), 'Opponent')

    techColors = loadColors(techColorPath)
    # Saved colors for this opponent, pulled from ESPN the first time we chart them
    oppoColors = {**NON_TEAM_COLORS, **teamColors(opponent, teamColorsCsv)}

    # Logos for the drive headers, plus bigger copies for the final scoreboard
    techLogo, oppoLogo = teamLogo(team, LOGO_DRAW_PX), teamLogo(opponent, LOGO_DRAW_PX)
    techLogoBig = teamLogo(team, FINAL_LOGO_PX) if techLogo is not None else None
    oppoLogoBig = teamLogo(opponent, FINAL_LOGO_PX) if oppoLogo is not None else None

    # Both logos are published under the site root and every drawn copy links to them
    LOGO_HREFS.clear()
    logoFiles = {'tech': publishLogo(team), 'oppo': publishLogo(opponent),
                 'tech_gray': publishLogo(team, gray=True),
                 'oppo_gray': publishLogo(opponent, gray=True)}

    fig, ax = setupChart(techColors['pass'], oppoColors['run'])

    # Venue, kickoff and attendance, between the top yard numbers and the first drive
    info = gameInfo(year, week, team, opponent, refresh=refreshData)
    info_rows = gameInfoRows(info) if info else []

    # Info header in the middle with each team's arrow key beside it, all sharing a center line
    info_height = gameInfoHeight(info_rows)
    middle = GAME_INFO_TOP + max(info_height, KEY_HEIGHT) / 2
    key_top = middle - KEY_HEIGHT / 2 - KEY_LOGO_H / 2  # drawColorKey starts at the logo band

    header_bottom = drawGameInfo(ax, info_rows, middle - info_height / 2) if info_rows else GAME_INFO_TOP
    # The first drive clears whichever of the three columns runs longest
    header_bottom = max(header_bottom,
                        drawColorKey(ax, techColors, key_top, techLogo, team, 1,
                                     href=logoFiles['tech']),
                        drawColorKey(ax, oppoColors, key_top, oppoLogo, opponent, -1,
                                     href=logoFiles['oppo']))
    i = header_bottom + GAME_INFO_BOTTOM_GAP
    offense = ''
    prev_row = None
    last_overtime = 4  # highest period we've already drawn an overtime divider for
    hover_texts = {}  # gid -> play text, for the HTML tooltips
    # Draw every play top to bottom, i being the current row's y
    for row in df.itertuples():
        if row.type in ('End of Half', 'End Period'):
            # Full-width divider between quarters, and a heavier one at halftime
            divider = periodBreak(row)
            if divider is not None:
                i += DIVIDER_GAP - PLAY_GAP
                drawDivider(ax, i, divider[0], divider[1])
                i += DIVIDER_GAP
                prev_row = row
            continue

        if row.type in ('Timeout', 'End of Game'):
            continue

        # Each overtime period gets its own divider, then starts a fresh drive
        period = quarterOf(row.clock)
        if period is not None and period > 4 and period > last_overtime:
            last_overtime = period
            i += DIVIDER_GAP - PLAY_GAP
            drawDivider(ax, i, overtimeLabel(period))
            i += DIVIDER_GAP
            offense = ''  # force a drive header for the first possession of the period

        if row.offense != offense or row.type in KICKOFF_DRIVE_TYPES:
            offense = row.offense
            i += DRIVE_GAP
            # Drive header: who has the ball, the clock, and the score going into the drive
            if prev_row is not None:
                if prev_row.offense == team:
                    tech_score, oppo_score = prev_row.offense_score, prev_row.defense_score
                else:
                    tech_score, oppo_score = prev_row.defense_score, prev_row.offense_score
            else:
                tech_score = oppo_score = 0
            headerColors = techColors if offense == team else oppoColors
            if tech_score > oppo_score: scoreString = f"Tech up {tech_score}-{oppo_score}"
            elif tech_score < oppo_score: scoreString = f"Tech down {oppo_score}-{tech_score}"
            else: scoreString = f"Tied at {tech_score}-{oppo_score}"

            drawScoreboard(ax, i - DRIVE_HEADER_Y, formatClock(row.clock), f"{offense} Ball",
                           int(tech_score), int(oppo_score), techLogo, oppoLogo,
                           headerColors['pass'], scoreString, offense == team,
                           logoFiles=logoFiles)

        geo = playGeometry(row, team, techColors, oppoColors)
        play_y = i
        n_patches, n_lines = len(ax.patches), len(ax.lines)
        i += drawPlay(ax, row, i, geo)

        # Invisible hover target covering the play's drawing, plus 5 yards each side
        xs = []
        for p in ax.patches[n_patches:]:
            xs.extend(p.get_path().vertices[:, 0])
        for ln in ax.lines[n_lines:]:
            xs.extend(ln.get_xdata())
        x_lo, x_hi = (min(xs), max(xs)) if xs else (row.start, row.start)
        gid = f"pbp{len(hover_texts)}"
        rect = ax.add_patch(Rectangle((x_lo - 5, play_y - 2), (x_hi - x_lo) + 10, 4,
                                      facecolor='none', edgecolor='none', zorder=20))
        rect.set_gid(gid)
        hover_texts[gid] = '' if pd.isna(row.text) else str(row.text)

        i += PLAY_GAP
        prev_row = row

    # Final score below the last play: both logos flanking the score, loser in gray
    final = finalScore(df, team)
    if final is not None:
        tech_final, oppo_final = final
        if tech_final == oppo_final:
            winnerColors = techColors
            finalString = f"Final: {team} {tech_final}, {opponent} {oppo_final}"
        else:
            winner = team if tech_final > oppo_final else opponent
            winnerColors = techColors if winner == team else oppoColors
            finalString = f"{winner} won {max(final)}-{min(final)}"
        i += 14
        drawFinalScoreboard(ax, i, tech_final, oppo_final, techLogoBig, oppoLogoBig,
                            tech_final >= oppo_final, oppo_final >= tech_final,
                            winnerColors['pass'], finalString, logoFiles=logoFiles)
        i += FINAL_SUBLINE + 6

    # Size the figure so vertical spacing matches the horizontal scale
    y_extent = i + 10
    ax.set_ylim(y_extent, -10)  # inverted: first play at top

    # Yard numbers along the bottom, rightside up (near-sideline view)
    drawYardNumbers(ax, y_extent - 4, upside_down=False)

    # Axis numbers are hidden for the clean look; uncomment the two lines below to debug
    ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
    #ax.yaxis.set_major_locator(mticker.MultipleLocator(4))  # tick every play row
    #ax.tick_params(axis='y', labelsize=4)

    width = X_RANGE / UNITS_PER_INCH
    height = max(8.0, y_extent / UNITS_PER_INCH)
    fig.set_size_inches(width, height)

    # Per-game output filenames: <MM_DD_opponent>.html, and fbPlaychart_<MM_DD_opponent>.png
    html_filename = gameFilename(info, week, opponent)
    slug = 'fbPlaychart_' + html_filename[:-len('.html')]
    html_dir = htmlDir(year)
    os.makedirs('out', exist_ok=True)
    os.makedirs(html_dir, exist_ok=True)

    # Save the PNG, and crop its top into the link-preview image
    fig_path = os.path.join('out', slug + '.png')
    fig.savefig(fig_path, bbox_inches='tight', pad_inches=0, dpi=200,
                transparent=False, facecolor=BACKGROUND_COLOR)
    preview = writePreviewCard(fig_path, html_dir, html_filename)

    # Also export an HTML version by embedding matplotlib's own SVG of the figure
    import io
    html_path = os.path.join(html_dir, html_filename)
    buf = io.StringIO()
    fig.savefig(buf, format='svg', bbox_inches='tight', pad_inches=0, facecolor='none')
    svg = buf.getvalue()
    svg = svg[svg.find('<svg'):]  # drop the <?xml?>/<!DOCTYPE> prolog for inline HTML

    # Every season's game list as a script the pages load (a strict CSP blocks fetching it)
    current_href = html_filename
    writeManifest(HTML_DIR, year, current_href)
    current_label = gameEntry(html_filename)['label']
    # Link-preview title and description; the date stays out of the short title
    kickoff = gameDateTime(info)
    matchup = f"{team} vs {opponent}"
    date_text = f"{kickoff:%B} {kickoff.day}, {year}" if kickoff else f"Wk {week}, {year}"
    card_title = f"Playchart | {matchup}"
    card_description = f"Every play of {matchup}, {date_text}."
    page_url = f"{SITE_URL}/{year}/{html_filename}"
    card_image = f"{SITE_URL}/{year}/{PREVIEW_DIR}/{preview}" if preview else None
    # gtpdd logo for the nav's "Back to home" button, published under the site root
    gtpdd_href = publishAsset(GTPDD_LOGO, WEB_IMG_DIR, PAGE_TO_ROOT)
    logo_img = ("<img class='navlogo' src='" + html_escape(gtpdd_href, quote=True) + "' alt='gtpdd'>"
                if gtpdd_href else "")
    # Shared stylesheet and script sit next to the season folders, since a strict CSP won't run them inline
    shutil.copyfile(PAGE_CSS, os.path.join(HTML_DIR, CSS_FILENAME))
    shutil.copyfile(PAGE_JS, os.path.join(HTML_DIR, JS_FILENAME))
    # Restore any hand-made site files missing from the site root, leaving existing ones alone
    copyMissingFiles(STATIC_DIR, HTML_DIR)

    # Fill the page template, escaping plain text
    esc = lambda text: html_escape(str(text), quote=True)
    with open(PAGE_TEMPLATE) as f:
        template = Template(f.read())
    # substitute, not safe_substitute: an unfilled placeholder fails the run instead of shipping
    page = template.substitute(
        title=esc(card_title),
        metaTags=previewMetaTags(card_title, card_description, page_url, card_image,
                                 twitter_handle=TWITTER_HANDLE).rstrip('\n'),
        cssHref=esc(PAGE_TO_ROOT + CSS_FILENAME),
        current=esc(current_href),
        year=year,
        homeUrl=esc(HOME_URL),
        logoImg=logo_img,
        siteTitle=esc(SITE_TITLE),
        currentLabel=esc(current_label),
        svg=cspSafeSvg(externalLogos(injectHoverText(svg, hover_texts))),
        manifestSrc=esc(PAGE_TO_ROOT + MANIFEST_FILENAME),
        jsSrc=esc(PAGE_TO_ROOT + JS_FILENAME),
    )
    with open(html_path, 'w') as f:
        f.write(page)
    print(f"Wrote {html_path}")

    print("Done.")


####
# COMMAND LINE
####

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate the Louisiana Tech play chart (PNG + interactive HTML) for a game.")
    parser.add_argument("--year", type=int, default=2026, help="Season year (default: 2025)")
    parser.add_argument("--week", type=int, default=1, help="Week number (default: 1)")
    parser.add_argument("--refresh-data", action="store_true",
                        help="Re-fetch play-by-play from CFBD (otherwise read the cached CSV)")
    args = parser.parse_args()

    fbPlaychart(year=args.year, week=args.week, refreshData=args.refresh_data)
