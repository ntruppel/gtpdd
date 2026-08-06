# -*- coding: utf-8 -*-
"""
Created on Wed Nov  2 18:06:08 2022

@author: ntrup
"""
import csv
import json
import os
import re
from html import escape as html_escape

import cfbd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.patheffects as path_effects
from matplotlib.patches import Rectangle
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

BACKGROUND_COLOR = "#d6e8cf"  # muted light green
EDGE_COLOR = "#222021"

HOME_URL = "index.html"           # TODO: replace with gtpdd home page
HTML_DIR = "html/fbPlaychart"     # per-game HTML pages
PBP_DIR = "csv/fbPlaychartPBP"    # per-game play-by-play CSVs

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
    'Fumble Recovery (Opponent)': 'fumble',
    'Fumble Return Touchdown': 'fumble',

}

## Non-scoring fumble turnover (the other team recovered): drawn hatched like an
## interception and labeled "Fumble!". (A fumble returned for a TD has its own
## branch that also spots the ball in the endzone.)
FUMBLE_TURNOVER_TYPES = ('Fumble Recovery (Opponent)',)


def getPBPData(year=2024, week=1, team='Louisiana Tech'):
    ## CFBD Configuration
    configuration = cfbd.Configuration(access_token=os.environ["cfbdAuth"])
    api_instance = cfbd.PlaysApi(cfbd.ApiClient(configuration))

    ## TODO: Grab the most recent game automatically
    api_response = api_instance.get_plays(year, week=week, team=team)

    dictList = []
    for play in api_response:
        start = play.yardline
        if start is not None and play.home != team:
            start = 100 - start
        ## Treat a bare "Interception" identically to a "Pass Interception Return".
        play_type = 'Pass Interception Return' if play.play_type == 'Interception' else play.play_type
        ## "Pass Completion" is the same thing as "Pass Reception".
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

    ## Remove duplicate plays
    seen, deduped = set(), []
    for d in dictList:
        key = tuple(v for k, v in d.items() if k != 'id')
        if key not in seen:
            seen.add(key)
            deduped.append(d)
    dictList = deduped

    ## Logic to separate games if CFBD's data is mixed up (G1 2025)
    games = {}
    for d in dictList:
        games.setdefault(d['game_id'], []).append(d)
    built = [buildGame(plays, team, week) for plays in games.values()]
    if len(built) > 1:
        print(f"\nWARNING: the Week {week} pull returned {len(built)} games (the data source merged them):")
        for g_df, g_opp in built:
            path = os.path.join(PBP_DIR, f"fbPlaychartPBP_{gameSlug(week, g_opp)}.csv")
            print(f"  - vs {g_opp}: {len(g_df)} plays -> {path}")
        print(f"Each was split into its own CSV (all named wk{week}). Rename the extra game(s)\n"
              "to the correct week, then re-run with refreshData=False for the game you want.\n")
        raise SystemExit(1)
    return built[0][0]


