# -*- coding: utf-8 -*-
"""
One NFL week's stats for every former Louisiana Tech player, as trading cards.

Alumni are found by scanning today's NFL rosters for ESPN college = Louisiana Tech,
so anyone who has left the league since is missed. Only players with a stat in a
box score get a card.

Cards go to out/fbNFLStats/ (cleared each run), plus one fanned-hand image per
player in out/fbNFLStats/fanned/ with that player's card on top. Action shots are
added by hand to img/fbNFLStats/ (e.g. L_Jarius_Sneed.jpg); without one, the card
uses team colors.

Run from the repo root:

    python fbNFLStats.py                          # most recent week with final games
    python fbNFLStats.py --week 2                 # that week of the current season
    python fbNFLStats.py --year 2025 --week 18
    python fbNFLStats.py --year 2025 --week 1 --postseason
"""

####
# IMPORTS
####

import argparse
import glob
import math
import os
import re

import requests
from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageFilter, ImageFont, ImageOps

from lib.fbCommon import assetSlug

####
# CONSTANTS
####

# ESPN ids and season types
COLLEGE_ID = '2348'               # ESPN's id for Louisiana Tech
NFL_URL = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl'
REGULAR_SEASON = 2
POSTSEASON = 3
SKIPPED_WEEKS = {'Pro Bowl'}

# File locations
PHOTO_DIR = 'img/fbNFLStats'
OUT_DIR = 'out/fbNFLStats'
FAN_DIR = 'out/fbNFLStats/fanned'
PHOTO_EXTENSIONS = ('png', 'jpg', 'jpeg', 'webp')
FONT_PATH = 'lib/font/fontOswald.ttf'
LOGO_PATH = 'img/gtpdd_logo.png'
BACKGROUND_PATH = 'img/fbNFLStats/background.png'

# Card geometry in pixels; 1500x2100 is a 2.5" x 3.5" card at 600 dpi
CARD_W, CARD_H = 1500, 2100
BORDER = 45
MAX_STATS = 3
STATS_TOP, STATS_BOTTOM = 560, 1745  # boxes are centered in this band
PANEL_H = 330
PANEL_GAP = 60
BOX_MIN_W = 430                   # boxes grow left from the card's edge to fit their number
BOX_MAX_W = 930
BOX_STEP = 90                     # each box reaches at least this much further left than the one above
SLANT = 60                        # how far a box's top edge sits right of its bottom edge
NAME_TOP = 1790

# Fanned hand of cards
FAN_CARD_W = 900                  # cards are scaled down to this width in the fan
FAN_CORNER = 28                   # rounded card corners, at fan scale
FAN_STEP = 11                     # degrees between neighboring cards...
FAN_SPREAD = 44                   # ...unless that would open the hand wider than this
FAN_OVERLAP = 0.75                # share of a card hidden by the one in front; higher is tighter
FAN_OUT_H = 1350                  # height of the finished image; width follows the background
FAN_MARGIN = 0.07                 # space kept between the hand and the image edge, as a share of height
FAN_SHADOW = 30                   # blur radius of the drop shadow under each card

WHITE = (255, 255, 255, 255)

