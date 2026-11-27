# -*- coding: utf-8 -*-
"""
The stats.gtpdd.dog landing page: a chalkboard of stats math with one card per stat
page taped to it, each showing that page's latest image and linking through to it.

Cards are read from each page's own og:/twitter: tags, so they follow whatever run
the page was last built from. The stat scripts rebuild this page after each run.
Page template lives in lib/html/statsIndex/.

Run from the repo root:

    python statsIndex.py
"""

####
# IMPORTS
####

import os
import pathlib
import re
import shutil
from html import escape as html_escape
from html import unescape
from string import Template

from PIL import Image, ImageDraw, ImageFont

from lib.common import screenshotPage
from lib.fbCommon import previewMetaTags


####
# CONSTANTS
####

# Site and file locations
HOME_URL = "https://gtpdd.dog"
SITE_URL = "https://stats.gtpdd.dog"   # the published root of html/stats/
SITE_TITLE = "gtpdd Stats"
TWITTER_HANDLE = "@gotechplsdntdie"
HTML_DIR = "html/stats"
PAGE_FILENAME = 'index.html'
ASSET_DIR_NAME = 'statsIndex'          # this page's own files, grouped beside it
ASSET_DIR = os.path.join(HTML_DIR, ASSET_DIR_NAME)
WEB_IMG_DIR = os.path.join(ASSET_DIR, 'img')
GTPDD_LOGO = 'img/gtpdd_logo.png'      # the masthead logo, published as a smaller copy
HEADER_LOGO_FILENAME = 'gtpdd_logo_header.png'
HEADER_LOGO_HEIGHT = 256               # 2x the masthead's drawn height, so it stays sharp
TAGLINE = "Louisiana Tech charts, predictors and trackers"

# The STATS wordmark is an image because the site's CSP blocks web fonts
WORDMARK_TEXT = 'STATS'
WORDMARK_FONT = 'lib/font/fontOswald.ttf'
WORDMARK_FILENAME = 'stats_wordmark.png'
WORDMARK_FONT_PX = 240                 # rendered big and drawn at about a quarter of that
WORDMARK_TRACKING = 0.08               # extra space between letters, as a share of the font size
CSS_FILENAME = 'statsIndex.css'
JS_FILENAME = 'statsIndex.js'

# Page skeleton (the blackboard), stylesheet and script live in lib/html/statsIndex/
TEMPLATE_DIR = 'lib/html/statsIndex'
PAGE_TEMPLATE = os.path.join(TEMPLATE_DIR, 'page.html')
PAGE_CSS = os.path.join(TEMPLATE_DIR, CSS_FILENAME)
PAGE_JS = os.path.join(TEMPLATE_DIR, JS_FILENAME)

# The link-preview image for sharing the index: the board with every card in one row, screenshotted
PREVIEW_TEMPLATE = os.path.join(TEMPLATE_DIR, 'preview.html')
PREVIEW_HTML = 'out/html/statsIndexPreview.html'  # the filled template, kept only for the screenshot
PREVIEW_FILENAME = 'preview.jpg'
PREVIEW_SIZE = (1200, 630)             # a summary_large_image card
PREVIEW_SCALE = 2                      # shot at 2x and scaled down, for crisp text

# Self-hosted fonts, subset to the characters the page uses: (source, published name, its license)
# They load only once the site's CSP allows font-src 'self' (syncScript.sh stats adds it)
WEB_FONTS = [
    ('lib/font/fontKalam.ttf', 'Kalam.woff', 'lib/font/OFL-Kalam.txt'),
    ('lib/font/fontCabinSketchBold.ttf', 'CabinSketch-Bold.woff', 'lib/font/OFL-CabinSketch.txt'),
]
FONT_DIR = os.path.join(ASSET_DIR, 'fonts')
# Latin, punctuation, and the math the board notes use
FONT_UNICODES = ([*range(0x20, 0x7F), *range(0xA0, 0x100), 0x2013, 0x2014, 0x2018, 0x2019,
                  0x201C, 0x201D, 0x2022, 0x2026, *range(0x2190, 0x2194), 0x2212, 0x221A,
                  0x2248, 0x2264, 0x2265])

# Sports selected when the page loads; drop one in its offseason to hide its cards by default
DEFAULT_SECTIONS = ['Football', 'Basketball']

