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
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Rectangle
from matplotlib.path import Path
from matplotlib.textpath import TextPath
import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

BACKGROUND_COLOR = "#d6e8cf"  # muted light green
EDGE_COLOR = "#222021"

HOME_URL = "index.html"           # TODO: replace with gtpdd home page
SITE_TITLE = "gtpdd's Football Playcharts"  
HTML_DIR = "html/fbPlaychart"     
PBP_DIR = "csv/fbPlaychartPBP"    
TEAM_COLORS_CSV = "csv/fbPlaychartPBP/fbPlaychartTeamColors.csv"
LOGO_DIR = "logo"                 # team logo cache, shared with the other gtpdd scripts
ESPN_LOGO_URL = "https://a.espncdn.com/i/teamlogos/ncaa/500/{}.png"
LOGO_DRAW_PX = 72                 # logos are shrunk to this before drawing; every drive header embeds a copy
## Logos are sized by height so square marks and wide wordmarks read alike, with a
## width cap so a wordmark can't run away with the line.
SCOREBOARD_LOGO_H = 4.2           # yards tall for a logo in the drive header
SCOREBOARD_LOGO_W = 7.0           # yards wide at most
SCOREBOARD_GAP = 1.8              # yards between the pieces of a drive header
POSSESSION_GAP = 2.0              # yards below the logo row for the clock/possession line
## Clock and possession arrow share a line under the logos
SCOREBOARD_SUBLINE = SCOREBOARD_LOGO_H / 2 + POSSESSION_GAP
CLOCK_FONTSIZE = 8               # smaller than the score above it
HEADER_TEXT_COLOR = 'black'       # the logos carry the team colors, so the text stays neutral
POSSESSION_ARROW_H = 2 / 3        # arrow height as a fraction of its length
POSSESSION_ARROW_PT = 8           # arrow length in points
DRIVE_GAP = 14                    # vertical room reserved above a drive for its header
DRIVE_HEADER_Y = 9.0              # header sits this far above the drive's first play
NON_TEAM_COLORS = {'penalty': 'white', 'safety': 'navy', 'fumble': 'navy'}
FALLBACK_TEAM_COLORS = {'pass': '#4d4d4d', 'run': '#a6a6a6'}

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
    'Fumble Return Touchdown': 'run',

}

FUMBLE_TURNOVER_TYPES = ('Fumble Recovery (Opponent)',)

## CFBD writes kick and punt text two different ways
KICKOFF_YARDS_RE = re.compile(r'kickoff\s+(?:for\s+)?(\d+)', re.IGNORECASE)
PUNT_YARDS_RE = re.compile(r'punt\s+(?:for\s+)?(\d+)', re.IGNORECASE)
RETURN_YARDS_RE = re.compile(r'return(?:ed|s)?\s+(?:for\s+)?(\d+)', re.IGNORECASE)

KICKOFF_TYPES = ('Kickoff', 'Kickoff Return (Offense)')
PUNT_TYPES = ('Punt', 'Punt Return')


def pbpDir(year):
    ## Cached play-by-play is grouped by season, e.g. 2025 -> 'csv/fbPlaychartPBP/2025'
    return os.path.join(PBP_DIR, str(year))


def getPBPData(year=2024, week=1, team='Louisiana Tech'):
    ## CFBD Configuration
    configuration = cfbd.Configuration(access_token=os.environ["cfbdAuth"])
    api_instance = cfbd.PlaysApi(cfbd.ApiClient(configuration))

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
    built = [buildGame(plays, team, week, year) for plays in games.values()]
    if len(built) > 1:
        print(f"\nWARNING: the Week {week} pull returned {len(built)} games (the data source merged them):")
        for g_df, g_opp in built:
            path = os.path.join(pbpDir(year), f"fbPlaychartPBP_{gameSlug(week, g_opp)}.csv")
            print(f"  - vs {g_opp}: {len(g_df)} plays -> {path}")
        print(f"Each was split into its own CSV (all named wk{week}). Rename the extra game(s)\n"
              "to the correct week, then re-run with refreshData=False for the game you want.\n")
        raise SystemExit(1)
    return built[0][0]


