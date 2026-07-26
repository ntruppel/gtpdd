# -*- coding: utf-8 -*-
"""
Created on Wed Nov  2 18:06:08 2022

@author: ntrup
"""

## TODO: This still needs a lot of work

import json
import os
import re

import cfbd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.patheffects as path_effects
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

BACKGROUND_COLOR = "#d6e8cf"  # muted light green

PLAY_COLOR_KEYS = {
    'Pass Reception': 'pass',
    'Passing Touchdown': 'pass',
    'Pass Incompletion': 'pass',
    'Rush': 'run',
    'Rushing Touchdown': 'run',
    'Penalty': 'penalty',
    'Sack': 'sack',
    'Pass Interception Return': 'int',
    'Interception Return Touchdown': 'int',
    'Safety': 'safety',
    'Fumble Recovery (Opponent)': 'fumble'

}


def getPBPData(year=2024, week=1, team='Louisiana Tech'):
    ## CFBD Configuration
    configuration = cfbd.Configuration(access_token=os.environ["cfbdAuth"])
    api_instance = cfbd.PlaysApi(cfbd.ApiClient(configuration))

    ## TODO: Grab the most recent game automatically
    api_response = api_instance.get_plays(year, week=week, team=team)
    print(api_response)
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

    df.to_csv('csv/fbPlaychartPBP.csv')
    return df


## Inches of figure per data-unit, kept roughly equal on both axes so the
## fixed-width play arrows keep their proportions instead of squishing.
UNITS_PER_INCH = 13.0
X_RANGE = 126  # xlim spans -13 .. 113


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

    return fig, ax


def loadColors(path):
    with open(path) as f:
        return json.load(f)


def formatClock(clock):
    """Tidy the stored clock string (e.g. 'Q1 15:0' -> 'Q1 15:00')."""
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
    """Shorten a signed displacement toward zero by ~1.9 (to leave a gap for the
    arrowhead) without ever flipping its sign — short plays keep pointing the right way."""
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


def drawPlay(ax, row, i, geo):
    """Draw a single play at row height i. Returns the extra vertical offset (if any) to apply before the next play."""
    start = row.start
    playType = row.type

    ## Faint orange first-down line: "distance" yards downfield from the start,
    ## in the direction the offense is driving.
    if playType not in NO_FIRST_DOWN_TYPES and pd.notna(row.distance):
        first_down = start + geo['direction'] * row.distance
        ax.plot([first_down, first_down], [i - 1.8, i + 1.8],
                color='orange', alpha=0.2, linewidth=2, zorder=1)

    ## Small down label inside the arrow, on its bottom edge, anchored to the
    ## tail (the side opposite the direction the arrow points).
    if playType not in NO_FIRST_DOWN_TYPES and pd.notna(row.down):
        ax.text(start, i + 1.6, ordinalDown(row.down), fontsize=6, color='white',
                va='bottom', ha=geo['ha'], zorder=6)

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
        ax.arrow(start, i, -1 * (start - geo['oppo_endzone']), 0, width=3.5, head_width=3.5, head_length=0.9, facecolor=color, edgecolor='black', linewidth=0.5)
        ax.text(start, i+2, " Interception ", fontsize=8, va='top', ha=geo['zha'])
        text_obj=ax.text(geo['oppo_endzone_mid'], i, "  TD!  ", weight='bold', fontsize=20, color='white', va='center', ha='center')

        text_obj.set_path_effects([
            path_effects.PathPatchEffect(offset=(2, -2), hatch='xxxx', facecolor='gray'),
            path_effects.withStroke(linewidth=1, foreground="black")
        ])
    else:
        color = playColor(playType, geo['colors'])
        if row.gained > 0:
            ax.arrow(start, i, geo['pos_gained'], 0, width=3.5, head_width=3.5, head_length=0.9, facecolor=color, edgecolor='black', linewidth=0.5)
        elif row.gained < 0:
            ax.arrow(start, i, geo['neg_gained'], 0, width=3.5, head_width=3.5, head_length=0.9, facecolor=color, edgecolor='black', linewidth=0.5)
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


def fbPlaychart(team='Louisiana Tech', techColorPath='lib/fbPlaychartColorsTech.txt',
                 oppoColorPath='lib/fbPlaychartColorsOppo.txt', refreshData=False,
                 year=2025, week=4):
    if refreshData:
        df = getPBPData(year, week, team)
    else:
        df = pd.read_csv('csv/fbPlaychartPBP.csv')

    techColors = loadColors(techColorPath)
    oppoColors = loadColors(oppoColorPath)

    fig, ax = setupChart(techColors['pass'], oppoColors['pass'])

    i = 0
    offense = ''
    prev_row = None
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
        i += drawPlay(ax, row, i, geo)
        i += 4
        prev_row = row

    ## Size the figure so vertical spacing matches the horizontal scale,
    ## keeping the fixed-width play arrows from squishing on a tall chart.
    y_extent = i + 10
    ax.set_ylim(y_extent, -10)  # inverted: first play at top
    ## Label a tick at every play-spacing step so each row is easy to track.
    ax.yaxis.set_major_locator(mticker.MultipleLocator(4))
    ax.tick_params(axis='y', labelsize=4)
    width = X_RANGE / UNITS_PER_INCH
    height = max(8.0, y_extent / UNITS_PER_INCH)
    fig.set_size_inches(width, height)

    fig_path = 'out/fbPlaychart.png'
    fig.savefig(fig_path, bbox_inches='tight', pad_inches=0, dpi=200,
                transparent=False, facecolor=BACKGROUND_COLOR)
    print("Done.")


fbPlaychart(refreshData=True)
#df = getPBPData(2025, 4, 'Louisiana Tech')