# One card per page, in display order. 'source' is the local page its tags are read from, 'href' the link.
# Optional: 'title' replaces the page's link-preview title; 'image' (relative to html/stats/) is a
# picture made just for this card, falling back to the link-preview image when it's missing
CARDS = [
    {'section': 'Football', 'source': 'html/stats/football/playchart.html',
     'href': 'football/playchart.html', 'title': 'Playchart',
     'image': 'football/playchart/card.jpg'},
    {'section': 'Football', 'source': 'html/stats/football/recordPredictor.html',
     'href': 'football/recordPredictor.html', 'title': 'Record Predictor',
     'image': 'football/recordPredictor/card.jpg'},
    {'section': 'Football', 'source': 'html/stats/football/sunBeltPredictor.html',
     'href': 'football/sunBeltPredictor.html', 'title': 'Sun Belt Predictor',
     'image': 'football/sunBeltPredictor/card.jpg'},
    {'section': 'Football', 'source': 'html/stats/football/scorigami.html',
     'href': 'football/scorigami.html', 'title': 'Scorigami',
     'image': 'football/scorigami/card.jpg'},
    {'section': 'Basketball', 'source': 'html/stats/hoops/lineups.html',
     'href': 'hoops/lineups.html', 'title': 'Lineup Tracker',
     'image': 'hoops/lineups/card.jpg'},
]

# <meta name|property="..." content="..."> tags, in either attribute order
META_RE = re.compile(r'<meta\s+(?:name|property)=["\']([^"\']+)["\']\s+content=["\']([^"\']*)["\']', re.I)
TITLE_RE = re.compile(r'<title>(.*?)</title>', re.I | re.S)


####
# CARDS
####

def readPreview(path):
    # Pulls a page's link-preview title and image from its meta tags
    with open(path) as f:
        head = f.read().split('</head>', 1)[0]
    tags = {name.lower(): unescape(value) for name, value in META_RE.findall(head)}
    title_tag = TITLE_RE.search(head)
    return {
        'title': tags.get('og:title') or tags.get('twitter:title')
                 or (unescape(title_tag.group(1).strip()) if title_tag else ''),
        'image': tags.get('og:image') or tags.get('twitter:image'),
    }


def localLink(url):
    # Turns a stats.gtpdd.dog URL into a link relative to the site root, so the page also works offline
    prefix = SITE_URL + '/'
    return url[len(prefix):] if url and url.startswith(prefix) else url


def cardImage(card_image, preview):
    # The card's own image when it's been made, else the page's link-preview image
    if card_image:
        path = os.path.join(HTML_DIR, card_image)
        if os.path.isfile(path):
            # The filename stays the same run to run, so the build time keeps browsers from showing a stale copy
            return f"{card_image}?v={int(os.path.getmtime(path))}"
    return localLink(preview['image'])


def cardHtml(section, title, href, image_src, shown=True):
    # One clickable card: image on top, section and title below; hidden when its sport isn't selected
    esc = lambda text: html_escape(str(text), quote=True)
    image = (f"<img class='card-img' src='{esc(image_src)}' alt='' loading='lazy'>"
             if image_src else "<div class='card-img card-img-empty'></div>")
    return (f"<a class='card' href='{esc(href)}' data-section='{esc(section)}'{'' if shown else ' hidden'}>\n"
            f"  {image}\n"
            f"  <div class='card-body'>\n"
            f"    <p class='card-section'>{esc(section)}</p>\n"
            f"    <h2 class='card-title'>{esc(title)}</h2>\n"
            f"  </div>\n"
            f"</a>")


def publishHeaderLogo():
    # A masthead-sized copy of the gtpdd logo; the source is thousands of pixels wide
    dest = os.path.join(WEB_IMG_DIR, HEADER_LOGO_FILENAME)
    if not os.path.isfile(GTPDD_LOGO):
        print(f"Missing {GTPDD_LOGO}; the masthead will do without it.")
        return None
    # Only redo it when the source logo has changed
    if not os.path.isfile(dest) or os.path.getmtime(GTPDD_LOGO) > os.path.getmtime(dest):
        img = Image.open(GTPDD_LOGO).convert('RGBA')
        img = img.crop(img.getbbox())
        img = img.resize((round(img.width * HEADER_LOGO_HEIGHT / img.height), HEADER_LOGO_HEIGHT), Image.LANCZOS)
        os.makedirs(WEB_IMG_DIR, exist_ok=True)
        img.save(dest, optimize=True)
    return f"{ASSET_DIR_NAME}/img/{HEADER_LOGO_FILENAME}"