def buildGame(plays, team, week, year):
    ## Process a single game's plays
    opponent = next((d['offense'] for d in plays if d['offense'] and d['offense'] != team), team)

    processed = []
    for d in plays:
        text = str(d.get('text') or '')

        ## Kickoff touchbacks: the CFBD kickoff row is credited to the kicking team
        ## Flip it to the receiving team.
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

        ## Every other kickoff
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

        ## Punts: CFBD's "gained" is unreliable, take the punt distance from the text
        ## Touchback: add a row for the receiving team at its own 20 (like the kickoff)
        ## Return:  add a following "Punt Return" row for the receiving team, starting where the punt was caught.
        elif d['type'] in PUNT_TYPES:
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

    ## CFBD can return plays out of game order
    ## Sort by clock, then by play id
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

    ## Per-game CSV: csv/fbPlaychartPBP/<year>/fbPlaychartPBP_wk<week>_<opponent>.csv
    df = df.drop(columns=['game_id'], errors='ignore')
    csv_dir = pbpDir(year)
    os.makedirs(csv_dir, exist_ok=True)
    df.to_csv(os.path.join(csv_dir, f"fbPlaychartPBP_{gameSlug(week, opponent)}.csv"))
    return df, opponent


## Inches of figure per data-unit, kept roughly equal on both axes so the
## fixed-width play arrows keep their proportions instead of squishing.
UNITS_PER_INCH = 13.0
X_RANGE = 126  # xlim spans -13 .. 113


def teamLogo(team, draw_px=LOGO_DRAW_PX):
    ## A team's ESPN logo, downloaded once into logo/ and shrunk to chart size.
    from PIL import Image as PILImage
    path = os.path.join(LOGO_DIR, f"{team}.png")
    if not os.path.isfile(path):
        team_id = lookupEspnId(team)
        if team_id is None:
            print(f"No ESPN id for '{team}' in csv/espnTeamIDs.csv; drive headers will use text scores.")
            return None
        try:
            import requests
            response = requests.get(ESPN_LOGO_URL.format(team_id), timeout=15)
            response.raise_for_status()
            os.makedirs(LOGO_DIR, exist_ok=True)
            with open(path, 'wb') as f:
                f.write(response.content)
            print(f"Saved {team} logo to {path}")
        except Exception as e:
            print(f"Could not fetch the logo for '{team}' ({type(e).__name__}: {e}).")
            return None
    try:
        img = PILImage.open(path).convert('RGBA')
        ## Trim to the artwork so every team's mark comes out the same visual size.
        bbox = img.split()[3].getbbox()
        if bbox:
            img = img.crop(bbox)
        img.thumbnail((draw_px, draw_px), PILImage.LANCZOS)
        return np.asarray(img)
    except Exception as e:
        print(f"Could not read {path} ({type(e).__name__}: {e}).")
        return None


def textWidthYards(text, fontsize, weight='bold'):
    ## Width of a rendered string in field yards, so header pieces can be laid out by hand
    if not text:
        return 0.0
    path = TextPath((0, 0), text, size=fontsize, prop=FontProperties(weight=weight))
    return path.get_extents().width / 72.0 * UNITS_PER_INCH


def possessionArrow(direction):
    ## Marker triangle pointing the way this offense drives, flattened vertically.
    tip, base, half = 0.5 * direction, -0.5 * direction, POSSESSION_ARROW_H / 2
    return Path([(base, -half), (tip, 0.0), (base, half), (base, -half)],
                [Path.MOVETO, Path.LINETO, Path.LINETO, Path.CLOSEPOLY])


