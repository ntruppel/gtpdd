# -*- coding: utf-8 -*-
"""
Pixel-art helpers for the 16-bit, Genesis-era menu-screen graphics.

Everything is drawn at console resolution with smoothing off, then blown up with
nearest neighbor so each pixel stays a hard square. Paths are repo-relative, so run
scripts from the repo root.
"""

####
# IMPORTS
####

import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from lib.fbCommon import downloadLogo, trimmedLogo

####
# CONSTANTS
####

FONT_PATH = 'lib/font/fontPressStart2P.ttf'

# Drawn at a console-like resolution, then blown up with hard pixel edges
W, H = 360, 360
SCALE = 3

# Menu palette, picked to match the old Sega Genesis screens
NAVY = (16, 20, 72)
NAVY_LIGHT = (48, 56, 136)
HILITE_TOP = (40, 48, 200)
HILITE_BOTTOM = (20, 24, 150)
HILITE_EDGE = (120, 128, 248)
SILVER_TOP = (236, 236, 240)
SILVER_BOTTOM = (164, 164, 176)
SILVER_EDGE = (104, 104, 120)
STRIPE_TOP = (72, 96, 232)
STRIPE_BOTTOM = (16, 24, 120)
MENU_BLUE = (28, 36, 196)
MENU_SUB = (92, 96, 132)
BACKDROP = (36, 36, 44)
BACKDROP_ALPHA = 200
WHITE = (248, 248, 248)
GRAY = (150, 150, 160)
GOLD = (248, 208, 48)
BLACK = (8, 8, 8)
LCD_BEZEL = (120, 120, 128)

# Two team colors closer than this (OKLab x100) look the same; the fallback stands in for a clash
MIN_COLOR_DISTANCE = 15
FALLBACK_COLOR = (235, 104, 52)

# Crowd colors: neutral shirts mixed in with team colors, plus skin and empty seats
NEUTRAL_SHIRTS = [(232, 232, 232), (112, 112, 120), (44, 44, 52), (176, 160, 128)]
HOME_SHARE = 0.85                  # share of home-section fans in home colors
ROAD_SHARE = 0.85                  # share of road-section fans in road colors
PRIMARY_SHARE = 0.70               # share of team-colored shirts in the primary color
ROAD_SECTION = {2: 38, 3: 60}      # crowd row -> how far right the road fans reach, bottom left
SKIN = [(244, 200, 160), (216, 160, 112), (168, 112, 72), (112, 72, 48)]
SEAT = (56, 56, 72)
STANDS = (24, 24, 40)
CROWD_H = 34
WALL_H = 6
FIELD_TOP = CROWD_H + WALL_H       # where the court or field starts

# Shared layout: scoreboard up top, factor table in the middle, dialog boxes along the bottom
MARGIN = 12
PANEL_X, PANEL_W = MARGIN, W - 2 * MARGIN
HEADER_Y = 48
TITLE_H, MATCHUP_H, SCORE_H = 14, 12, 50
TABLE_Y = 136
TABLE_HEAD_H = 28
STRIPE_W = 4
LABEL_W = 100
TEAM_W = (PANEL_W - LABEL_W) // 2
DIALOG_Y, DIALOG_H = 294, 54
MAX_ICONS = 5                      # most sprites a rating meter shows


####
# PIXEL HELPERS
####

def newScreen():
    # Blank screen and a drawing context with text smoothing turned off
    img = Image.new('RGBA', (W, H), BLACK + (255,))
    draw = ImageDraw.Draw(img)
    draw.fontmode = '1'
    return img, draw


def font(size=8):
    # Press Start 2P only stays crisp at multiples of 8px
    return ImageFont.truetype(FONT_PATH, size)


def rect(draw, x, y, w, h, color):
    # Filled rectangle by position and size, since PIL's corners are inclusive
    if w > 0 and h > 0:
        draw.rectangle((x, y, x + w - 1, y + h - 1), fill=color)


def lerp(a, b, t):
    # Blends two RGB colors
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient(draw, x, y, w, h, top, bottom, band=2):
    # Vertical gradient in 2px bands, like the limited palettes of the era
    for i in range(h):
        t = (i // band * band) / max(h - 1, 1)
        draw.line((x, y + i, x + w - 1, y + i), fill=lerp(top, bottom, t))


def shade(img, x, y, w, h, color=BACKDROP, alpha=BACKDROP_ALPHA):
    # Lays a see-through color over part of the image so the background shows through
    region = img.crop((x, y, x + w, y + h))
    region = Image.alpha_composite(region, Image.new('RGBA', (w, h), color + (alpha,)))
    img.paste(region, (x, y))


def text(draw, x, y, s, color, size=8, shadow=None, outline=None):
    # Draws unsmoothed text, with an optional 1px drop shadow and/or 1px outline all around
    f = font(size)
    if shadow:
        draw.text((x + 1, y + 1), s, font=f, fill=shadow, anchor='lt')
    if outline:
        for dx, dy in ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)):
            draw.text((x + dx, y + dy), s, font=f, fill=outline, anchor='lt')
    draw.text((x, y), s, font=f, fill=color, anchor='lt')


