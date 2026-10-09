# -*- coding: utf-8 -*-
"""
Graphic of Bill Connelly's five factors for one Louisiana Tech game.

Each factor (efficiency, explosiveness, drive finishing, field position, turnovers)
is drawn as a pair of bars, Tech vs the opponent, using CFBD's advanced box score.
The headline is CFBD's postgame win expectancy, or a weighted stand-in from the
five factors when CFBD has none.

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

import os

import cfbd
import matplotlib.pyplot as plt
import numpy as np
from dotenv import load_dotenv
from matplotlib.patches import FancyBboxPatch, Rectangle, Wedge
from PIL import Image

from lib.fbCommon import (cfbdApi, currentSeason, gameDateText, getGames, getTeamInfo,
                          localDateTime, resolveEspnId, teamLogo)

# Pull the CFBD API key and other settings from .env
load_dotenv()

####
# CONSTANTS
####

# Team and file locations
TEAM = 'Louisiana Tech'
FIG_PATH = 'out/fbAdvancedBoxScore.png'
BACKGROUND_PATH = 'img/fbAdvancedBoxScoreBackground.png'
LOGO_BOX = 440                     # logos are shrunk to fit this many pixels

# Palette is dark ink on light, translucent panels so the paper background shows through
TECH_COLOR = '#003087'             # Tech blue
INK = '#12141a'
INK_SOFT = '#4a4d57'
INK_MUTED = '#7c7f88'
FALLBACK_OPPO = '#eb6834'          # used when the opponent's colors are too close to Tech blue
MIN_COLOR_DISTANCE = 15            # OKLab x100; below this two colors look the same


# Each factor's label, description, stat key, which direction wins, and display format
FACTORS = [
    {'name': 'Efficiency', 'about': 'Percentage of offensive plays that were successful (aka Success Rate)',
     'key': 'efficiency', 'better': 'high', 'fmt': '{:.1%}'},
    {'name': 'Explosiveness', 'about': 'Of those successful plays, how explosive were they? (aka IsoPPP)',
     'key': 'explosiveness', 'better': 'high', 'fmt': '{:.2f}'},
    {'name': 'Drive Finishing', 'about': "Points per trip inside the Opponents' 40",
     'key': 'finishing', 'better': 'high', 'fmt': '{:.1f}'},
    {'name': 'Field Position', 'about': 'Average yardline of drive start',
     'key': 'field', 'better': 'high', 'fmt': 'own {:.1f}'},
    {'name': 'Turnovers', 'about': 'Offensive giveaways', 'key': 'turnovers',
     'better': 'low', 'fmt': '{:.0f}'},
]

# How strongly each factor correlates with winning; only used if CFBD has no win expectancy
FACTOR_WEIGHTS = {'explosiveness': 0.86, 'efficiency': 0.83, 'finishing': 0.75,
                  'field': 0.72, 'turnovers': 0.73}


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
    # Returns (opponent, 'vs'/'at', kickoff date) for the header
    home = game.home_team == team
    opponent = game.away_team if home else game.home_team
    where = 'vs' if home else 'at'
    # Neutral-site games always read as 'vs'
    if game.neutral_site:
        where = 'vs'
    when = localDateTime(game.start_date) if game.start_date else None
    return opponent, where, (gameDateText(when) or '')


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
# COLORS
####

def oklab(hex_color):
    # Converts sRGB hex to OKLab, where distance matches how different colors look
    h = str(hex_color).lstrip('#')
    # Expand shorthand hex like 'fff'
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    # Undo sRGB gamma to get linear light
    r, g, b = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    # Linear RGB to LMS cone response, then to OKLab
    l = np.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m = np.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s = np.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    return np.array([0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
                     1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
                     0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s])


def colorDistance(a, b):
    # Perceptual distance between two colors, scaled x100
    return float(np.linalg.norm(oklab(a) - oklab(b))) * 100


def contrastRatio(a, b):
    # WCAG contrast ratio, i.e. whether one color is visible against the other
    def luminance(color):
        # Relative luminance of a hex color
        h = str(color).lstrip('#')
        vals = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        vals = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in vals]
        return 0.2126 * vals[0] + 0.7152 * vals[1] + 0.0722 * vals[2]
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def withContrast(hex_color, surface='#ffffff', target=3.0):
    # Darkens a color until it hits the target contrast, so light team colors stay readable
    h = str(hex_color).lstrip('#')
    rgb = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    color = hex_color
    # Each step darkens by 7%; 30 steps is enough to reach any target
    for _ in range(30):
        if contrastRatio(color, surface) >= target:
            return color
        rgb = [max(0, round(c * 0.93)) for c in rgb]
        color = '#%02x%02x%02x' % tuple(rgb)
    return color


def opponentColor(name, avoid=TECH_COLOR):
    # Opponent's primary color, then secondary, then a fallback, whichever is distinct from Tech's
    espn_id = resolveEspnId(name)
    options = []
    # Look up the opponent's two team colors from ESPN
    if espn_id is not None:
        try:
            _, color1, color2 = getTeamInfo(str(espn_id))
            options = ['#' + str(c).lstrip('#') for c in (color1, color2) if c]
        except Exception as e:
            print(f"Could not fetch ESPN colors for '{name}' ({type(e).__name__}: {e}).")

    # Take the first color that's distinct from Tech blue and not near-white
    for option in options:
        if colorDistance(option, avoid) >= MIN_COLOR_DISTANCE \
                and colorDistance(option, '#ffffff') >= MIN_COLOR_DISTANCE:
            return withContrast(option)
    if options:
        print(f"{name}'s colors sit too close to Tech's; using a contrasting stand-in.")
    return withContrast(FALLBACK_OPPO)


####
# LAYOUT
####

# Square canvas in a square figure, so one data unit is square and circles stay round
CANVAS_W, CANVAS_H = 100.0, 100.0
FIG_INCHES = 12.0
HEADER_TOP, HEADER_H = 97.5, 24.0
# Body is two columns: factor rows on the left, win expectancy on the right
BODY_TOP, BODY_BOTTOM = 71.5, 4.0
LEFT_X, LEFT_W = 3.0, 56.0         # the factor column
RIGHT_X, RIGHT_W = 62.0, 35.0      # the win-expectancy panel
BAR_LEFT, BAR_RIGHT = 12.0, 44.0   # the bars' track; values are labelled past the tip
MARK_X = 8.0                       # where the small team logo sits beside each bar
ROW_H = 13.7                       # one factor row


####
# DRAWING
####

def panel(ax, x, y, w, h, facecolor='white', alpha=0.62, edgecolor='none', lw=0, z=1):
    # Draws a translucent rounded panel so the paper background shows through
    box = FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0,rounding_size=1.6',
                         facecolor=facecolor, alpha=alpha, edgecolor=edgecolor,
                         linewidth=lw, zorder=z)
    ax.add_patch(box)
    return box


def drawLogo(ax, img, cx, cy, height, max_width=7.0, z=4):
    # Draws a logo centered at (cx, cy), sized by height with a width cap for wide wordmarks
    if img is None:
        return
    h, w = img.shape[0], img.shape[1]
    # Keep the aspect ratio while respecting the width cap
    width = min(height * w / h, max_width)
    height = width * h / w
    ax.imshow(img, extent=(cx - width / 2, cx + width / 2, cy - height / 2, cy + height / 2),
              aspect='auto', zorder=z)


def bar(ax, x, y, width, height, color, z=3):
    # Draws a horizontal bar with a rounded tip and a square base
    if width <= 0:
        return
    # Too short to round, so draw a plain rectangle
    if width < height:
        ax.add_patch(Rectangle((x, y), width, height, facecolor=color, edgecolor='none', zorder=z))
        return
    # Square body plus a rounded cap at the end
    r = height / 2
    ax.add_patch(Rectangle((x, y), width - r, height, facecolor=color, edgecolor='none', zorder=z))
    ax.add_patch(FancyBboxPatch((x + width - 2 * r, y + r), r, 0,
                                boxstyle=f'round,pad={r}', facecolor=color,
                                edgecolor='none', zorder=z))


def drawFactorRow(ax, factor, values, top, colors, logos):
    # Draws one factor row: title, description, and Tech's bar above the opponent's
    winner = factorWinner(factor, values)
    tech, oppo = values['tech'], values['oppo']

    # Tint the panel and edge stripe in the winner's color (gray on a tie)
    tint = colors[winner] if winner else INK_MUTED
    panel(ax, LEFT_X, top - 12.7, LEFT_W, 11.7, facecolor='white', alpha=0.66)
    panel(ax, LEFT_X, top - 12.7, LEFT_W, 11.7, facecolor=tint, alpha=0.10)
    ax.add_patch(Rectangle((LEFT_X, top - 12.7), 0.7, 11.7,
                           facecolor=tint, edgecolor='none', zorder=2))

    # Factor name and description
    ax.text(LEFT_X + 4.0, top - 2.9, factor['name'], fontsize=18, fontweight='bold',
            color=INK, va='center', ha='left', zorder=4)
    ax.text(LEFT_X + 4.0, top - 5.9, factor['about'], fontsize=12, color=INK_MUTED,
            va='center', ha='left', zorder=4)

    # Both bars share one scale; turnovers get a floor of 2 so zero still shows a track
    span = max(abs(tech), abs(oppo))
    span = max(span * 1.08, 2.0) if factor['key'] == 'turnovers' else max(span * 1.08, 1e-6)
    track = BAR_RIGHT - BAR_LEFT

    # Draw each team's bar, value label and logo
    for value, side, y in ((tech, 'tech', top - 8.9), (oppo, 'oppo', top - 11.5)):
        width = max(0.0, min(value / span, 1.0)) * track
        bar(ax, BAR_LEFT, y - 0.9, width, 1.8, colors[side])
        ax.text(BAR_LEFT + width + 1.3, y, factor['fmt'].format(value), fontsize=15,
                fontweight='bold', color=INK, va='center', ha='left', zorder=4)
        # A small logo identifies whose bar it is
        drawLogo(ax, logos[side], MARK_X, y, 2.2, max_width=4.6)

def drawDonut(ax, center, radius, share, colors):
    # Draws win expectancy as a ring, with Tech's slice running clockwise from the top
    cx, cy = center
    start = 90.0
    # Faded opponent-colored ring as the background
    ax.add_patch(Wedge((cx, cy), radius, 0, 360, width=radius * 0.30,
                       facecolor=colors['oppo'], alpha=0.28, edgecolor='none', zorder=2))
    # Tech's share on top
    ax.add_patch(Wedge((cx, cy), radius, start - share * 360, start,
                       width=radius * 0.30, facecolor=colors['tech'],
                       edgecolor='none', zorder=3))
    # Show a decimal near 0% or 100% so a blowout never reads as a flat 100%
    headline = '{:.0%}'.format(share) if 0.01 <= share <= 0.99 else '{:.1%}'.format(share)
    ax.text(cx, cy, headline, fontsize=52 if len(headline) <= 3 else 38,
            fontweight='bold', color=colors['tech'], va='center', ha='center', zorder=4)

def drawScoreboard(ax, names, points, colors, logos, date_text):
    # Draws the header: title, date, logos, names and score; it also serves as the color legend
    panel(ax, 3, HEADER_TOP - HEADER_H, CANVAS_W - 6, HEADER_H, facecolor='white', alpha=0.7)

    # Title and game date
    ax.text(CANVAS_W / 2, HEADER_TOP - 3.5, 'ADVANCED BOX SCORE', fontsize=31,
            fontweight='bold', color=INK, va='center', ha='center', zorder=4)
    ax.text(CANVAS_W / 2, HEADER_TOP - 7.6, date_text, fontsize=15, color=INK_SOFT,
            va='center', ha='center', zorder=4)

    # Who won the game, or None for a tie
    won = 'tech' if points['tech'] > points['oppo'] else (
        'oppo' if points['oppo'] > points['tech'] else None)
    for side, cx in (('tech', 26.0), ('oppo', 74.0)):
        # Logo sized by height with a width cap so tall or wide logos aren't stretched
        drawLogo(ax, logos[side], cx, HEADER_TOP - 14.0, 9.6, max_width=15.0)
        # Team name in ink, since light team colors are unreadable at this size
        ax.text(cx, HEADER_TOP - 20.4, names[side], fontsize=15, fontweight='bold',
                color=INK, va='center', ha='center', zorder=4)
        # Underline in the team's bar color, sized to the name's length
        rule_w = 3.0 + 0.82 * len(names[side])
        ax.add_patch(Rectangle((cx - rule_w / 2, HEADER_TOP - 22.0), rule_w, 0.55,
                               facecolor=colors[side], edgecolor='none', zorder=4))

    # Scores between the logos: winner in team color, loser in muted ink
    for side, cx in (('tech', 42.0), ('oppo', 58.0)):
        ax.text(cx, HEADER_TOP - 14.0, str(points[side]), fontsize=62, fontweight='bold',
                color=colors[side] if side == won or won is None else INK_MUTED,
                va='center', ha='center', zorder=4)
    ax.text(CANVAS_W / 2, HEADER_TOP - 14.0, '–', fontsize=30, color=INK_MUTED,
            va='center', ha='center', zorder=4)


def buildGraphic(names, points, colors, logos, factors, share, source, date_text):
    # Sets up a borderless square figure with the canvas in data units
    fig, ax = plt.subplots(figsize=(FIG_INCHES, FIG_INCHES))
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_xlim(0, CANVAS_W)
    ax.set_ylim(0, CANVAS_H)
    ax.axis('off')

    drawScoreboard(ax, names, points, colors, logos, date_text)

    # Stack the five factor rows down the left column
    top = BODY_TOP
    for factor in FACTORS:
        drawFactorRow(ax, factor, factors[factor['key']], top, colors, logos)
        top -= ROW_H

    # Right panel runs the full height of the factor column
    won = sum(1 for f in FACTORS if factorWinner(f, factors[f['key']]) == 'tech')
    cx = RIGHT_X + RIGHT_W / 2
    panel(ax, RIGHT_X, BODY_BOTTOM, RIGHT_W, BODY_TOP - BODY_BOTTOM,
          facecolor='white', alpha=0.7)
    ax.text(cx, BODY_TOP - 6.0, 'POSTGAME\nWIN EXPECTANCY', fontsize=16, fontweight='bold',
            color=INK, va='center', ha='center', zorder=4)
    drawDonut(ax, (cx, 47.0), 15.0, share, colors)
    # Source note, blank when the number came from CFBD
    ax.text(cx, 28.0, source, fontsize=11, color=INK_MUTED,
            va='center', ha='center', zorder=4)
    # Count of factors Tech won, spelled out as ALL for a sweep
    if won != 5:
        wonString= f"Tech won\n{won}\nof the five factors"
    else:
        wonString= f"Tech won\nALL\nof the five factors"
    ax.text(cx, 15.5, wonString, fontsize=26,
            fontweight='bold', color=INK, va='center', ha='center', zorder=4)
    return fig


####
# SAVING
####

def saveGraphic(fig, fig_path=FIG_PATH, background_path=BACKGROUND_PATH):
    # Saves the chart with a transparent background, then layers it onto the paper photo
    os.makedirs(os.path.dirname(fig_path) or '.', exist_ok=True)
    fig.savefig(fig_path, bbox_inches='tight', pad_inches=0, dpi=170, transparent=True)
    plt.close(fig)

    # Without the paper photo, keep the transparent chart as is
    if not os.path.isfile(background_path):
        print(f"No background at {background_path}; leaving the chart on its own.")
        return fig_path

    chart = Image.open(fig_path).convert('RGBA')
    background = Image.open(background_path).convert('RGBA')
    # Crop the center square out of the portrait paper photo
    side = min(background.width, background.height)
    background = background.crop(((background.width - side) // 2,
                                  (background.height - side) // 2,
                                  (background.width + side) // 2,
                                  (background.height + side) // 2))
    # Scale the chart to fit inside the paper with an even margin
    margin = 0.94
    scale = min(background.width * margin / chart.width,
                background.height * margin / chart.height)
    chart = chart.resize((round(chart.width * scale), round(chart.height * scale)),
                         Image.LANCZOS)
    # Center the chart on the paper and save as a flat RGB image
    offset = ((background.width - chart.width) // 2, (background.height - chart.height) // 2)
    background.alpha_composite(chart, offset)
    background.convert('RGB').save(fig_path)
    return fig_path


####
# MAIN
####

def fbAdvancedBoxScore(team=TEAM, year=None, week=None, opponent=None, gameId=None,
                       fig_path=FIG_PATH):
    # Find the game and print a header line for it
    game, season = resolveGame(team, year, week, opponent, gameId)
    oppo_name, where, date_text = gameLabel(game, team)
    print(f"{season} week {game.week}: {team} {where} {oppo_name} ({date_text})")

    # Pull the stats and work out win expectancy
    factors, tech_pts, oppo_pts = gameFactors(game, team, season)
    share, source = winExpectancy(game, factors, team)

    # Print a text summary of each factor and who won it
    for factor in FACTORS:
        values = factors[factor['key']]
        winner = factorWinner(factor, values)
        won_by = {'tech': team, 'oppo': oppo_name}.get(winner, 'even')
        print(f"  {factor['name']:<16} {factor['fmt'].format(values['tech']):>9}"
              f"  vs {factor['fmt'].format(values['oppo']):>9}   -> {won_by}")
    print(f"  {'Win expectancy':<16} {share:>9.1%}   ({source})")

    # Gather per-team names, scores, colors and logos for drawing
    names = {'tech': team, 'oppo': oppo_name}
    points = {'tech': tech_pts, 'oppo': oppo_pts}
    colors = {'tech': TECH_COLOR, 'oppo': opponentColor(oppo_name)}
    logos = {'tech': teamLogo(team, LOGO_BOX), 'oppo': teamLogo(oppo_name, LOGO_BOX)}

    # Draw and save the graphic
    fig = buildGraphic(names, points, colors, logos, factors, share, source, date_text)
    path = saveGraphic(fig, fig_path)
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