# Box score (category, label) -> card label; order is the fallback ranking
STAT_NAMES = {
    ('defensive', 'TOT'): 'TACKLES',
    ('defensive', 'SOLO'): 'SOLO TKL',
    ('defensive', 'SACKS'): 'SACKS',
    ('defensive', 'TFL'): 'TFL',
    ('defensive', 'PD'): 'PASS DEF',
    ('defensive', 'QB HTS'): 'QB HITS',
    ('defensive', 'TD'): 'DEF TD',
    ('interceptions', 'INT'): 'INT',
    ('interceptions', 'YDS'): 'INT YDS',
    ('interceptions', 'TD'): 'PICK SIX',
    ('fumbles', 'REC'): 'FUM REC',
    ('passing', 'YDS'): 'PASS YDS',
    ('passing', 'TD'): 'PASS TD',
    ('passing', 'C/ATT'): 'COMP/ATT',
    ('passing', 'RTG'): 'RATING',
    ('rushing', 'YDS'): 'RUSH YDS',
    ('rushing', 'CAR'): 'CARRIES',
    ('rushing', 'TD'): 'RUSH TD',
    ('rushing', 'AVG'): 'YDS/CAR',
    ('receiving', 'REC'): 'CATCHES',
    ('receiving', 'YDS'): 'REC YDS',
    ('receiving', 'TD'): 'REC TD',
    ('receiving', 'TGTS'): 'TARGETS',
    ('kicking', 'FG'): 'FG',
    ('kicking', 'XP'): 'XP',
    ('kicking', 'PTS'): 'POINTS',
    ('kicking', 'LONG'): 'LONG FG',
    ('punting', 'NO'): 'PUNTS',
    ('punting', 'AVG'): 'PUNT AVG',
    ('punting', 'In 20'): 'INSIDE 20',
    ('punting', 'LONG'): 'LONG PUNT',
    ('kickReturns', 'YDS'): 'KR YDS',
    ('kickReturns', 'TD'): 'KR TD',
    ('puntReturns', 'YDS'): 'PR YDS',
    ('puntReturns', 'TD'): 'PR TD',
}

# Stats that lead the card for each position, ahead of the fallback order
POSITION_STATS = {
    'QB': [('passing', 'YDS'), ('passing', 'TD'), ('passing', 'C/ATT'),
           ('rushing', 'YDS'), ('passing', 'RTG')],
    'RB': [('rushing', 'YDS'), ('rushing', 'CAR'), ('rushing', 'TD'),
           ('receiving', 'YDS'), ('receiving', 'REC')],
    'FB': [('rushing', 'YDS'), ('receiving', 'YDS'), ('rushing', 'CAR')],
    'WR': [('receiving', 'REC'), ('receiving', 'YDS'), ('receiving', 'TD'),
           ('rushing', 'YDS'), ('receiving', 'TGTS')],
    'TE': [('receiving', 'REC'), ('receiving', 'YDS'), ('receiving', 'TD'),
           ('receiving', 'TGTS')],
    'PK': [('kicking', 'FG'), ('kicking', 'XP'), ('kicking', 'PTS'), ('kicking', 'LONG')],
    'K': [('kicking', 'FG'), ('kicking', 'XP'), ('kicking', 'PTS'), ('kicking', 'LONG')],
    'P': [('punting', 'NO'), ('punting', 'AVG'), ('punting', 'In 20'), ('punting', 'LONG')],
}

# Big plays that jump to the top of any card
HEADLINE_STATS = [('interceptions', 'INT'), ('interceptions', 'TD'), ('defensive', 'TD'),
                  ('defensive', 'SACKS'), ('fumbles', 'REC'), ('kickReturns', 'TD'),
                  ('puntReturns', 'TD')]

# One HTTP session reused for every ESPN request
session = requests.Session()


####
# ESPN DATA
####

def getJson(url, params=None):
    # GETs an ESPN endpoint and returns the parsed JSON
    r = session.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def getCollegeAlumni(college_id=COLLEGE_ID):
    # Returns athlete id -> player info for everyone on an NFL roster from that college
    alumni = {}
    # Walk every NFL team's roster
    for league in getJson(NFL_URL + '/teams')['sports'][0]['leagues']:
        for entry in league['teams']:
            team = entry['team']
            roster = getJson(NFL_URL + '/teams/' + team['id'] + '/roster')
            for group in roster['athletes']:
                for athlete in group['items']:
                    if (athlete.get('college') or {}).get('id') == college_id:
                        alumni[athlete['id']] = {
                            'name': athlete['displayName'],
                            'position': athlete.get('position', {}).get('abbreviation', ''),
                            'jersey': athlete.get('jersey', ''),
                            'team': team['abbreviation'],
                            'teamName': team['name'],
                            'color': '#' + team.get('color', '333333'),
                        }
    return alumni