def centerText(draw, cx, y, s, color, size=8, shadow=None):
    # Centers text on cx, snapped to whole pixels so glyphs don't smear
    width = draw.textlength(s, font=font(size))
    text(draw, round(cx - width / 2), y, s, color, size, shadow)


def hexColors(*values):
    # ESPN hex strings like '003087' as RGB, skipping any that are missing; gray if none are left
    colors = []
    for value in values:
        h = str(value or '').lstrip('#')
        if len(h) == 6:
            colors.append(tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)))
    return colors or [GRAY]


def oklab(rgb):
    # Converts RGB to OKLab, where distance matches how different colors look
    r, g, b = [c / 255 for c in rgb]
    # Undo sRGB gamma to get linear light
    r, g, b = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    # Linear RGB to LMS cone response, then to OKLab
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def colorDistance(a, b):
    # Perceptual distance between two RGB colors, scaled x100
    return sum((p - q) ** 2 for p, q in zip(oklab(a), oklab(b))) ** 0.5 * 100


def distinctColor(colors, avoid):
    # A team's first color that doesn't look like avoid, else the fallback
    for color in colors:
        if colorDistance(color, avoid) >= MIN_COLOR_DISTANCE:
            return color
    return FALLBACK_COLOR


####
# SPRITES
####

def drawSprite(draw, sprite, x, y, cols=None):
    # Draws a sprite of {'rows': [...], 'colors': {...}}; '.' is see-through, cols trims the right side
    for row, line in enumerate(sprite['rows']):
        for col, ch in enumerate(line[:cols]):
            if ch != '.':
                draw.point((x + col, y + row), fill=sprite['colors'][ch])


def drawMeter(draw, sprite, x, y, rating):
    # A row of whole sprites plus a half sprite for any .5
    whole = int(rating)
    for i in range(min(whole, MAX_ICONS)):
        drawSprite(draw, sprite, x + i * sprite['step'], y)
    if rating - whole >= 0.5 and whole < MAX_ICONS:
        drawSprite(draw, sprite, x + whole * sprite['step'], y, cols=sprite['half'])


####
# BACKGROUND
####

def drawCrowd(draw, rng, homeColors, roadColors):
    # Rows of pixel fans in the stands, offset row to row like stadium seating
    rect(draw, 0, 0, W, CROWD_H, STANDS)
    for row, y in enumerate(range(1, CROWD_H - 7, 8)):
        offset = 3 if row % 2 else 0
        for x in range(-offset, W, 7):
            # Roughly one seat in eight sits empty
            if rng.random() < 0.12:
                rect(draw, x + 1, y + 3, 5, 4, SEAT)
                continue
            # Road fans are bunched in the bottom left corner; everyone else roots for the home team
            if x < ROAD_SECTION.get(row, -W):
                colors, share = roadColors, ROAD_SHARE
            else:
                colors, share = homeColors, HOME_SHARE
            if rng.random() >= share:
                shirt = rng.choice(NEUTRAL_SHIRTS)
            # Team colors lean heavily on the primary
            elif len(colors) == 1 or rng.random() < PRIMARY_SHARE:
                shirt = colors[0]
            else:
                shirt = rng.choice(colors[1:])
            # Head over a shirt
            rect(draw, x + 2, y, 3, 3, rng.choice(SKIN))
            rect(draw, x + 1, y + 3, 5, 4, shirt)
    # Padded wall in front of the stands
    rect(draw, 0, CROWD_H, W, WALL_H, (40, 44, 88))
    rect(draw, 0, CROWD_H, W, 1, (96, 104, 168))
    rect(draw, 0, CROWD_H + WALL_H - 1, W, 1, BLACK)


####
# LOGOS
####

