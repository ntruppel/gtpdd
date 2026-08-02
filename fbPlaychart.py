# -*- coding: utf-8 -*-
"""
Created on Wed Nov  2 18:06:08 2022

@author: ntrup
"""

## TODO: This still needs a lot of work

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
    'Fumble Recovery (Opponent)': 'fumble'

}


def getPBPData(year=2024, week=1, team='Louisiana Tech'):
    ## CFBD Configuration
    configuration = cfbd.Configuration(access_token=os.environ["cfbdAuth"])
    api_instance = cfbd.PlaysApi(cfbd.ApiClient(configuration))

    ## TODO: Grab the most recent game automatically
    api_response = api_instance.get_plays(year, week=week, team=team)
    #print(api_response)
    dictList = []
    for play in api_response:
        dictList.append({
            'offense': play.offense,
            'clock': f"Q{play.period} {play.clock.minutes}:{play.clock.seconds}",
            'down': play.down,
            'distance': play.distance,
            'type': play.play_type,
            'start': play.yardline,
            'gained': play.yards_gained,
            'text': play.play_text,
            'id': play.id,
            'offense_score': play.offense_score,
            'defense_score': play.defense_score,
        })

    opponent = next((d['offense'] for d in dictList if d['offense'] and d['offense'] != team), team)
    processed = []
    for d in dictList:
        text = str(d.get('text') or '')

        ## Kickoff touchbacks: the CFBD "Kickoff" row is credited to the kicking
        ## team. Flip it to the receiving team, mark it as a 65-yard kick, and
        ## insert a following "Touchback" row spotting the ball at the 25.
        if d['type'] == 'Kickoff' and 'touchback' in text.lower():
            d['offense'] = opponent if d['offense'] == team else team
            d['gained'] = -65
            processed.append(d)

            touchback = dict(d)
            touchback['type'] = 'Touchback'
            touchback['start'] = 0 if touchback['offense'] == team else 100
            touchback['gained'] = 25
            processed.append(touchback)

        ## Kickoffs without a touchback: like the touchback case, credit the row
        ## to the receiving team. Take the kick distance from the text ("kickoff
        ## for N yds") as a negative gained so it draws toward the receiver's end.
        elif d['type'] == 'Kickoff':
            d['offense'] = opponent if d['offense'] == team else team
            ko_match = re.search(r'kickoff for (\d+)', text, re.IGNORECASE)
            if ko_match:
                d['gained'] = -int(ko_match.group(1))
            processed.append(d)

        ## Returned kickoffs: split the CFBD "Kickoff Return (Offense)" row into
        ## the kick leg and the return leg, like punts. Flip to the receiving team,
        ## make this row the kick itself ("kickoff for N", drawn as a negative
        ## gained toward the receiver's end), then add a "Kickoff Return (Offense)"
        ## row for the runback ("return for N") starting where the ball was caught.
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

        ## Punts: CFBD's "gained" is unreliable — take the punt distance from the
        ## text ("punt for N yds"). If the returner brought it back ("returns for
        ## N yds"), add a following "Punt Return" row for the receiving team,
        ## starting where the punt was caught.
        elif d['type'] == 'Punt':
            punt_match = re.search(r'punt for (\d+)', text, re.IGNORECASE)
            if punt_match:
                d['gained'] = int(punt_match.group(1))
            processed.append(d)

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

        else:
            processed.append(d)
    dictList = processed

    df = pd.DataFrame(dictList)

    ## CFBD can return plays out of game order — sort chronologically from the
    ## clock string "Q<period> M:SS": quarter ascending, then time remaining
    ## descending (the clock counts down within a quarter), then play id ascending
    ## to break same-clock ties. A stable sort keeps inserted rows (touchbacks,
    ## punt returns) right after their parent play, since they share its id.
    clock_parts = df['clock'].str.extract(r'Q(\d+)\s+(\d+):(\d+)').astype(float)
    df['_period'] = clock_parts[0]
    df['_secs_remaining'] = clock_parts[1] * 60 + clock_parts[2]
    df['_id'] = pd.to_numeric(df['id'], errors='coerce')
    df = (df.sort_values(['_period', '_secs_remaining', '_id'], ascending=[True, False, True], kind='stable')
            .drop(columns=['_period', '_secs_remaining', '_id'])
            .reset_index(drop=True))

    ## Per-game CSV: csv/fbPlaychartPBP/fbPlaychartPBP_wk<week>_<opponent>.csv
    os.makedirs(PBP_DIR, exist_ok=True)
    df.to_csv(os.path.join(PBP_DIR, f"fbPlaychartPBP_{gameSlug(week, opponent)}.csv"))
    return df


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
    ## (This chart only has lines on the 10s, unlike a real field's every-5.)
    for yard in range(0, 101, 10):
        lw = 3 if yard in (0, 50, 100) else 1
        ax.axvline(yard, color='white', linewidth=lw, zorder=0)

    ## Yard numbers along the top, upside down (far-sideline view from above).
    drawYardNumbers(ax, -6, upside_down=True)

    return fig, ax