def getWeekGames(year, season_type, week):
    # Returns the scoreboard's games for one week
    scoreboard = getJson(NFL_URL + '/scoreboard', {'dates': year,
                                                   'seasontype': season_type,
                                                   'week': week})
    return scoreboard['events']


def seasonWeeks(scoreboard):
    # Returns regular season and postseason weeks in order, as (season type, week, label)
    weeks = []
    for period in scoreboard['leagues'][0]['calendar']:
        if int(period['value']) in (REGULAR_SEASON, POSTSEASON):
            for entry in period['entries']:
                if entry['label'] not in SKIPPED_WEEKS:
                    weeks.append((int(period['value']), int(entry['value']), entry['label']))
    return weeks


def findLatestWeek():
    # Returns (year, season type, week, label) for the latest week with a final game
    current = getJson(NFL_URL + '/scoreboard')
    year = current['season']['year']
    here = (current['season']['type'], current['week']['number'])
    # The current week may not have kicked off, so walk backward, into last season if needed
    for _ in range(2):
        weeks = seasonWeeks(getJson(NFL_URL + '/scoreboard', {'dates': year}))
        if here[0] in (REGULAR_SEASON, POSTSEASON):
            weeks = weeks[:[w[:2] for w in weeks].index(here) + 1]
        elif here[0] is not None and here[0] < REGULAR_SEASON:
            weeks = []                        # preseason: nothing to report this year
        for season_type, week, label in reversed(weeks):
            events = getWeekGames(year, season_type, week)
            if any(e['status']['type']['state'] == 'post' for e in events):
                return year, season_type, week, label
        year, here = year - 1, (None, None)
    raise RuntimeError('No completed NFL games found this season or last')


def getPlayerStats(game_id, athlete_ids):
    # Returns {athlete id: [(category, {label: value})]} for the given players in one game
    summary = getJson(NFL_URL + '/summary', {'event': game_id})
    found = {}
    for team in summary['boxscore'].get('players', []):
        for category in team['statistics']:
            for line in category['athletes']:
                athlete_id = line['athlete']['id']
                if athlete_id in athlete_ids:
                    stats = dict(zip(category['labels'], line['stats']))
                    found.setdefault(athlete_id, []).append((category['name'], stats))
    return found


def gameResult(event, team_abbrev):
    # Returns e.g. ('vs', 'DEN', 'W 31-10') from this team's side of the game
    competition = event['competitions'][0]
    teams = {c['team']['abbreviation']: c for c in competition['competitors']}
    us = teams.get(team_abbrev)
    them = next((c for abbrev, c in teams.items() if abbrev != team_abbrev), None)
    # Fall back to ESPN's short name if the team can't be found
    if us is None or them is None:
        return '', event['shortName'], ''
    where = 'vs' if us['homeAway'] == 'home' else '@'
    result = 'W' if us.get('winner') else ('L' if them.get('winner') else 'T')
    return where, them['team']['abbreviation'], '%s %s-%s' % (result, us.get('score', ''),
                                                             them.get('score', ''))


####
# PICKING STATS
####

def isZero(value):
    # True if every number in a stat string is zero (e.g. '0/0' or '0.0')
    numbers = re.findall(r'\d+(?:\.\d+)?', str(value))
    return not numbers or all(float(n) == 0 for n in numbers)


def cardStats(position, categories, limit=MAX_STATS):
    # Returns the (value, card label) pairs worth showing, best first, zeros left off
    lines = {(category, label): value
             for category, stats in categories for label, value in stats.items()}
    # Headline plays first, then position stats, then the fallback order
    order = HEADLINE_STATS + POSITION_STATS.get(position, []) + list(STAT_NAMES)
    picked = []
    for key in order:
        if key in lines and key in STAT_NAMES and not isZero(lines[key]):
            if all(key != k for k, _, _ in picked):
                picked.append((key, lines[key], STAT_NAMES[key]))
    return [(value, name) for _, value, name in picked[:limit]]