def buildGame(plays, team, week):
    ## Process a single game's plays
    opponent = next((d['offense'] for d in plays if d['offense'] and d['offense'] != team), team)

    processed = []
    for d in plays:
        text = str(d.get('text') or '')

        ## Kickoff touchbacks: the CFBD "Kickoff" row is credited to the kicking team
        ## Flip it to the receiving team.
        if d['type'] == 'Kickoff' and 'touchback' in text.lower():
            d['offense'] = opponent if d['offense'] == team else team
            d['gained'] = -65
            processed.append(d)

            touchback = dict(d)
            touchback['type'] = 'Touchback'
            touchback['start'] = 0 if touchback['offense'] == team else 100
            touchback['gained'] = 25
            processed.append(touchback)

        ## Kickoffs without a touchback
        elif d['type'] == 'Kickoff':
            d['offense'] = opponent if d['offense'] == team else team
            ko_match = re.search(r'kickoff for (\d+)', text, re.IGNORECASE)
            if ko_match:
                d['gained'] = -int(ko_match.group(1))
            processed.append(d)

        ## Returned kickoffs: split the CFBD "Kickoff Return (Offense)" row into the kick and return
        elif d['type'] == 'Kickoff Return (Offense)':
            d['offense'] = opponent if d['offense'] == team else team
            d['type'] = 'Kickoff'
            ko_match = re.search(r'kickoff for (\d+)', text, re.IGNORECASE)
            if ko_match:
                d['gained'] = -int(ko_match.group(1))
            processed.append(d)

            return_match = re.search(r'return(?:ed|s)? for (\d+)', text, re.IGNORECASE)
            if return_match:
                catch = d['start'] + d['gained'] if d['offense'] == team else d['start'] - d['gained']
                kick_return = dict(d)
                kick_return['type'] = 'Kickoff Return (Offense)'
                kick_return['start'] = catch
                kick_return['gained'] = int(return_match.group(1))
                processed.append(kick_return)

        ## Punts: CFBD's "gained" is unreliable — take the punt distance from the text ("punt for N yds")
        ## Touchback: add a row for the receiving team at its own 20 (like the kickoff
        ## Return:  add a following "Punt Return" row for the receiving team, starting where the punt was caught.
        elif d['type'] == 'Punt':
            punt_match = re.search(r'punt for (\d+)', text, re.IGNORECASE)
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
                return_match = re.search(r'returns? for (\d+)', text, re.IGNORECASE)
                if return_match:
                    ## Catch point is direction-aware: the punting team's own punts
                    ## travel toward x=100 (start+gained), the opponent's toward x=0.
                    catch = d['start'] + d['gained'] if d['offense'] == team else d['start'] - d['gained']
                    punt_return = dict(d)
                    punt_return['type'] = 'Punt Return'
                    punt_return['offense'] = opponent if d['offense'] == team else team
                    punt_return['start'] = catch
                    punt_return['gained'] = int(return_match.group(1))
                    processed.append(punt_return)

        ## Interception into the endzone -> touchback
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

    ## CFBD can return plays out of game order — sort chronologically from the
    ## clock string "Q<period> M:SS": quarter ascending, then time remaining
    ## descending (the clock counts down within a quarter), then play id ascending
    ## to break same-clock ties.
    clock_parts = df['clock'].str.extract(r'Q(\d+)\s+(\d+):(\d+)').astype(float)
    df['_period'] = clock_parts[0]
    df['_secs_remaining'] = clock_parts[1] * 60 + clock_parts[2]
    df['_id'] = pd.to_numeric(df['id'], errors='coerce')
    df = (df.sort_values(['_period', '_secs_remaining', '_id'], ascending=[True, False, True], kind='stable')
            .drop(columns=['_period', '_secs_remaining', '_id'])
            .reset_index(drop=True))

    ## Interception returns and un-returned punts: CFBD yards gained doesn't work here. Draw the arrow to wherever the next play begins.
    stop_types = {'End Period', 'End of Half', 'Timeout', 'End of Game'}
    starts, types, offs, gains = (list(df[c]) for c in ('start', 'type', 'offense', 'gained'))
    for i in range(len(df)):
        if pd.isna(starts[i]):
            continue
        j = i + 1
        while j < len(df) and types[j] in stop_types:
            j += 1
        if types[i] == 'Pass Interception Return':
            pass  # always redraw an interception return to the next play
        elif types[i] == 'Punt' and (j >= len(df) or types[j] not in ('Punt Return', 'Touchback')):
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

    ## Per-game CSV: csv/fbPlaychartPBP/fbPlaychartPBP_wk<week>_<opponent>.csv
    df = df.drop(columns=['game_id'], errors='ignore')
    os.makedirs(PBP_DIR, exist_ok=True)
    df.to_csv(os.path.join(PBP_DIR, f"fbPlaychartPBP_{gameSlug(week, opponent)}.csv"))
    return df, opponent


## Inches of figure per data-unit, kept roughly equal on both axes so the
## fixed-width play arrows keep their proportions instead of squishing.
UNITS_PER_INCH = 13.0
X_RANGE = 126  # xlim spans -13 .. 113


def drawYardNumbers(ax, y, upside_down):
    rotation = 180 if upside_down else 0
    for yard in range(10, 100, 10):
        digits = list(str(min(yard, 100 - yard)))  # e.g. ['4', '0']
        if upside_down:
            digits = digits[::-1]
        left, right = digits
        for digit, dx in ((left, -1.1), (right, 1.1)):
            ax.text(yard + dx, y, digit, color='white', fontsize=11, fontweight='bold',
                    va='center', ha='center', rotation=rotation, zorder=2)

        ## Small triangle pointing toward the nearest goal line
        if yard != 50:
            marker, mx = ('<', yard - 3.2) if yard < 50 else ('>', yard + 3.2)
            ax.plot([mx], [y], marker=marker, markersize=3, color='white',
                    linestyle='None', zorder=2)