def loadColors(path):
    with open(path) as f:
        return json.load(f)


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
    """Geometry/colors for drawing a play, mirrored depending on which team has the ball."""
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


## Special-teams / non-scrimmage rows have no meaningful "yards to gain," so we
## skip the first-down line for them.
NO_FIRST_DOWN_TYPES = {
    'Kickoff', 'Kickoff Return (Offense)', 'Touchback',
    'Punt', 'Punt Return', 'Field Goal Good', 'Field Goal Missed',
}


def ordinalDown(down):
    """1 -> '1', 2 -> '2nd', 3 -> '3rd', 4 -> '4th'."""
    return {1: '1', 2: '2', 3: '3', 4: '4'}.get(int(down), '')


## Interceptions get a contrasting hatch overlay so they stand out by texture,
## independent of the team's fill color (which varies game to game).
INTERCEPTION_HATCH = '//'
INTERCEPTION_HATCH_COLOR = 'white'


def drawArrow(ax, x, y, dx, color, interception=False):
    """Draw a play arrow (int-color fill, black outline). Interceptions get a
    second overlay arrow with no fill and a hatch, so the pattern reads on top
    of any fill color while the base arrow keeps its outline."""
    ax.arrow(x, y, dx, 0, width=3.5, head_width=3.5, head_length=0.9,
             facecolor=color, edgecolor='black', linewidth=0.5)
    if interception:
        ax.arrow(x, y, dx, 0, width=3.5, head_width=3.5, head_length=0.9,
                 facecolor='none', edgecolor=INTERCEPTION_HATCH_COLOR,
                 linewidth=0, hatch=INTERCEPTION_HATCH, zorder=3)


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

    ## KICKOFF (drawn as a dashed line, like a punt). The ball travels toward the
    ## receiving team's own end, i.e. opposite the offense's normal direction.
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
    elif playType == 'Field Goal Missed':
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
    else:
        color = playColor(playType, geo['colors'])
        is_int = 'Interception' in playType
        if row.gained > 0:
            drawArrow(ax, start, i, geo['pos_gained'], color, interception=is_int)
        elif row.gained < 0:
            drawArrow(ax, start, i, geo['neg_gained'], color, interception=is_int)
        else:
            ax.plot([start, start], [i - 1.75, i + 1.75], color=color, linewidth=1)

        if 'Touchdown' in playType:
            text_obj=ax.text(geo['endzone_mid'], i, "  TD!  ", weight='bold', fontsize=20, color='white', va='center', ha='center')

            text_obj.set_path_effects([
                path_effects.PathPatchEffect(offset=(2, -2), hatch='xxxx', facecolor='gray'),
                path_effects.withStroke(linewidth=1, foreground="black")
            ])
        elif 'Sack' in playType:
            ax.text(start+geo['neg_gained'], i, '  Sack!  ', color='black', fontsize='8', ha=geo['zha'], va='top')

        elif 'Interception' in playType:
            ax.text(start, i, ' INT! ', color='black', fontsize='12', ha=geo['ha'], va='center')

        elif 'Safety' in playType:
            ax.text(geo['int_endzone'], i, " Safety! ", color="white", fontsize=10, va='center', ha=geo['zha'])

        elif 'Fumble Recovery' in playType:
            ## Label on the arrow's pointing (head) end, unless that text would run
            ## into an endzone (x<0 or x>100) — then put it on the flat (tail) end.
            dx = geo['pos_gained'] if row.gained > 0 else (geo['neg_gained'] if row.gained < 0 else 0)
            head_x = start + dx
            fumble_w = 11  # approx width of " Fumble! " in data units
            if dx >= 0:  # arrow points right, head text extends right
                head_ha, tail_ha = 'left', 'right'
                overlaps = head_x + fumble_w > 100
            else:  # arrow points left, head text extends left
                head_ha, tail_ha = 'right', 'left'
                overlaps = head_x - fumble_w < 0
            if overlaps:
                ax.text(start, i, ' Fumble! ', color='black', fontsize=12, ha=tail_ha, va='center')
            else:
                ax.text(head_x+1, i, ' Fumble! ', color='black', fontsize=12, ha=head_ha, va='center')
            

    return 0