####
# DRAWING
####

def font(size):
    # The card font at a given size
    return ImageFont.truetype(FONT_PATH, size)


def fitFont(text, max_w, max_h, start, stroke=0):
    # Shrinks the font from start until text fits in max_w x max_h
    size = start
    while size > 10:
        left, top, right, bottom = font(size).getbbox(text, stroke_width=stroke)
        if right - left <= max_w and bottom - top <= max_h:
            break
        size -= 4
    return font(size)


def shade(hex_color, factor):
    # Scales a color toward black (factor < 1) or white (factor > 1)
    r, g, b = ImageColor.getrgb(hex_color)[:3]
    if factor <= 1:
        return tuple(int(c * factor) for c in (r, g, b)) + (255,)
    return tuple(int(c + (255 - c) * (factor - 1)) for c in (r, g, b)) + (255,)


def teamDark(hex_color):
    # Darkens a team color enough for white numbers to read on it
    r, g, b = ImageColor.getrgb(hex_color)[:3]
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return shade(hex_color, min(0.6, 0.14 / max(luminance, 0.01)))


def textLayer(text, fnt, fill, stroke=0, stroke_fill=None, shadow=None, tracking=0):
    # Renders text on its own tightly cropped transparent layer, with optional shadow and letter spacing
    pad = stroke + 40 + (abs(shadow[0]) + abs(shadow[1]) if shadow else 0)
    # With tracking, each character is drawn separately with extra space after it
    widths = [fnt.getlength(ch) + tracking for ch in text] if tracking else [fnt.getlength(text)]
    bottom = fnt.getbbox(text, stroke_width=stroke)[3]
    w, h = int(sum(widths) + 2 * pad), int(bottom + 2 * pad)
    layer = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    def put(offset, color, outline):
        # Draws the text once at an offset
        x = pad + offset[0]
        chunks = list(text) if tracking else [text]
        for chunk, width in zip(chunks, widths):
            draw.text((x, pad + offset[1]), chunk, font=fnt, fill=color,
                      stroke_width=stroke, stroke_fill=outline)
            x += width

    # Shadow first, then the text on top
    if shadow:
        put(shadow[:2], shadow[2], shadow[2])
    put((0, 0), fill, stroke_fill or fill)
    return layer.crop(layer.getbbox())


def italic(layer, lean=0.2):
    # Shears a layer so its top leans right, like the reference card's type
    w, h = layer.size
    shift = int(lean * h)
    wide = Image.new('RGBA', (w + shift, h), (0, 0, 0, 0))
    wide.paste(layer, (0, 0))
    return wide.transform(wide.size, Image.AFFINE, (1, lean, -shift, 0, 1, 0),
                          resample=Image.BICUBIC)