def setupChart(techColor, oppoColor):
    fig, ax = plt.subplots()
    fig.patch.set_facecolor(BACKGROUND_COLOR)
    ax.set_facecolor(BACKGROUND_COLOR)
    ax.set_xlim(-13, 113)

    ## Endzones: Tech's color on the left (-13..0), opponent's on the right (100..113).
    ax.axvspan(-13, 0, color=techColor, zorder=-1)
    ax.axvspan(100, 113, color=oppoColor, zorder=-1)

    ## White yard lines every 10 from 0 to 100; 0/50/100 drawn thicker.
    for yard in range(0, 101, 10):
        lw = 3 if yard in (0, 50, 100) else 1
        ax.axvline(yard, color='white', linewidth=lw, zorder=0)

    ## Yard numbers along the top, upside down (far-sideline view from above).
    drawYardNumbers(ax, -6, upside_down=True)

    return fig, ax


def loadColors(path):
    with open(path) as f:
        return json.load(f)


def lookupEspnId(name, team_id_csv='csv/espnTeamIDs.csv'):
    if not os.path.isfile(team_id_csv):
        return None
    with open(team_id_csv, newline='') as f:
        for row in csv.reader(f):
            if len(row) >= 2 and row[0].strip().lower() == str(name).strip().lower():
                return row[1].strip()
    return None


def hexLuminance(hex_color):
    """Perceived brightness (0-255) of a #RRGGBB color; lower is darker."""
    h = str(hex_color).lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 0.299 * r + 0.587 * g + 0.114 * b


def whiteToBlack(hex_color):
    ## Replace a white team color with black for a better chart
    h = str(hex_color).lstrip('#').lower()
    if h in ('fff', 'ffffff'):
        return '#000000'
    return hex_color


def updateOppoColors(opponent, oppo_color_path):
    ## When refreshColors=True, updates the team's colors in lib/fbPlaychartColorsOppo.txt
    team_id = lookupEspnId(opponent)
    if team_id is None:
        print(f"No ESPN id for '{opponent}' in csv/espnTeamIDs.csv; keeping existing opponent colors.")
        return
    try:
        from lib.fbCommon import getTeamInfo
        _, color1, color2 = getTeamInfo(str(team_id))
    except Exception as e:
        print(f"Could not fetch ESPN colors for '{opponent}' ({type(e).__name__}: {e}); keeping existing.")
        return
    colors = loadColors(oppo_color_path)
    ## Use the darker of the two team colors for "pass" and the lighter for "run".
    c1, c2 = '#' + str(color1).lstrip('#'), '#' + str(color2).lstrip('#')
    c1, c2 = whiteToBlack(c1), whiteToBlack(c2)
    try:
        colors['pass'], colors['run'] = sorted((c1, c2), key=hexLuminance)
    except (ValueError, IndexError):
        colors['pass'], colors['run'] = c1, c2  # non-hex color: keep color1/color2 order
    with open(oppo_color_path, 'w') as f:
        json.dump(colors, f, indent=4)
    print(f"Opponent colors from ESPN ({opponent}): pass={colors['pass']}, run={colors['run']}")


def logoDataUri(path, height_px=64):
    try:
        import base64
        import io
        from PIL import Image as PILImage
        img = PILImage.open(path)
        w, h = img.size
        if h > height_px:
            img = img.resize((max(1, round(w * height_px / h)), height_px), PILImage.LANCZOS)
        b = io.BytesIO()
        img.save(b, format='PNG')
        return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode('ascii')
    except Exception:
        return None


def formatClock(clock):
    try:
        head, secs = str(clock).rsplit(':', 1)
        return f"{head}:{int(secs):02d}"
    except (ValueError, AttributeError):
        return str(clock)


def playColor(playType, colors):
    key = PLAY_COLOR_KEYS.get(playType)
    if key:
        return colors[key]
    print(playType)
    return 'green'  # Catchall for unlisted. If we see green, there's a problem