def logoSize(logo):
    ## Drawn (width, height) in yards, at the logo's own aspect ratio
    height_px, width_px = logo.shape[0], logo.shape[1]
    scale = min(SCOREBOARD_LOGO_H / height_px, SCOREBOARD_LOGO_W / width_px)
    return width_px * scale, height_px * scale


def drawLogo(ax, logo, x, y):
    ## Logo centered on (x, y).
    width, height = logoSize(logo)
    ax.imshow(logo, extent=(x - width / 2, x + width / 2, y + height / 2, y - height / 2),
              aspect='auto', zorder=6, interpolation='antialiased')


def drawScoreboard(ax, y, clock_text, poss_text, tech_score, oppo_score,
                   techLogo, oppoLogo, color, fallback_text, techHasBall, fontsize=12):
    ## Drive header
    ax.text(50, y + SCOREBOARD_SUBLINE, clock_text, fontsize=CLOCK_FONTSIZE,
            fontweight='bold', va='center', ha='center', color=HEADER_TEXT_COLOR)

    if techLogo is None or oppoLogo is None:
        ## No logos to point at, so name the team that has the ball instead
        ax.text(50, y, f"{fallback_text} | {poss_text}", fontsize=fontsize,
                fontweight='bold', va='center', ha='center', color=color)
        return

    score_text = f"{tech_score} - {oppo_score}"
    score_half = textWidthYards(score_text, fontsize) / 2
    tech_width, oppo_width = logoSize(techLogo)[0], logoSize(oppoLogo)[0]

    tech_x = 50 - score_half - SCOREBOARD_GAP - tech_width / 2
    oppo_x = 50 + score_half + SCOREBOARD_GAP + oppo_width / 2
    ax.text(50, y, score_text, fontsize=fontsize, fontweight='bold',
            va='center', ha='center', color=HEADER_TEXT_COLOR)
    drawLogo(ax, techLogo, tech_x, y)
    drawLogo(ax, oppoLogo, oppo_x, y)

    ## Possession arrow
    arrow_x = tech_x if techHasBall else oppo_x
    arrow_half = POSSESSION_ARROW_PT / 72.0 * UNITS_PER_INCH / 2
    ## TextPath measures ink, which runs a little narrower than the rendered string,
    ## so pad the clock before deciding how far out the arrow has to sit.
    clear = textWidthYards(clock_text, CLOCK_FONTSIZE) * 1.1 / 2 + arrow_half + SCOREBOARD_GAP
    if abs(arrow_x - 50) < clear:
        arrow_x = 50 + clear * (1 if arrow_x >= 50 else -1)
    ax.plot([arrow_x], [y + SCOREBOARD_SUBLINE],
            marker=possessionArrow(1 if techHasBall else -1), markersize=POSSESSION_ARROW_PT,
            color=color, alpha=0.75, linestyle='None', zorder=6)


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
    ## Perceived brightness (0-255) of a #RRGGBB color; lower is darker.
    h = str(hex_color).lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 0.299 * r + 0.587 * g + 0.114 * b


def whiteToBlack(hex_color):
    ## Replace a white team color with black for a better chart
    h = str(hex_color).lstrip('#').lower()
    if h in ('fff', 'ffffff'):
        return '#000000'
    return hex_color


def loadTeamColorsCsv(path=TEAM_COLORS_CSV):
    ## team (lowercased) -> {'pass': ..., 'run': ...} from the saved color table
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


def appendTeamColors(team, pass_color, run_color, path=TEAM_COLORS_CSV):
    ## Add one team to the color table, writing the header if the file is new
    os.makedirs(os.path.dirname(path), exist_ok=True)
    is_new = not os.path.isfile(path)
    with open(path, 'a', newline='') as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(['team', 'passColor', 'runColor'])
        writer.writerow([team, pass_color, run_color])