def pixelLogo(path, url, name, box):
    # Team logo shrunk to box pixels, with hard edges, a cut-down palette and a white outline
    # Download into the shared logo cache on first use
    if not os.path.isfile(path):
        if not url or not downloadLogo(url, path, name):
            return None
    img = trimmedLogo(path)
    if img is None:
        return None
    img.thumbnail((box - 2, box - 2), Image.LANCZOS)

    # Snap alpha to on/off and limit the colors so it reads as a sprite
    alpha = img.split()[3].point(lambda a: 255 if a >= 128 else 0)
    rgb = img.convert('RGB').quantize(colors=24, method=Image.Quantize.MEDIANCUT).convert('RGB')
    sprite = rgb.convert('RGBA')
    sprite.putalpha(alpha)

    # Grow the silhouette by a pixel and fill it white for the outline
    out = Image.new('RGBA', (sprite.width + 2, sprite.height + 2), (0, 0, 0, 0))
    mask = Image.new('L', out.size, 0)
    mask.paste(alpha, (1, 1))
    mask = mask.filter(ImageFilter.MaxFilter(3))
    out.paste(Image.new('RGBA', out.size, WHITE + (255,)), (0, 0), mask)
    out.alpha_composite(sprite, (1, 1))
    return out


def pasteLogo(img, logo, cx, cy):
    # Centers a logo on (cx, cy)
    if logo is not None:
        img.alpha_composite(logo, (round(cx - logo.width / 2), round(cy - logo.height / 2)))


####
# PANELS
####