def shortenArrow(disp):
    sign = 1 if disp >= 0 else -1
    return sign * max(abs(disp) - 1.9, 0.6)


def playGeometry(row, team, techColors, oppoColors):
    ## Geometry/colors for drawing a play, mirrored depending on which team has the ball.
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


## Don't draw first down lines for Special-teams / non-scrimmage rows
NO_FIRST_DOWN_TYPES = {
    'Kickoff', 'Kickoff Return (Offense)', 'Touchback',
    'Punt', 'Punt Return', 'Field Goal Good', 'Field Goal Missed', 'Blocked Field Goal',
}


def ordinalDown(down):
    """1 -> '1', 2 -> '2nd', 3 -> '3rd', 4 -> '4th'."""
    return {1: '1', 2: '2', 3: '3', 4: '4'}.get(int(down), '')


## Interceptions get a contrasting hatch overlay so they stand out by texture,
## independent of the team's fill color (which varies game to game).
INTERCEPTION_HATCH = '//'
INTERCEPTION_HATCH_COLOR = 'white'
## Penalties are drawn as patterned gold so they don't blend into a team whose
## color happens to be gold (e.g. LSU): a black cross-hatch over the gold fill.
PENALTY_HATCH = 'xxx'
PENALTY_HATCH_COLOR = 'black'