def fetchTeamColors(team):
    ## (pass, run) from ESPN — darker color for pass, lighter for run — or None
    team_id = lookupEspnId(team)
    if team_id is None:
        print(f"No ESPN id for '{team}' in csv/espnTeamIDs.csv.")
        return None
    try:
        from lib.fbCommon import getTeamInfo
        _, color1, color2 = getTeamInfo(str(team_id))
    except Exception as e:
        print(f"Could not fetch ESPN colors for '{team}' ({type(e).__name__}: {e}).")
        return None
    c1 = whiteToBlack('#' + str(color1).lstrip('#'))
    c2 = whiteToBlack('#' + str(color2).lstrip('#'))
    try:
        return tuple(sorted((c1, c2), key=hexLuminance))
    except (ValueError, IndexError):
        return c1, c2  # non-hex color: keep color1/color2 order


def teamColors(team, path=TEAM_COLORS_CSV):
    ## A team's chart colors.
    entry = loadTeamColorsCsv(path).get(str(team).strip().lower())
    if entry is None:
        fetched = fetchTeamColors(team)
        if fetched is None:
            entry = dict(FALLBACK_TEAM_COLORS)
            print(f"Wrote placeholder colors for '{team}' to {path} — edit that row to fix them.")
        else:
            entry = {'pass': fetched[0], 'run': fetched[1]}
            print(f"Added '{team}' to {path}: pass={entry['pass']}, run={entry['run']}")
        appendTeamColors(team, entry['pass'], entry['run'], path)
    return {**NON_TEAM_COLORS, **entry}


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


def finalScore(df, team):
    ## (tech score, opponent score) from the last row that carries a score
    for row in reversed(list(df.itertuples())):
        if pd.isna(row.offense_score) or pd.isna(row.defense_score):
            continue
        if row.offense == team:
            return int(row.offense_score), int(row.defense_score)
        return int(row.defense_score), int(row.offense_score)
    return None


def quarterOf(clock):
    ## Period number from a clock string like 'Q5 0:19'; None if it doesn't parse
    m = re.match(r'\s*Q(\d+)', str(clock))
    return int(m.group(1)) if m else None


def overtimeLabel(period):
    ## Periods past the 4th are overtimes: Q5 -> 'OT1', Q6 -> 'OT2', ...
    return f"OT{period - 4}"


def drawDivider(ax, y, label):
    ## Full-width rule with a boxed label, used for halftime and each overtime
    ax.axhline(y, color='black', linewidth=3, zorder=5)
    ax.text(50, y, f" {label} ", fontsize=12, fontweight='bold',
            va='center', ha='center', color='black',
            bbox=dict(facecolor=BACKGROUND_COLOR, edgecolor='black', pad=3), zorder=6)


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
    'Kickoff', 'Kickoff Return (Offense)', 'Return Touchdown', 'Touchback',
    'Punt', 'Punt Return', 'Field Goal Good', 'Field Goal Missed', 'Blocked Field Goal',
}


def ordinalDown(down):
    """1 -> '1', 2 -> '2nd', 3 -> '3rd', 4 -> '4th'."""
    return {1: '1', 2: '2', 3: '3', 4: '4'}.get(int(down), '')


## Yards of clearance between the flat tail of the arrow and the down label
DOWN_LABEL_PAD = 0.8