def pasteAt(card, layer, x, y, anchor='la'):
    # Pastes a layer by its left/right/middle x and top/bottom/middle y
    w, h = layer.size
    x = {'l': x, 'r': x - w, 'm': x - w // 2}[anchor[0]]
    y = {'a': y, 'b': y - h, 'm': y - h // 2}[anchor[1]]
    card.alpha_composite(layer, (int(x), int(y)))


def findPhoto(slug):
    # Returns the player's action shot path in any supported format, or None
    for ext in PHOTO_EXTENSIONS:
        for path in glob.glob(os.path.join(PHOTO_DIR, slug + '.' + ext)):
            return path
    return None


def drawBackground(card, player, photo_path):
    # Fills the card inside the border with the action shot or a team-color stand-in
    inner = (CARD_W - 2 * BORDER, CARD_H - 2 * BORDER)
    if photo_path:
        photo = ImageOps.exif_transpose(Image.open(photo_path)).convert('RGBA')
        photo = ImageOps.fit(photo, inner, method=Image.LANCZOS, centering=(0.4, 0.3))
    else:
        # No action shot yet: team-color gradient with a giant faded jersey number
        top, bottom = shade(player['color'], 0.8), shade(player['color'], 0.18)
        photo = Image.new('RGBA', inner)
        draw = ImageDraw.Draw(photo)
        for y in range(inner[1]):
            t = y / inner[1]
            draw.line([(0, y), (inner[0], y)],
                      fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
        number = textLayer(player['jersey'] or '#', font(1100), (255, 255, 255, 38))
        pasteAt(photo, italic(number), inner[0] * 0.3, inner[1] * 0.55, 'mm')

    # Darken the right side and the top so the boxes and title read over any photo
    ramp = Image.linear_gradient('L').rotate(90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
    right_side = ramp.point(lambda v: int(170 * max(0, (v / 255 - 0.35) / 0.65)))
    top = Image.linear_gradient('L').point(lambda v: int(140 * max(0, 1 - v / 255 / 0.3)))
    shadow = ImageChops.lighter(right_side.resize(inner), top.resize(inner))
    photo = Image.composite(Image.new('RGBA', inner, (0, 0, 0, 255)), photo, shadow)
    card.alpha_composite(photo, (BORDER, BORDER))


def drawTitle(card, label):
    # Draws the week ('WEEK 1', 'WILD CARD') fit to the width, with 'STATS' beneath it
    text = label.upper()
    max_w = CARD_W - 2 * BORDER - 120
    big = fitFont(text, max_w - 60, 260, 300, stroke=8)
    title = italic(textLayer(text, big, (58, 58, 64, 255), stroke=8, stroke_fill=WHITE,
                             shadow=(12, 12, (0, 0, 0, 150))))
    # Shrink the title further if the italic lean pushed it past the width
    if title.width > max_w:
        title = title.resize((max_w, int(title.height * max_w / title.width)), Image.LANCZOS)
    pasteAt(card, title, CARD_W // 2, 95, 'ma')

    stats = italic(textLayer('STATS', font(120), WHITE, stroke=2, tracking=40,
                             shadow=(5, 5, (0, 0, 0, 140))), lean=0.12)
    pasteAt(card, stats, CARD_W - BORDER - 70, 95 + title.height - 10, 'ra')


def statLayers(value, name):
    # Returns the rotated stat name and the big number, sized as large as the widest box allows
    name_layer = textLayer(name, fitFont(name, PANEL_H - 50, 60, 56, stroke=1), WHITE,
                           stroke=1).rotate(-90, expand=True)
    room = BOX_MAX_W - SLANT - 40 - 30 - name_layer.width - 40
    number = textLayer(value, fitFont(value, room, PANEL_H - 90, 260, stroke=4), WHITE,
                       stroke=4, shadow=(10, 10, (0, 0, 0, 170)))
    return name_layer, number


def boxWidth(name_layer, number):
    # Slant, padding, the number, a gap, the stat name, padding
    return SLANT + 40 + number.width + 30 + name_layer.width + 40


def drawStatBox(card, top, left, name_layer, number, fill):
    # Draws one slanted stat box from left to the card's right edge
    right, bottom = CARD_W - BORDER, top + PANEL_H
    draw = ImageDraw.Draw(card)

    # Two thin stripes chasing the box's slanted left edge
    for gap, width in ((34, 10), (62, 6)):
        draw.polygon([(left + SLANT - gap, top), (left + SLANT - gap + width, top),
                      (left - gap + width, bottom), (left - gap, bottom)], fill=WHITE)

    # White outline, then the team-color box inset inside it
    outline = [(left + SLANT, top), (right, top), (right, bottom), (left, bottom)]
    draw.polygon(outline, fill=WHITE)
    inset = [(left + SLANT + 9, top + 9), (right - 9, top + 9), (right - 9, bottom - 9),
             (left + 9 + 9 * SLANT // PANEL_H, bottom - 9)]
    box = Image.new('RGBA', card.size, (0, 0, 0, 0))
    box_draw = ImageDraw.Draw(box)
    box_draw.polygon(inset, fill=fill)
    # Mesh texture, like the jersey fabric on the reference card
    dot = shade('#%02x%02x%02x' % fill[:3], 0.7)
    for y in range(top + 20, bottom - 12, 16):
        for x in range(left + ((y // 16) % 2) * 8, right, 16):
            box_draw.ellipse([x, y, x + 5, y + 5], fill=dot)
    # Clip the textured box to the inset shape
    mask = Image.new('L', card.size, 0)
    ImageDraw.Draw(mask).polygon(inset, fill=255)
    card.paste(box, (0, 0), Image.composite(box, Image.new('RGBA', card.size), mask))

    # Stat name runs down the right edge, the number sits just inside it
    pasteAt(card, name_layer, right - 40, top + PANEL_H // 2, 'rm')
    pasteAt(card, number, right - 40 - name_layer.width - 30, top + PANEL_H // 2 + 8, 'rm')


def drawNamePlate(card, player, game, fill):
    # Draws the bottom strip: player name and game line on the left, gtpdd logo on the right
    draw = ImageDraw.Draw(card)
    split, bottom, right = 960, CARD_H - BORDER, CARD_W - BORDER

    # Name plate in team color on the left, logo on white on the right
    draw.polygon([(split + 110, NAME_TOP + 25), (right, NAME_TOP + 25), (right, bottom),
                  (split + 20, bottom)], fill=WHITE)
    draw.polygon([(BORDER, NAME_TOP), (split + 90, NAME_TOP), (split, bottom), (BORDER, bottom)],
                 fill=fill)
    draw.rectangle([BORDER, NAME_TOP, split + 90, NAME_TOP + 10], fill=WHITE)
    for gap, width in ((30, 10), (52, 6)):
        draw.polygon([(split + 90 + gap, NAME_TOP + 25), (split + 90 + gap + width, NAME_TOP + 25),
                      (split + gap + width, bottom), (split + gap, bottom)], fill=fill)

    # Player name, sized to fit the plate
    text_w = split - BORDER - 90
    name_text = player['name'].upper()
    name = textLayer(name_text, fitFont(name_text, text_w, 105, 120, stroke=3),
                     WHITE, stroke=3, shadow=(5, 5, (0, 0, 0, 150)))
    pasteAt(card, name, BORDER + 45, NAME_TOP + 50)

    # Team, position and game result along the bottom
    where, opponent, result = game
    details = '%s  •  %s  •  %s %s %s' % (player['teamName'].upper(), player['position'],
                                                result, where, opponent)
    line = italic(textLayer(details, fitFont(details, text_w - 40, 60, 58, stroke=1),
                            WHITE, stroke=1), lean=0.18)
    pasteAt(card, line, BORDER + 45, bottom - 45, 'lb')

    # gtpdd logo centered in the white panel
    logo = Image.open(LOGO_PATH).convert('RGBA')
    logo.thumbnail((right - split - 200, bottom - NAME_TOP - 90), Image.LANCZOS)
    pasteAt(card, logo, (split + 150 + right) // 2, (NAME_TOP + 25 + bottom) // 2, 'mm')


def drawCard(player, stats, game, label, path):
    # Draws and saves one player's card, returning it as an RGB image
    card = Image.new('RGBA', (CARD_W, CARD_H), WHITE)
    fill = teamDark(player['color'])
    drawBackground(card, player, findPhoto(assetSlug(player['name'])))
    drawTitle(card, label)
    # Center the stack of stat boxes in the stats band
    stack = len(stats) * PANEL_H + (len(stats) - 1) * PANEL_GAP
    first = STATS_TOP + (STATS_BOTTOM - STATS_TOP - stack) // 2
    width = 0
    # Each box fits its number but is never narrower than the one above plus BOX_STEP
    for i, (value, name) in enumerate(stats):
        name_layer, number = statLayers(value, name)
        width = min(BOX_MAX_W, max(BOX_MIN_W, boxWidth(name_layer, number),
                                   width + BOX_STEP if i else 0))
        drawStatBox(card, first + i * (PANEL_H + PANEL_GAP), CARD_W - BORDER - width,
                    name_layer, number, fill)
    drawNamePlate(card, player, game, fill)

    # Thin rule inside the white border, as on a printed card
    ImageDraw.Draw(card).rectangle([BORDER, BORDER, CARD_W - BORDER, CARD_H - BORDER],
                                   outline=(210, 210, 210, 255), width=3)
    card = card.convert('RGB')
    card.save(path)
    return card


####
# FANNED HAND
####

def fanCard(card):
    # Scales a card down for the fan, rounds its corners, and adds a soft shadow
    h = round(card.height * FAN_CARD_W / card.width)
    face = card.convert('RGBA').resize((FAN_CARD_W, h), Image.LANCZOS)
    corners = Image.new('L', face.size, 0)
    ImageDraw.Draw(corners).rounded_rectangle([0, 0, FAN_CARD_W - 1, h - 1], FAN_CORNER, fill=255)
    face.putalpha(corners)

    # Blurred, offset copy of the card shape as the shadow, with the card on top
    pad = FAN_SHADOW * 3
    tile = Image.new('RGBA', (FAN_CARD_W + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    shadow = Image.new('L', tile.size, 0)
    shadow.paste(corners.point(lambda v: v * 110 // 255), (pad + 8, pad + 16))
    tile.putalpha(shadow.filter(ImageFilter.GaussianBlur(FAN_SHADOW)))
    tile.alpha_composite(face, (pad, pad))
    return tile


def fanSlots(n):
    # Returns each card's angle in degrees, top card upright and each one behind leaning further left
    step = min(FAN_STEP, FAN_SPREAD / (n - 1)) if n > 1 else 0
    return [-i * step for i in range(n)]


def drawFan(cards, featured):
    # Fans all cards out to the left with cards[featured] on top; the rest follow in order behind it
    n = len(cards)
    order = cards[featured:] + cards[:featured]

    placed = []
    # Cards ride an arc around a pivot below the hand, spaced by FAN_OVERLAP
    slots = fanSlots(n)
    spacing = (1 - FAN_OVERLAP) * FAN_CARD_W
    radius = spacing / math.sin(math.radians(abs(slots[1]))) if n > 1 else 0
    for tile, angle in zip(map(fanCard, order), slots):
        rotated = tile.rotate(-angle, resample=Image.BICUBIC, expand=True)
        rad = math.radians(angle)
        cx = radius * math.sin(rad)
        cy = -radius * math.cos(rad)
        placed.append((rotated, cx - rotated.width / 2, cy - rotated.height / 2))

    # Size the canvas to the bounding box of every placed card
    left = min(x for _, x, _ in placed)
    top = min(y for _, _, y in placed)
    width = max(x + im.width for im, x, _ in placed) - left
    height = max(y + im.height for im, _, y in placed) - top
    hand = Image.new('RGBA', (math.ceil(width), math.ceil(height)), (0, 0, 0, 0))

    # Bottom of the hand first, so each card lands on top of the one behind it
    for im, x, y in reversed(placed):
        hand.alpha_composite(im, (round(x - left), round(y - top)))
    return hand


def onBackground(hand, background_path=BACKGROUND_PATH):
    # Centers the hand on the background, scaled to fit inside the margin
    background = Image.open(background_path).convert('RGBA')
    width = round(background.width * FAN_OUT_H / background.height)
    image = background.resize((width, FAN_OUT_H), Image.LANCZOS)

    margin = round(FAN_OUT_H * FAN_MARGIN)
    scale = min((width - 2 * margin) / hand.width, (FAN_OUT_H - 2 * margin) / hand.height)
    hand = hand.resize((round(hand.width * scale), round(hand.height * scale)), Image.LANCZOS)
    image.alpha_composite(hand, ((width - hand.width) // 2, (FAN_OUT_H - hand.height) // 2))
    return image.convert('RGB')


####
# MAIN
####

def clearCards(dirs=(OUT_DIR, FAN_DIR)):
    # Deletes last run's cards so players without stats this week don't linger
    for out_dir in dirs:
        os.makedirs(out_dir, exist_ok=True)
        for path in glob.glob(os.path.join(out_dir, '*.png')):
            os.remove(path)


def main():
    # Description comes from the first line of the module docstring
    arg_parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    arg_parser.add_argument('--year', type=int,
                            help='season year (default: the current season)')
    arg_parser.add_argument('--week', type=int,
                            help='week number (default: the most recent week with final games)')
    arg_parser.add_argument('--postseason', action='store_true',
                            help='treat --week as a playoff round (1 = Wild Card)')
    args = arg_parser.parse_args()

    # Pick the week: latest completed by default, otherwise the one requested
    if args.week is None:
        year, season_type, week, label = findLatestWeek()
    else:
        year = args.year or getJson(NFL_URL + '/scoreboard')['season']['year']
        season_type = POSTSEASON if args.postseason else REGULAR_SEASON
        week = args.week
        label = ('Postseason Week %d' if args.postseason else 'Week %d') % week
    print('%d %s\n' % (year, label))

    print('Finding former Louisiana Tech players on NFL rosters...')
    alumni = getCollegeAlumni()
    print('Found %d: %s\n' % (len(alumni), ', '.join(sorted(a['name'] for a in alumni.values()))))

    games = getWeekGames(year, season_type, week)
    clearCards()
    played, missing_photos, cards = set(), [], []
    # Make a card for every alum with a stat in a finished game
    for event in games:
        if event['status']['type']['state'] != 'post':
            print('Skipping %s (%s)' % (event['shortName'],
                                        event['status']['type']['description']))
            continue
        for athlete_id, categories in getPlayerStats(event['id'], alumni).items():
            player = alumni[athlete_id]
            game = gameResult(event, player['team'])
            played.add(athlete_id)
            # Print the player's raw box score lines
            print('%s, %s, %s (%s)' % (player['name'], player['position'], player['team'],
                                       ' '.join(game)))
            for category, stats in categories:
                line = ', '.join('%s %s' % (stat, value) for stat, value in stats.items())
                print('    %-14s %s' % (category, line))

            slug = assetSlug(player['name'])
            path = os.path.join(OUT_DIR, slug + '.png')
            cards.append((slug, drawCard(player, cardStats(player['position'], categories),
                                         game, label, path)))
            print('    card -> %s' % path)
            if not findPhoto(slug):
                missing_photos.append(os.path.join(PHOTO_DIR, slug + '.jpg'))
            print()

    # One fanned-hand image per player, with that player's card on top
    for i, (slug, _) in enumerate(cards):
        path = os.path.join(FAN_DIR, slug + '.png')
        onBackground(drawFan([card for _, card in cards], i)).save(path)
        print('fanned, %s on top -> %s' % (slug, path))

    # Report alumni with no stats and cards still needing a photo
    quiet = sorted(alumni[a]['name'] for a in alumni if a not in played)
    if quiet:
        print('No stats in %d %s: %s' % (year, label, ', '.join(quiet)))
    if missing_photos:
        print('\nNo action shot yet (png/jpg/webp all work), used team colors instead:')
        for path in missing_photos:
            print('    ' + path)


####
# COMMAND LINE
####

if __name__ == '__main__':
    main()