def drawArrow(ax, x, y, dx, color, interception=False, penalty=False, fumble=False):
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
    start = row.start
    playType = row.type

    ## Faint orange first-down line: "distance" yards downfield from the start
    if playType not in NO_FIRST_DOWN_TYPES and pd.notna(row.distance):
        first_down = start + geo['direction'] * row.distance
        ax.plot([first_down, first_down], [i - 1.8, i + 1.8],
                color='orange', alpha=0.2, linewidth=2, zorder=1)

    ## Small down label inside the arrow, on its bottom edge
    if playType not in NO_FIRST_DOWN_TYPES and pd.notna(row.down):
        down_ha = geo['zha'] if row.gained < 0 else geo['ha']
        down_color = 'black' if (row.gained == 0 or playType in ('Penalty')) else 'white'
        ax.text(start, i + 1.6, ordinalDown(row.down), fontsize=6, color=down_color,
                va='bottom', ha=down_ha, zorder=6)

    ## KICKOFF (drawn as a dashed line, like a punt)
    if playType == 'Kickoff':
        ko_marker = '<' if geo['marker'] == '>' else '>'
        ax.text(start, i+0.5, " Kickoff ", fontsize=8, va='top', ha=geo['zha'])
        ax.plot([start, start + geo['pos_gained']], [i, i], '--', marker=ko_marker, markersize=1, linewidth=2, color='black')

    elif playType == 'Kickoff Return (Offense)':
        ax.text(start, i+0.5, " Return ", fontsize=8, va='top', ha=geo['ha'])
        ax.plot([start, start + geo['pos_gained']], [i, i], '--', marker=geo['marker'], markersize=1, linewidth=2, color='black')

    elif playType == 'Touchback':
            ax.text(start, i+0.5, " Touchback ", fontsize=8, va='top', ha=geo['ha'])
            ax.plot([start, start + geo['pos_gained']], [i, i], '--', marker=geo['marker'], markersize=1, linewidth=2, color='black')
               

    ## FIELD GOAL
    elif playType == 'Field Goal Good':
        ax.plot([start, geo['fg_yards']], [i, i], '--', marker='P', markersize=8, linewidth=4, color='green')
        text_obj = ax.text(geo['endzone_mid'], i, " FG! ", weight='bold', fontsize=20, color='white', va='center', ha='center')

        text_obj.set_path_effects([
                        path_effects.PathPatchEffect(offset=(2, -2), hatch='xxxx', facecolor='gray'),
                        path_effects.withStroke(linewidth=1, foreground="black")
                    ])
    elif playType in ('Field Goal Missed', 'Blocked Field Goal'):
        ax.plot([start, start + geo['fg_yards']], [i, i], '--', marker='X', markersize=8, linewidth=4, color='gray')
        ax.text(start, i+1, " FG Miss! ", weight='bold', fontsize=10, color='black', va='top', ha=geo['ha'])


    ## PUNT
    elif playType == 'Punt':
        ax.text(start, i+0.5, " Punt ", fontsize=8, va='top', ha=geo['ha'])
        ax.plot([start, start + geo['pos_gained']], [i, i], '--', marker=geo['marker'], markersize=1, linewidth=2, color='black')

    ## PUNT RETURN
    elif playType == 'Punt Return':
        ax.text(start, i+0.5, " Return ", fontsize=8, va='top', ha=geo['ha'])
        ax.plot([start, start + geo['pos_gained']], [i, i], '--', marker=geo['marker'], markersize=1, linewidth=2, color='black')


    ## INTERCEPTION
    elif playType == 'Interception':
        ax.text(start, i, 'INTERCEPTION', color='purple', fontsize='40', ha=geo['ha'])

    elif playType == 'Interception Return Touchdown':
        color = playColor(playType, geo['colors'])
        drawArrow(ax, start, i, -1 * (start - geo['oppo_endzone']), color, interception=True)
        ax.text(start, i+2, " Interception! ", fontsize=8, va='top', ha=geo['zha'])
        text_obj=ax.text(geo['oppo_endzone_mid'], i, "  TD!  ", weight='bold', fontsize=20, color='white', va='center', ha='center')

        text_obj.set_path_effects([
            path_effects.PathPatchEffect(offset=(2, -2), hatch='xxxx', facecolor='gray'),
            path_effects.withStroke(linewidth=1, foreground="black")
        ])

    ## Fumble returned for a TD — same as an interception-return TD (arrow to the
    ## returning team's endzone, "TD!" there), but labeled "Fumble!".
    elif playType == 'Fumble Return Touchdown':
        color = playColor(playType, geo['colors'])
        drawArrow(ax, start, i, -1 * (start - geo['oppo_endzone']), color, fumble=True)
        ax.text(start, i+2, " Fumble! ", fontsize=8, va='top', ha=geo['zha'])
        text_obj=ax.text(geo['oppo_endzone_mid'], i, "  TD!  ", weight='bold', fontsize=20, color='white', va='center', ha='center')

        text_obj.set_path_effects([
            path_effects.PathPatchEffect(offset=(2, -2), hatch='xxxx', facecolor='gray'),
            path_effects.withStroke(linewidth=1, foreground="black")
        ])
    else:
        if playType == 'Fumble Recovery (Own)':
            ## Own-fumble kept possession — color it by whether the text was a run
            ## or pass (a sack that fumbled has neither, so it defaults to run).
            color = geo['colors']['pass' if 'pass' in str(row.text).lower() else 'run']
        else:
            color = playColor(playType, geo['colors'])
        is_int = 'Interception' in playType
        is_pen = playType == 'Penalty'
        is_fum = playType in FUMBLE_TURNOVER_TYPES
        if row.gained > 0:
            drawArrow(ax, start, i, geo['pos_gained'], color, interception=is_int, penalty=is_pen, fumble=is_fum)
        elif row.gained < 0:
            drawArrow(ax, start, i, geo['neg_gained'], color, interception=is_int, penalty=is_pen, fumble=is_fum)
        else:
            ax.plot([start, start], [i - 1.75, i + 1.75], color=color, linewidth=1)

        if is_fum:
            ## Fumble turnover — hatched like an interception, labeled below the arrow.
            ax.text(start, i+2, " Fumble! ", fontsize=8, va='top', ha=geo['zha'])
        elif 'Touchdown' in playType:
            text_obj=ax.text(geo['endzone_mid'], i, "  TD!  ", weight='bold', fontsize=20, color='white', va='center', ha='center')

            text_obj.set_path_effects([
                path_effects.PathPatchEffect(offset=(2, -2), hatch='xxxx', facecolor='gray'),
                path_effects.withStroke(linewidth=1, foreground="black")
            ])
        elif 'Sack' in playType:
            ax.text(start+geo['neg_gained'], i, '  Sack!  ', color='black', fontsize='8', ha=geo['zha'], va='top')

        elif 'Interception' in playType:
            ## Labeled below the arrow, matching the "Interception Return Touchdown" style.
            ax.text(start, i+2, " Interception! ", fontsize=8, va='top', ha=geo['zha'])

        elif 'Safety' in playType:
            ax.text(geo['int_endzone'], i, " Safety! ", color="white", fontsize=10, va='center', ha=geo['zha'])

        elif 'Fumble Recovery' in playType:
            ## Printed the same way as "Sack!" — small, below the arrow's head.
            ax.text(start+geo['neg_gained'], i, '  Fumble!  ', color='black', fontsize='8', ha=geo['zha'], va='top')
            

    return 0


