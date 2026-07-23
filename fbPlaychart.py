# -*- coding: utf-8 -*-
"""
Created on Wed Nov  2 18:06:08 2022

@author: ntrup
"""

## TODO: This still needs a lot of work

import json
import os

import cfbd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

BACKGROUND_COLOR = '#d6e8cf'  # muted light green

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

    dictList = []
    for play in api_response:
        dictList.append({
            'offense': play.offense,
            'clock': f"Q{play.period} {play.clock.minutes}:{play.clock.seconds}",
            'down': play.down,
            'distance': play.distance,
            'type': play.play_type,
            'start': play.yard_line,
            'gained': play.gained,
        })

    df = pd.DataFrame(dictList)
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


def playGeometry(row, team, techColors, oppoColors):
    """Geometry/colors for drawing a play, mirrored depending on which team has the ball."""
    gained = row.gained
    if row.offense == team:
        return {
            'colors': techColors,
            'pos_gained': gained - 1.9,
            'neg_gained': gained + 1.9,
            'fg_yards': gained - 10,
            'int_endzone': 0,
            'endzone': 100,
            'marker': '>',
            'ha': 'left',
            'zha': 'right',
        }
    else:
        return {
            'colors': oppoColors,
            'pos_gained': -gained + 1.9,
            'neg_gained': -gained - 1.9,
            'fg_yards': -gained - 10,
            'int_endzone': 100,
            'endzone': 0,
            'marker': '<',
            'ha': 'right',
            'zha': 'left',
        }


def drawPlay(ax, row, i, geo):
    """Draw a single play at row height i. Returns the extra vertical offset (if any) to apply before the next play."""
    start = row.start
    playType = row.type

    ## KICKOFF (drawn as a dashed line, like a punt). The ball travels toward the
    ## receiving team's own end, i.e. opposite the offense's normal direction.
    if playType == 'Kickoff':
        ko_marker = '<' if geo['marker'] == '>' else '>'
        ax.text(start, i, " Kickoff ", fontsize=12, va='center', ha=geo['ha'])
        ax.plot([start, start + geo['pos_gained']], [i, i], '--', marker=ko_marker, markersize=1, linewidth=2, color='black')

    elif playType == 'Kickoff Return (Offense)':
        ax.text(start + geo['pos_gained'], i, " Return ", fontsize=12, va='center', ha=geo['ha'])
        ax.plot([start, start + geo['pos_gained']], [i, i], '--', marker=geo['marker'], markersize=1, linewidth=2, color='black')

    elif playType == 'Touchback':
            ax.text(start + geo['pos_gained'], i, " Touchback ", fontsize=12, va='center', ha=geo['ha'])
            ax.plot([start, start + geo['pos_gained']], [i, i], '--', marker=geo['marker'], markersize=1, linewidth=2, color='black')
               

    ## FIELD GOAL
    elif playType == 'Field Goal Good':
        ax.plot([start, start + geo['fg_yards']], [i, i], '--', marker='P', markersize=8, linewidth=4, color='green')
        ax.text(geo['endzone'], i, " FG! ", fontsize=12, color='white', va='top', ha=geo['ha'])
    elif playType == 'Field Goal Missed':
        ax.plot([start, start + geo['fg_yards']], [i, i], '--', marker='X', markersize=8, linewidth=4, color='gray')
        ax.text(geo['endzone'], i+1, " FG Miss! ", fontsize=10, color='white', va='top', ha=geo['ha'])


    ## PUNT
    elif playType == 'Punt':
        ax.text(start, i, " Punt ", fontsize=12, va='center', ha=geo['zha'])
        ax.plot([start, start + geo['pos_gained']], [i, i], '--', marker=geo['marker'], markersize=1, linewidth=2, color='black')

    ## PUNT RETURN
    elif playType == 'Punt Return':
        ax.text(start, i, " Punt Return ", fontsize=12, va='center', ha=geo['zha'])
        ax.plot([start, start + geo['pos_gained']], [i, i], '--', marker=geo['marker'], markersize=1, linewidth=2, color='black')


    ## INTERCEPTION
    elif playType == 'Interception':
        ax.text(start, i, 'INTERCEPTION', color='purple', fontsize='40', ha=geo['ha'])

    elif playType == 'Interception Return Touchdown':
        color = playColor(playType, geo['colors'])
        ax.arrow(start, i, -1 * (start - geo['int_endzone']), 0, width=3.5, head_width=3.5, head_length=0.9, facecolor=color, edgecolor='black', linewidth=0.5)
        ax.text(geo['int_endzone'], i, " INT TD! ", fontsize=12, color = 'white', va='center', ha=geo['zha'])

    else:
        color = playColor(playType, geo['colors'])
        if row.gained > 0:
            ax.arrow(start, i, geo['pos_gained'], 0, width=3.5, head_width=3.5, head_length=0.9, facecolor=color, edgecolor='black', linewidth=0.5)
        elif row.gained < 0:
            ax.arrow(start, i, geo['neg_gained'], 0, width=3.5, head_width=3.5, head_length=0.9, facecolor=color, edgecolor='black', linewidth=0.5)
        else:
            ax.plot([start, start], [i - 1.75, i + 1.75], color=color, linewidth=1)

        if 'Touchdown' in playType:
            ax.text(geo['endzone'], i, " TD! ", fontsize=12, color='white', va='center', ha=geo['ha'])

        elif 'Sack' in playType:
            ax.text(start, i, ' Sack! ', color='black', fontsize='12', ha=geo['ha'], va='center')

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
                 year=2024, week=1):
    if refreshData:
        df = getPBPData(year, week, team)
    else:
        df = pd.read_csv('csv/fbPlaychartPBP.csv')

    techColors = loadColors(techColorPath)
    oppoColors = loadColors(oppoColorPath)

    fig, ax = setupChart(techColors['pass'], oppoColors['pass'])

    i = 0
    offense = ''
    for row in df.itertuples():
        if row.type in ('End Period', 'End of Half', 'Timeout'):
            continue

        if row.offense != offense:
            offense = row.offense
            i += 10
            ## Drive header: who has the ball and the clock at the drive's start.
            headerColors = techColors if offense == team else oppoColors
            ax.text(50, i - 5, f"{offense}  —  {formatClock(row.clock)}",
                    fontsize=12, fontweight='bold', va='center', ha='center',
                    color=headerColors['pass'])

        geo = playGeometry(row, team, techColors, oppoColors)
        i += drawPlay(ax, row, i, geo)
        i += 4

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


fbPlaychart()