## Interceptions get a contrasting hatch overlay so they stand out by texture,
## independent of the team's fill color (which varies game to game).
INTERCEPTION_HATCH = '///'
INTERCEPTION_HATCH_COLOR = 'white'
## Penalties are drawn as patterned gold so they don't blend into a team whose
## color happens to be gold (e.g. LSU): a black cross-hatch over the gold fill.
PENALTY_HATCH = '/////'
PENALTY_HATCH_COLOR = 'goldenrod'


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

    ## Small down label just outside the flat tail of the arrow. Keeping it off the
    ## fill means it never has to contrast with a team color, so it's always black.
    if playType not in NO_FIRST_DOWN_TYPES and pd.notna(row.down):
        if row.gained == 0:
            arrow_sign = geo['direction']
        else:
            arrow_sign = 1 if geo['pos_gained'] >= 0 else -1
        label = ax.text(start - arrow_sign * DOWN_LABEL_PAD, i, ordinalDown(row.down),
                        fontsize=6, color='black', va='center',
                        ha='right' if arrow_sign > 0 else 'left', zorder=6)
        ## Thin white halo for the goal-line case, where the label lands on an endzone
        label.set_path_effects([path_effects.withStroke(linewidth=0.8, foreground='white')])

    ## KICKOFF (drawn as a dashed line, like a punt)
    if playType == 'Kickoff':
        ko_marker = '<' if geo['marker'] == '>' else '>'
        ax.text(start, i+0.5, " Kickoff ", fontsize=8, va='top', ha=geo['zha'])
        ax.plot([start, start + geo['pos_gained']], [i, i], '--', marker=ko_marker, markersize=1, linewidth=2, color='black')

    elif playType == 'Kickoff Return (Offense)':
        ax.text(start, i+0.5, " Return ", fontsize=8, va='top', ha=geo['ha'])
        ax.plot([start, start + geo['pos_gained']], [i, i], '--', marker=geo['marker'], markersize=1, linewidth=2, color='black')

    elif playType == 'Return Touchdown':
        ax.text(start, i+0.5, " Return ", fontsize=8, va='top', ha=geo['ha'])
        ax.plot([start, start + geo['pos_gained']], [i, i], '--', marker=geo['marker'], markersize=1, linewidth=2, color='black')

        text_obj=ax.text(geo['endzone_mid'], i, "  TD!  ", weight='bold', fontsize=20, color='white', va='center', ha='center')
        
        text_obj.set_path_effects([
            path_effects.PathPatchEffect(offset=(2, -2), hatch='xxxx', facecolor='gray'),
            path_effects.withStroke(linewidth=1, foreground="black")
        ])

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

    ## Fumble returned for a TD — same as an interception-return TD, but labeled "Fumble!".
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


def htmlDir(year):
    ## Pages are grouped by season, e.g. 2025 -> 'html/fbPlaychart/2025'
    return os.path.join(HTML_DIR, str(year))


def findPbpCsv(year, week):
    ## Path to the cached play-by-play CSV for a week of a season
    prefix = f"fbPlaychartPBP_wk{week}_"
    csv_dir = pbpDir(year)
    if os.path.isdir(csv_dir):
        for fn in sorted(os.listdir(csv_dir)):
            if fn.startswith(prefix) and fn.endswith('.csv'):
                return os.path.join(csv_dir, fn)
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


def loadYears(base_dir, current=None):
    ## Available seasons are the four-digit subdirectories of base_dir, newest first
    years = set()
    listing = os.listdir(base_dir) if os.path.isdir(base_dir) else []
    for fn in listing:
        if re.fullmatch(r'\d{4}', fn) and os.path.isdir(os.path.join(base_dir, fn)):
            years.add(int(fn))
    if current is not None:
        years.add(int(current))
    return sorted(years, reverse=True)