def gameSlug(week, opponent):
    ## Shared 'wk<week>_<opponent>' slug for a game's output files
    opp = re.sub(r'[^0-9A-Za-z]+', '_', opponent).strip('_')
    return f"wk{week}_{opp}"


def gameFilename(week, opponent):
    ## Page filename for a game, e.g. week 4 vs Southern Miss -> 'fbPlaychart_wk4_Southern_Miss.html'
    return f"fbPlaychart_{gameSlug(week, opponent)}.html"


def findPbpCsv(week):
    ## Path to the cached play-by-play CSV for a week
    prefix = f"fbPlaychartPBP_wk{week}_"
    if os.path.isdir(PBP_DIR):
        for fn in sorted(os.listdir(PBP_DIR)):
            if fn.startswith(prefix) and fn.endswith('.csv'):
                return os.path.join(PBP_DIR, fn)
    return None


def loadGames(html_dir, current=None):
    ## Build the game-selector list by scanning html_dir for pages named fbPlaychart_wk<week>_<opponent>.html
    games = {}
    listing = os.listdir(html_dir) if os.path.isdir(html_dir) else []
    for fn in listing:
        m = re.match(r'fbPlaychart_wk(\d+)_(.+)\.html$', fn)
        if m:
            week, opponent = int(m.group(1)), m.group(2).replace('_', ' ')
            games[fn] = {'week': week, 'label': f"Wk {week} — {opponent}", 'href': fn}
    if current:
        games[current['href']] = {'week': current['week'], 'href': current['href'],
                                  'label': f"Wk {current['week']} — {current['opponent']}"}
    return sorted(games.values(), key=lambda g: g['week'])