def renderWordmark():
    # The STATS wordmark in Oswald: white letters with the logo's black outline and drop shadow
    dest = os.path.join(WEB_IMG_DIR, WORDMARK_FILENAME)
    font = ImageFont.truetype(WORDMARK_FONT, WORDMARK_FONT_PX)
    tracking = round(WORDMARK_FONT_PX * WORDMARK_TRACKING)
    stroke = round(WORDMARK_FONT_PX * 0.035)
    shadow = round(WORDMARK_FONT_PX * 0.04)
    # Lay the letters out one at a time so the tracking can be set
    widths = [font.getlength(ch) for ch in WORDMARK_TEXT]
    pad = stroke + shadow
    width = round(sum(widths) + tracking * (len(WORDMARK_TEXT) - 1)) + 2 * pad
    ascent, descent = font.getmetrics()
    img = Image.new('RGBA', (width, ascent + descent + 2 * pad), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Shadow first, offset down and right like the logo's, then the outlined letters on top
    for dx, dy, fill in ((shadow, shadow, 'black'), (0, 0, 'white')):
        x = pad
        for ch, w in zip(WORDMARK_TEXT, widths):
            draw.text((x + dx, pad + dy), ch, font=font, fill=fill, stroke_width=stroke, stroke_fill='black')
            x += w + tracking
    os.makedirs(WEB_IMG_DIR, exist_ok=True)
    img.crop(img.getbbox()).save(dest, optimize=True)
    return f"{ASSET_DIR_NAME}/img/{WORDMARK_FILENAME}"


def publishFonts():
    # Subsets each web font to the page's characters and publishes it with its license
    from fontTools import subset
    os.makedirs(FONT_DIR, exist_ok=True)
    for src, name, license_path in WEB_FONTS:
        dest = os.path.join(FONT_DIR, name)
        # Only redo a font when its source has changed
        if not os.path.isfile(dest) or os.path.getmtime(src) > os.path.getmtime(dest):
            options = subset.Options()
            options.flavor = 'woff'        # zlib-compressed; woff2 would need the brotli module
            options.layout_features = ['*']  # keep kerning and ligatures
            font = subset.load_font(src, options)
            subsetter = subset.Subsetter(options)
            subsetter.populate(unicodes=FONT_UNICODES)
            subsetter.subset(font)
            subset.save_font(font, dest, options)
            print(f"Wrote {dest} ({os.path.getsize(dest) // 1024}KB)")
        # The Open Font License travels with the font
        shutil.copyfile(license_path, os.path.join(FONT_DIR, os.path.basename(license_path)))


def filterHtml(sections, selected):
    # The sport toggles: 'All Sports' plus one per sport, pressed for each selected sport
    esc = lambda text: html_escape(str(text), quote=True)
    pressed = lambda on: 'true' if on else 'false'
    buttons = [f"<button type='button' class='filter' data-filter='all' "
               f"aria-pressed='{pressed(set(sections) <= set(selected))}'>All Sports</button>"]
    buttons += [f"<button type='button' class='filter' data-filter='{esc(s)}' "
                f"aria-pressed='{pressed(s in selected)}'>{esc(s)}</button>" for s in sections]
    return "<div class='filters' role='group' aria-label='Sports'>\n" + '\n'.join(buttons) + "\n</div>"


####
# LINK PREVIEW
####

def fileUri(href):
    # A link relative to html/stats/ (query string and all) as a file:// URL, for rendering from out/html/
    return pathlib.Path(HTML_DIR, href.split('?')[0]).resolve().as_uri()


def writePreviewImage(card_rows, logo_href, wordmark_href):
    # Renders the board with every card in one row as the index's link-preview image; returns its link or None
    esc = lambda text: html_escape(str(text), quote=True)
    with open(PAGE_TEMPLATE) as f:
        page_text = f.read()
    # The same chalk notes as the page; the preview's styles pick which of them show
    notes = re.search(r"<div class='board-notes'.*?\n</div>", page_text, re.S)
    brand = ((f"<img class='brand-logo' src='{esc(fileUri(logo_href))}' alt=''>" if logo_href else "")
             + f"<img class='wordmark' src='{esc(fileUri(wordmark_href))}' alt=''>")
    # Every card, whatever the default filter, since the preview stands for the whole page
    cards = [cardHtml(section, title, href, fileUri(image) if image else None)
             for section, title, href, image in card_rows]
    with open(PREVIEW_TEMPLATE) as f:
        template = Template(f.read())
    os.makedirs(os.path.dirname(PREVIEW_HTML), exist_ok=True)
    with open(PREVIEW_HTML, 'w') as f:
        f.write(template.substitute(
            cssHref=esc(fileUri(f"{ASSET_DIR_NAME}/{CSS_FILENAME}")),
            notes=notes.group(0) if notes else '',
            brand=brand, tagline=esc(TAGLINE), cards='\n'.join(cards)))
    dest = os.path.join(ASSET_DIR, PREVIEW_FILENAME)
    if screenshotPage(PREVIEW_HTML, dest, size=PREVIEW_SIZE, scale=PREVIEW_SCALE, query='') is None:
        return None
    print(f"Wrote {dest}")
    # The build time keeps a share from picking up a stale copy of the same filename
    return f"{ASSET_DIR_NAME}/{PREVIEW_FILENAME}?v={int(os.path.getmtime(dest))}"


####
# MAIN
####

def writeStatsIndex():
    # Rebuilds html/stats/index.html from the current state of every stat page
    # A page that hasn't been built yet just gets left off
    built = [card for card in CARDS if os.path.isfile(card['source'])]
    for card in CARDS:
        if card not in built:
            print(f"Skipping {card['source']}: not built yet")

    # One toggle per sport with a card, in card order; a default naming none of them shows everything
    sections = list(dict.fromkeys(card['section'] for card in built))
    selected = [s for s in sections if s in DEFAULT_SECTIONS] or sections

    # Cards outside the default selection start hidden, so the page is right before the script runs
    cards, card_rows = [], []
    for card in built:
        preview = readPreview(card['source'])
        row = (card['section'], card.get('title') or preview['title'], card['href'],
               cardImage(card.get('image'), preview))
        card_rows.append(row)
        cards.append(cardHtml(*row, shown=card['section'] in selected))

    # Stylesheet, script, fonts and masthead images sit in the page's asset folder, since a strict CSP won't run them inline
    os.makedirs(ASSET_DIR, exist_ok=True)
    shutil.copyfile(PAGE_CSS, os.path.join(ASSET_DIR, CSS_FILENAME))
    shutil.copyfile(PAGE_JS, os.path.join(ASSET_DIR, JS_FILENAME))
    logo_href = publishHeaderLogo()
    wordmark_href = renderWordmark()
    publishFonts()

    esc = lambda text: html_escape(str(text), quote=True)
    # The heading reads 'gtpdd Stats' to screen readers through the images' alt text
    brand = ((f"<img class='brand-logo' src='{esc(logo_href)}' alt='gtpdd'>" if logo_href else "gtpdd ")
             + f"<img class='wordmark' src='{esc(wordmark_href)}' alt='Stats'>")
    icon = f"<link rel='icon' href='{esc(logo_href)}'>\n" if logo_href else ""
    description = "Louisiana Tech playcharts, predictors, lineups and more from gtpdd."
    # The share image: the board with every card on it, made after the stylesheet and fonts are published
    preview_href = writePreviewImage(card_rows, logo_href, wordmark_href)
    card_image = f"{SITE_URL}/{preview_href}" if preview_href else None

    # Fill the page template, escaping plain text
    with open(PAGE_TEMPLATE) as f:
        template = Template(f.read())
    # substitute, not safe_substitute: an unfilled placeholder fails the run instead of shipping
    page = template.substitute(
        title=esc(SITE_TITLE),
        headLinks=(previewMetaTags(SITE_TITLE, description, SITE_URL + '/', card_image,
                                   twitter_handle=TWITTER_HANDLE) + icon).rstrip('\n'),
        cssHref=esc(f"{ASSET_DIR_NAME}/{CSS_FILENAME}"),
        homeUrl=esc(HOME_URL),
        brand=brand,
        tagline=esc(TAGLINE),
        filters=filterHtml(sections, selected),
        cards='\n'.join(cards),
        jsSrc=esc(f"{ASSET_DIR_NAME}/{JS_FILENAME}"),
    )
    html_path = os.path.join(HTML_DIR, PAGE_FILENAME)
    with open(html_path, 'w') as f:
        f.write(page)
    print(f"Wrote {html_path} ({len(cards)} cards)")
    return html_path


####
# COMMAND LINE
####

if __name__ == "__main__":
    writeStatsIndex()