def gameSlug(week, opponent):
    """Shared 'wk<week>_<opponent>' slug for a game's output files. Spaces and
    punctuation in the opponent become underscores so the name can be recovered
    from the filename."""
    opp = re.sub(r'[^0-9A-Za-z]+', '_', opponent).strip('_')
    return f"wk{week}_{opp}"


def gameFilename(week, opponent):
    """Page filename for a game, e.g. week 4 vs Southern Miss ->
    'fbPlaychart_wk4_Southern_Miss.html'."""
    return f"fbPlaychart_{gameSlug(week, opponent)}.html"


def findPbpCsv(week):
    """Path to the cached play-by-play CSV for a week (fbPlaychartPBP_wk<week>_*.csv
    in PBP_DIR), or None if none exists yet."""
    prefix = f"fbPlaychartPBP_wk{week}_"
    if os.path.isdir(PBP_DIR):
        for fn in sorted(os.listdir(PBP_DIR)):
            if fn.startswith(prefix) and fn.endswith('.csv'):
                return os.path.join(PBP_DIR, fn)
    return None


def loadGames(html_dir, current=None):
    """Build the game-selector list by scanning html_dir for pages named
    fbPlaychart_wk<week>_<opponent>.html, recovering the week/opponent from each
    filename. `current` ({week, opponent, href}) is folded in so a brand-new game
    appears before its file has been written. Returns dicts sorted by week."""
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
                 year=2025, week=4):
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

    techColors = loadColors(techColorPath)
    oppoColors = loadColors(oppoColorPath)

    fig, ax = setupChart(techColors['pass'], oppoColors['pass'])

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

        if row.offense != offense:
            offense = row.offense
            i += 10
            ## Drive header: who has the ball, the clock, and the score (Tech left,
            ## USM right) at the drive's start. Read the score from the PREVIOUS
            ## play — kickoff rows have had their "offense" flipped, so their own
            ## offense/defense scores no longer line up with that column.
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
    ## keeping the fixed-width play arrows from squishing on a tall chart.
    y_extent = i + 10
    ax.set_ylim(y_extent, -10)  # inverted: first play at top

    ## Yard numbers along the bottom, rightside up (near-sideline view).
    drawYardNumbers(ax, y_extent - 4, upside_down=False)
    ## Axis numbers are hidden for the clean look. To re-enable for debugging,
    ## comment out the tick_params line below and uncomment the two after it.
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
    ## Save with a transparent figure background (facecolor='none') so the page's
    ## dark background shows in the margins instead of a green border — the green
    ## field and endzones live on the axes patch, so they stay.
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

    ## Nav header: home button + a game selector. The full game list lives in
    ## html/fbPlaychart/games.json (rebuilt here from the directory); each page
    ## fetches it at load, so every page reflects all games without regenerating.
    ## A single fallback <option> (this game) is baked in for when the fetch can't
    ## run (e.g. the page opened via file://).
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


fbPlaychart(year=2025, week=3, refreshData=True)
#df = getPBPData(2025, 4, 'Louisiana Tech')