def fbPlaychart(team='Louisiana Tech', techColorPath='lib/fbPlaychartColorsTech.txt',
                 oppoColorPath='lib/fbPlaychartColorsOppo.txt', refreshData=False,
                 refreshColors=False, year=2025, week=4):
    if refreshData:
        df = getPBPData(year, week, team)
    else:
        csv_path = findPbpCsv(week)
        if csv_path is None:
            raise FileNotFoundError(
                f"No cached play-by-play CSV for week {week} in {PBP_DIR}/. "
                "Run with refreshData=True first.")
        df = pd.read_csv(csv_path)

    opponent = next((o for o in df['offense'].dropna().unique() if o != team), 'Opponent')

    ## Pull the opponent's team colors from ESPN.
    if refreshColors:
        updateOppoColors(opponent, oppoColorPath)

    techColors = loadColors(techColorPath)
    oppoColors = loadColors(oppoColorPath)

    fig, ax = setupChart(techColors['pass'], oppoColors['run'])

    i = 0
    offense = ''
    prev_row = None
    hover_texts = {}  # gid -> play text, for the HTML tooltips
    for row in df.itertuples():
        if row.type == 'End of Half':
            ## Draw a full-width divider between the two halves.
            i += 4
            ax.axhline(i, color='black', linewidth=3, zorder=5)
            ax.text(50, i, " Halftime ", fontsize=12, fontweight='bold',
                    va='center', ha='center', color='black',
                    bbox=dict(facecolor=BACKGROUND_COLOR, edgecolor='black', pad=3), zorder=6)
            i += 4
            prev_row = row
            continue

        if row.type in ('End Period', 'Timeout', 'End of Game'):
            continue

        if row.offense != offense or row.type == 'Kickoff':
            offense = row.offense
            i += 10
            ## Drive header: who has the ball, the clock, and the score
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


            ax.text(50, i - 5, f"{formatClock(row.clock)} | {scoreString} | {offense} Ball",
                    fontsize=12, fontweight='bold', va='center', ha='center',
                    color=headerColors['pass'])

        geo = playGeometry(row, team, techColors, oppoColors)
        play_y = i
        n_patches, n_lines = len(ax.patches), len(ax.lines)
        i += drawPlay(ax, row, i, geo)

        ## Invisible hover target for this play, +/- 5 yards of play
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

        i += 4
        prev_row = row

    ## Size the figure so vertical spacing matches the horizontal scale,
    y_extent = i + 10
    ax.set_ylim(y_extent, -10)  # inverted: first play at top

    ## Yard numbers along the bottom, rightside up (near-sideline view).
    drawYardNumbers(ax, y_extent - 4, upside_down=False)

    ## Axis numbers are hidden for the clean look. Re-enable to debug
    ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
    #ax.yaxis.set_major_locator(mticker.MultipleLocator(4))  # tick every play row
    #ax.tick_params(axis='y', labelsize=4)
    
    width = X_RANGE / UNITS_PER_INCH
    height = max(8.0, y_extent / UNITS_PER_INCH)
    fig.set_size_inches(width, height)

    ## Per-game output filenames: fbPlaychart_wk<week>_<opponent>.(png|html)
    html_filename = gameFilename(week, opponent)
    slug = html_filename[:-len('.html')]
    os.makedirs('out', exist_ok=True)
    os.makedirs(HTML_DIR, exist_ok=True)

    fig_path = os.path.join('out', slug + '.png')
    fig.savefig(fig_path, bbox_inches='tight', pad_inches=0, dpi=200,
                transparent=False, facecolor=BACKGROUND_COLOR)

    ## Also export an HTML version by embedding matplotlib's OWN SVG of the figure.
    import io
    html_path = os.path.join(HTML_DIR, html_filename)
    buf = io.StringIO()
    fig.savefig(buf, format='svg', bbox_inches='tight', pad_inches=0, facecolor='none')
    svg = buf.getvalue()
    svg = svg[svg.find('<svg'):]  # drop the <?xml?>/<!DOCTYPE> prolog for inline HTML

    ## Styles for the nav header and the play-text tooltip.
    style = (
        "body { margin: 0; background: " + EDGE_COLOR + "; }"
        " svg { display: block; margin: 0 auto; height: auto; max-width: 100%; }"
        " svg g[id^='pbp'] path { pointer-events: all; cursor: pointer; }"
        " #gtpdd-nav { position: sticky; top: 0; z-index: 20; display: flex; gap: 10px;"
        " align-items: center; padding: 8px 12px; background: #17181a;"
        " border-bottom: 1px solid #333; font: 14px -apple-system, Segoe UI, sans-serif; }"
        " #gtpdd-nav .spacer { flex: 1; }"
        " #gtpdd-nav label { color: #aaa; }"
        " #gtpdd-nav a.navbtn, #gtpdd-nav button, #gtpdd-nav select {"
        " font: inherit; color: #eee; background: #2a2c2f; border: 1px solid #444;"
        " border-radius: 6px; padding: 6px 12px; cursor: pointer; text-decoration: none; }"
        " #gtpdd-nav a.navbtn { display: inline-flex; align-items: center; gap: 5px; }"
        " #gtpdd-nav a.navbtn:hover, #gtpdd-nav button:hover { background: #3a3d41; }"
        " #gtpdd-nav .navlogo { height: 20px; width: auto; vertical-align: middle; }"
        " #gtpdd-nav .nav-arrow { display: none; font-size: 16px; line-height: 1; }"
        " @media (max-width: 640px) {"
        " #gtpdd-nav { gap: 6px; padding: 6px 8px; }"
        " #gtpdd-nav .nav-text { display: none; }"        # drop "Back to" / "home"
        " #gtpdd-nav .nav-arrow { display: inline; }"     # show the left arrow instead
        " #gtpdd-nav label { display: none; }"            # drop the "Game:" label
        " #gtpdd-nav select { max-width: 120px; }"        # much narrower dropdown
        " #gtpdd-nav a.navbtn, #gtpdd-nav button, #gtpdd-nav select { padding: 6px 8px; } }"
        " #pbp-tooltip { position: fixed; pointer-events: none; z-index: 30;"
        " max-width: 380px; padding: 6px 9px; border-radius: 5px; display: none;"
        " background: rgba(20,20,20,0.92); color: #fff;"
        " font: 13px/1.35 -apple-system, Segoe UI, sans-serif;"
        " box-shadow: 0 2px 8px rgba(0,0,0,0.3); }"
    )

    ## Nav header: home button + a game selector
    current_href = html_filename
    games = loadGames(HTML_DIR, current={'week': week, 'opponent': opponent, 'href': current_href})
    with open(os.path.join(HTML_DIR, 'games.json'), 'w') as f:
        json.dump(games, f, indent=2)
    current_label = f"Wk {week} — {opponent}"
    options = "<option value='{}' selected>{}</option>".format(
        html_escape(current_href, quote=True), html_escape(current_label))
    ## "Back to <gtpdd logo> home" — embed the logo (falls back to a relative path).
    logo_src = logoDataUri('img/gtpdd_logo.png') or '../img/gtpdd_logo.png'
    logo_img = "<img class='navlogo' src='" + html_escape(logo_src, quote=True) + "' alt='gtpdd'>"
    navbar = (
        "<div id='gtpdd-nav'>"
        "<a class='navbtn' href='" + html_escape(HOME_URL, quote=True) + "'>"
        "<span class='nav-arrow'>&#8592;</span>"
        "<span class='nav-text'>Back to</span>" + logo_img +
        "<span class='nav-text'>home</span></a>"
        "<span class='spacer'></span>"
        "<label for='gtpdd-game'>Game:</label>"
        "<select id='gtpdd-game'>" + options + "</select>"
        "<button id='gtpdd-go'>Load</button>"
        "</div>"
    )
    nav_js = (
        "<script>(function(){"
        "var cur=" + json.dumps(current_href) + ";"
        "var sel=document.getElementById('gtpdd-game');"
        "document.getElementById('gtpdd-go').addEventListener('click',function(){"
        "if(sel.value)window.location.href=sel.value;});"
        ## Populate the selector from the shared manifest so it lists every game.
        "fetch('games.json').then(function(r){return r.json();}).then(function(gs){"
        "sel.innerHTML='';"
        "gs.forEach(function(g){var o=document.createElement('option');"
        "o.value=g.href;o.textContent=g.label;if(g.href===cur)o.selected=true;"
        "sel.appendChild(o);});"
        "}).catch(function(){});"
        "})();</script>"
    )

    tooltip_js = (
        "<script>(function(){"
        "var T=" + json.dumps(hover_texts).replace("</", "<\\/") + ";"
        "var tip=document.getElementById('pbp-tooltip');"
        "document.addEventListener('mousemove',function(e){"
        "var g=e.target.closest?e.target.closest(\"g[id^='pbp']\"):null;"
        "if(g&&T[g.id]){tip.textContent=T[g.id];tip.style.display='block';"
        "tip.style.left=Math.min(e.clientX+14,window.innerWidth-260)+'px';"
        "tip.style.top=(e.clientY+14)+'px';}"
        "else{tip.style.display='none';}"
        "});})();</script>"
    )
    page = (
        "<!DOCTYPE html>\n<html lang='en'>\n<head>\n"
        "<meta charset='utf-8'>\n"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>\n"
        "<title>" + html_escape(f"{team} vs {opponent} — Wk {week} Play Chart") + "</title>\n"
        "<style>" + style + "</style>\n"
        "</head>\n<body>\n" + navbar + "\n" + svg + "\n"
        "<div id='pbp-tooltip'></div>\n" + nav_js + tooltip_js + "\n</body>\n</html>\n"
    )
    with open(html_path, 'w') as f:
        f.write(page)
    print(f"Wrote {html_path}")

    print("Done.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate the Louisiana Tech play chart (PNG + interactive HTML) for a game.")
    parser.add_argument("--year", type=int, default=2025, help="Season year (default: 2025)")
    parser.add_argument("--week", type=int, default=1, help="Week number (default: 1)")
    parser.add_argument("--refresh-data", action="store_true",
                        help="Re-fetch play-by-play from CFBD (otherwise read the cached CSV)")
    parser.add_argument("--refresh-colors", action="store_true",
                        help="Pull the opponent's colors from ESPN into the opponent color file")
    args = parser.parse_args()

    fbPlaychart(year=args.year, week=args.week,
                refreshData=args.refresh_data, refreshColors=args.refresh_colors)