def fbPlaychart(team='Louisiana Tech', techColorPath='lib/fbPlaychartColorsTech.txt',
                 teamColorsCsv=TEAM_COLORS_CSV, refreshData=False, year=2025, week=4):
    if refreshData:
        df = getPBPData(year, week, team)
    else:
        csv_path = findPbpCsv(year, week)
        if csv_path is None:
            raise FileNotFoundError(
                f"No cached play-by-play CSV for week {week} in {pbpDir(year)}/. "
                "Run with refreshData=True first.")
        df = pd.read_csv(csv_path)

    opponent = next((o for o in df['offense'].dropna().unique() if o != team), 'Opponent')

    techColors = loadColors(techColorPath)
    ## Saved colors for this opponent, pulled from ESPN the first time we chart them.
    oppoColors = teamColors(opponent, teamColorsCsv)

    ## Logos for the drive-header scoreboards, fetched once per game
    techLogo, oppoLogo = teamLogo(team), teamLogo(opponent)

    fig, ax = setupChart(techColors['pass'], oppoColors['run'])

    i = 0
    offense = ''
    prev_row = None
    last_overtime = 4  # highest period we've already drawn an overtime divider for
    hover_texts = {}  # gid -> play text, for the HTML tooltips
    for row in df.itertuples():
        if row.type == 'End of Half':
            ## Draw a full-width divider between the two halves.
            i += 4
            drawDivider(ax, i, 'Halftime')
            i += 4
            prev_row = row
            continue

        if row.type in ('End Period', 'Timeout', 'End of Game'):
            continue

        ## Each overtime period gets its own divider, then starts a fresh drive.
        period = quarterOf(row.clock)
        if period is not None and period > 4 and period > last_overtime:
            last_overtime = period
            i += 4
            drawDivider(ax, i, overtimeLabel(period))
            i += 4
            offense = ''  # force a drive header for the first possession of the period

        if row.offense != offense or row.type == 'Kickoff':
            offense = row.offense
            i += DRIVE_GAP
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

            drawScoreboard(ax, i - DRIVE_HEADER_Y, formatClock(row.clock), f"{offense} Ball",
                           int(tech_score), int(oppo_score), techLogo, oppoLogo,
                           headerColors['pass'], scoreString, offense == team)

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

    ## Final score below the last play, in the winner's color
    final = finalScore(df, team)
    if final is not None:
        tech_final, oppo_final = final
        if tech_final == oppo_final:
            winner, winnerColors = None, techColors
            finalString = f"Final: {team} {tech_final}, {opponent} {oppo_final}"
        else:
            winner = team if tech_final > oppo_final else opponent
            winnerColors = techColors if winner == team else oppoColors
            finalString = f"{winner} won {max(final)}-{min(final)}"
        i += 12
        ax.text(50, i, finalString, fontsize=18, fontweight='bold',
                va='center', ha='center', color=winnerColors['pass'])
        i += 6

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
    html_dir = htmlDir(year)
    os.makedirs('out', exist_ok=True)
    os.makedirs(html_dir, exist_ok=True)

    fig_path = os.path.join('out', slug + '.png')
    fig.savefig(fig_path, bbox_inches='tight', pad_inches=0, dpi=200,
                transparent=False, facecolor=BACKGROUND_COLOR)

    ## Also export an HTML version by embedding matplotlib's OWN SVG of the figure.
    import io
    html_path = os.path.join(html_dir, html_filename)
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
        " #gtpdd-nav .nav-title { color: #eee; font-size: 15px; font-weight: 600;"
        " white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }"
        " @media (max-width: 640px) {"
        " #gtpdd-nav { gap: 6px; padding: 6px 8px; }"
        " #gtpdd-nav .nav-text { display: none; }"        # drop "Back to" / "home"
        " #gtpdd-nav .nav-arrow { display: inline; }"     # show the left arrow instead
        " #gtpdd-nav label { display: none; }"            # drop the "Year:"/"Game:" labels
        " #gtpdd-nav .nav-title { display: none; }"       # the game dropdown already names the game
        " #gtpdd-nav select { max-width: 120px; }"        # much narrower dropdown
        " #gtpdd-nav #gtpdd-year { max-width: 80px; }"    # the year only needs four digits
        " #gtpdd-nav a.navbtn, #gtpdd-nav button, #gtpdd-nav select { padding: 6px 8px; } }"
        " #pbp-tooltip { position: fixed; pointer-events: none; z-index: 30;"
        " max-width: 380px; padding: 6px 9px; border-radius: 5px; display: none;"
        " background: rgba(20,20,20,0.92); color: #fff;"
        " font: 13px/1.35 -apple-system, Segoe UI, sans-serif;"
        " box-shadow: 0 2px 8px rgba(0,0,0,0.3); }"
    )

    ## Nav header: home button + year and game selectors
    current_href = html_filename
    games = loadGames(html_dir, current={'week': week, 'opponent': opponent, 'href': current_href})
    with open(os.path.join(html_dir, 'games.json'), 'w') as f:
        json.dump(games, f, indent=2)
    ## Season manifest lives one level up, shared by every year's pages.
    years = loadYears(HTML_DIR, current=year)
    with open(os.path.join(HTML_DIR, 'years.json'), 'w') as f:
        json.dump(years, f, indent=2)
    current_label = f"Wk {week} — {opponent}"
    page_title = f"{team} vs {opponent} — Wk {week}, {year}"
    options = "<option value='{}' selected>{}</option>".format(
        html_escape(current_href, quote=True), html_escape(current_label))
    year_options = "<option value='{0}' selected>{0}</option>".format(year)
    ## "Back to <gtpdd logo> home" — embed the logo (falls back to a relative path).
    ## Fallback path is relative to html/fbPlaychart/<year>/, i.e. two levels under html/
    logo_src = logoDataUri('img/gtpdd_logo.png') or '../../img/gtpdd_logo.png'
    logo_img = "<img class='navlogo' src='" + html_escape(logo_src, quote=True) + "' alt='gtpdd'>"
    navbar = (
        "<div id='gtpdd-nav'>"
        "<a class='navbtn' href='" + html_escape(HOME_URL, quote=True) + "'>"
        "<span class='nav-arrow'>&#8592;</span>"
        "<span class='nav-text'>Back to</span>" + logo_img +
        "<span class='nav-text'>home</span></a>"
        "<span class='spacer'></span>"
        "<span class='nav-title'>" + html_escape(SITE_TITLE) + "</span>"
        "<span class='spacer'></span>"
        "<label for='gtpdd-year'>Year:</label>"
        "<select id='gtpdd-year'>" + year_options + "</select>"
        "<label for='gtpdd-game'>Game:</label>"
        "<select id='gtpdd-game'>" + options + "</select>"
        "<button id='gtpdd-go'>Load</button>"
        "</div>"
    )
    nav_js = (
        "<script>(function(){"
        "var cur=" + json.dumps(current_href) + ";"
        "var curYear=" + json.dumps(str(year)) + ";"
        "var ysel=document.getElementById('gtpdd-year');"
        "var sel=document.getElementById('gtpdd-game');"
        "document.getElementById('gtpdd-go').addEventListener('click',function(){"
        "if(sel.value)window.location.href=sel.value;});"
        ## Each year's games come from that year's manifest; hrefs are relative to
        ## this page, which sits in html/fbPlaychart/<year>/.
        "function fillGames(y){return fetch('../'+y+'/games.json')"
        ".then(function(r){return r.json();}).then(function(gs){"
        "sel.innerHTML='';"
        "gs.forEach(function(g){var o=document.createElement('option');"
        "o.value='../'+y+'/'+g.href;o.textContent=g.label;"
        "if(y===curYear&&g.href===cur)o.selected=true;"
        "sel.appendChild(o);});"
        "}).catch(function(){});}"
        "ysel.addEventListener('change',function(){fillGames(ysel.value);});"
        ## Populate the year selector from the manifest shared by every season.
        "fetch('../years.json').then(function(r){return r.json();}).then(function(ys){"
        "ysel.innerHTML='';"
        "ys.forEach(function(y){var o=document.createElement('option');"
        "o.value=y;o.textContent=y;if(String(y)===curYear)o.selected=true;"
        "ysel.appendChild(o);});"
        "}).catch(function(){});"
        "fillGames(curYear);"
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
        "<title>" + html_escape(page_title + " Play Chart") + "</title>\n"
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
    args = parser.parse_args()

    fbPlaychart(year=args.year, week=args.week, refreshData=args.refresh_data)