def drawScoreboard(img, draw, teams, order, neutral, when, status, logos,
                   title='ADVANCED BOX SCORE'):
    # Title bar, matchup bar, then each logo and score around a scoreboard clock
    y = HEADER_Y
    gradient(draw, PANEL_X, y, PANEL_W, TITLE_H, NAVY_LIGHT, NAVY)
    centerText(draw, W / 2, y + 3, title, WHITE, shadow=BLACK)

    # Matchup as 'road at home' in menu blue on a silver bar; short names if the full ones don't fit
    y += TITLE_H
    left, right = order
    joiner = 'vs' if neutral else 'at'
    gradient(draw, PANEL_X, y, PANEL_W, MATCHUP_H, SILVER_TOP, SILVER_BOTTOM)
    matchup = f"{teams[left]['name']} {joiner} {teams[right]['name']}"
    if draw.textlength(matchup, font=font()) > PANEL_W - 8:
        matchup = f"{teams[left]['short']} {joiner} {teams[right]['short']}"
    centerText(draw, W / 2, y + 2, matchup, MENU_BLUE)

    # Logos and scores over a dark see-through backdrop
    y += MATCHUP_H
    shade(img, PANEL_X, y, PANEL_W, SCORE_H)
    mid = y + SCORE_H // 2
    best = max(teams[left]['points'], teams[right]['points'])
    for side, logoX, scoreX in ((left, 48, 112), (right, W - 48, W - 112)):
        pasteLogo(img, logos[side], logoX, mid)
        # Winner's score in white, loser's grayed out
        centerText(draw, scoreX, mid - 12, str(teams[side]['points']),
                   WHITE if teams[side]['points'] >= best else GRAY, size=24, shadow=BLACK)

    # Scoreboard clock showing the final and the date
    clockW, clockH = 76, 32
    cx = W // 2 - clockW // 2
    rect(draw, cx - 2, mid - clockH // 2 - 2, clockW + 4, clockH + 4, LCD_BEZEL)
    rect(draw, cx - 1, mid - clockH // 2 - 1, clockW + 2, clockH + 2, WHITE)
    rect(draw, cx, mid - clockH // 2, clockW, clockH, BLACK)
    centerText(draw, W / 2, mid - 11, status, GOLD)
    centerText(draw, W / 2, mid + 3, when.strftime('%m/%d/%y'), WHITE)


def drawLabel(draw, y, rowH, name, sub):
    # Silver menu button with the factor name and its stat underneath
    x = PANEL_X + STRIPE_W
    gradient(draw, x, y, LABEL_W - STRIPE_W, rowH, SILVER_TOP, SILVER_BOTTOM)
    rect(draw, x, y, LABEL_W - STRIPE_W, 1, WHITE)
    rect(draw, x, y + rowH - 1, LABEL_W - STRIPE_W, 1, SILVER_EDGE)
    # Name and stat are 18px tall together, centered in the row
    top = y + (rowH - 18) // 2
    text(draw, x + 5, top, name, MENU_BLUE)
    text(draw, x + 5, top + 10, sub, MENU_SUB)


def drawCell(draw, x, y, rowH, cell, sprite, color=None):
    # One team's value and meter, on a highlight bar if it won the row
    if cell['won']:
        # Menu blue by default, or a bar shaded from the team's color
        top, bottom, edge = HILITE_TOP, HILITE_BOTTOM, HILITE_EDGE
        if color:
            top, bottom, edge = color, lerp(color, BLACK, 0.3), lerp(color, WHITE, 0.45)
        gradient(draw, x + 2, y + 2, TEAM_W - 4, rowH - 4, top, bottom)
        rect(draw, x + 2, y + 2, TEAM_W - 4, 1, edge)
    # Meters sit in the same spot on every row so counts line up down the column
    drawMeter(draw, sprite, x + TEAM_W - MAX_ICONS * sprite['step'] - 4,
              y + (rowH - len(sprite['rows'])) // 2, cell['rating'])
    text(draw, x + 6, y + (rowH - 8) // 2, cell['text'], WHITE if cell['won'] else GRAY,
         shadow=BLACK)


def drawTable(img, draw, title, rows, order, logos, sprite, rowH, colors=None):
    # Matchups-style table: names down the left, each team's numbers and meter to the right
    # Each row is {'name', 'sub', 'cells': {side: {'text', 'rating', 'won'}}}
    # Optional colors is {side: RGB} for each team's highlight bar
    colors = colors or {}
    height = TABLE_HEAD_H + len(rows) * rowH
    teamX = {order[0]: PANEL_X + LABEL_W, order[1]: PANEL_X + LABEL_W + TEAM_W}

    # Dark backdrop behind the team columns and the blue stripe down the left edge
    shade(img, PANEL_X + LABEL_W, TABLE_Y, TEAM_W * 2, height)
    gradient(draw, PANEL_X, TABLE_Y, STRIPE_W, height, STRIPE_TOP, STRIPE_BOTTOM, band=4)

    # Header: two-line title on navy, team logos over their columns
    gradient(draw, PANEL_X + STRIPE_W, TABLE_Y, LABEL_W - STRIPE_W, TABLE_HEAD_H, NAVY_LIGHT, NAVY)
    for i, line in enumerate(title):
        text(draw, PANEL_X + STRIPE_W + 4, TABLE_Y + 6 + 10 * i, line, WHITE, shadow=BLACK)
    for side, x in teamX.items():
        pasteLogo(img, logos[side], x + TEAM_W // 2, TABLE_Y + TABLE_HEAD_H // 2)

    # One row per entry
    for i, row in enumerate(rows):
        y = TABLE_Y + TABLE_HEAD_H + i * rowH
        drawLabel(draw, y, rowH, row['name'], row['sub'])
        for side, x in teamX.items():
            drawCell(draw, x, y, rowH, row['cells'][side], sprite, colors.get(side))


def dialogFrame(draw, x, y, w, h):
    # Game-style dialog box: gray bezel, white border, navy fill
    rect(draw, x, y, w, h, LCD_BEZEL)
    rect(draw, x + 1, y + 1, w - 2, h - 2, WHITE)
    gradient(draw, x + 3, y + 3, w - 6, h - 6, NAVY_LIGHT, NAVY, band=4)


def drawDialog(draw, x, y, w, h, lines):
    # Dialog box with a small white line, big gold line, small white line
    dialogFrame(draw, x, y, w, h)
    top, big, bottom = lines
    cx = x + w / 2
    centerText(draw, cx, y + 8, top, WHITE, shadow=BLACK)
    centerText(draw, cx, y + 19, big, GOLD, size=16, shadow=BLACK)
    centerText(draw, cx, y + 39, bottom, WHITE, shadow=BLACK)


def drawShareBar(draw, x, y, w, h, share, color, otherColor, fromLeft, label):
    # Stacked bar split share / 1 - share, framed so dark team colors still stand out on navy
    rect(draw, x, y, w, h, WHITE)
    rect(draw, x + 1, y + 1, w - 2, h - 2, BLACK)
    fx, fy, fw, fh = x + 2, y + 2, w - 4, h - 4
    split = round(min(max(share, 0.0), 1.0) * fw)

    # The share fills from its team's side of the screen, the rest takes the other side
    left = (split, color) if fromLeft else (fw - split, otherColor)
    right = (fw - split, otherColor) if fromLeft else (split, color)
    for sx, (width, fill) in ((fx, left), (fx + left[0], right)):
        rect(draw, sx, fy, width, fh, fill)
        # A lighter top edge gives each segment that 16-bit bevel
        rect(draw, sx, fy, width, 2, lerp(fill, WHITE, 0.35))
    # Dark seam where the two segments meet
    if 0 < left[0] < fw:
        rect(draw, fx + left[0], fy, 1, fh, BLACK)

    # Label centered on the whole bar, outlined so it reads over either color
    labelW = draw.textlength(label, font=font(16))
    text(draw, round(fx + (fw - labelW) / 2), fy + (fh - 16) // 2, label, WHITE, size=16,
         shadow=BLACK, outline=BLACK)


####
# SAVING
####

def saveScreen(img, fig_path):
    # Scales up with nearest neighbor so every pixel stays a hard square
    os.makedirs(os.path.dirname(fig_path) or '.', exist_ok=True)
    img.convert('RGB').resize((W * SCALE, H * SCALE), Image.NEAREST).save(fig_path)
    return fig_path
