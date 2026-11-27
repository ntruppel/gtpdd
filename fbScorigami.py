# -*- coding: utf-8 -*-
"""
Louisiana Tech football scorigami: how often each final score has happened in
school history, and whether the latest game's score is new.

Combines the game history in csv/fbScorigamiGames.csv with this season's games from
CFBD and writes the score table to html/stats/football/scorigami/json.js. The page is
html/stats/football/scorigami.html (stats.gtpdd.dog); its template and hand-made files
live in lib/html/fbScorigami/.

Run from the repo root:

    python fbScorigami.py               # this season
    python fbScorigami.py --year 2025   # a past season
"""

####
# IMPORTS
####

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import cfbd
import os
import json
import re
from datetime import datetime
from html import escape as html_escape
from string import Template
from dotenv import load_dotenv

from lib.common import copyMissingFiles, screenshotPage
from lib.fbCommon import currentSeason, previewMetaTags
from statsIndex import writeStatsIndex

# Pull the CFBD API key and other settings from .env
load_dotenv()


####
# CONSTANTS
####

# Site and file locations
SITE_URL = "https://stats.gtpdd.dog"   # the published root of html/stats/
TWITTER_HANDLE = "@gotechplsdntdie"
HTML_DIR = "html/stats"                # shared by several gtpdd stat pages
SITE_SECTION = 'football'              # the page publishes under stats.gtpdd.dog/football/
PAGE_DIR = os.path.join(HTML_DIR, SITE_SECTION)
PAGE_FILENAME = 'scorigami.html'
ASSET_DIR_NAME = 'scorigami'           # this page's own files, grouped beside it
ASSET_DIR = os.path.join(PAGE_DIR, ASSET_DIR_NAME)
PAGE_TO_ASSETS = f"{ASSET_DIR_NAME}/"  # from football/scorigami.html to the asset folder
DATA_JS = os.path.join(ASSET_DIR, 'json.js')  # the score table the page's script imports
PREVIEW_FILENAME = 'preview.png'

# Page skeleton and hand-made files (script, CSS, images) live in lib/html/fbScorigami/
TEMPLATE_DIR = 'lib/html/fbScorigami'
PAGE_TEMPLATE = os.path.join(TEMPLATE_DIR, 'page.html')
STATIC_DIR = os.path.join(TEMPLATE_DIR, 'static')

# The stats.gtpdd.dog index card: a zoom on the chart around the latest score, screenshotted beside the page
CARD_TEMPLATE = os.path.join(TEMPLATE_DIR, 'card.html')
CARD_HTML = 'out/html/fbScorigamiCard.html'  # the filled template, kept only for the screenshot
CARD_FILENAME = 'card.jpg'
CARD_SIZE = (1200, 630)                # the same shape as the link-preview cards
CARD_SCALE = 2                         # shot at 2x and scaled down, for crisp text
CHART_WIN_MAX, CHART_LOSS_MAX = 100, 57  # the chart's last column and row, as in script.js
ZOOM_COLS, ZOOM_ROWS = 7, 3            # cells shown around the latest score; odd, so it can sit in the middle
CAPTION_FONT_PX = 50                   # the verdict line's size, shrunk for lines longer than CAPTION_FIT_CHARS
CAPTION_FIT_CHARS = 52                 # about how many characters fit across the card at full size
# Scores the chart blacks out besides any losing score above the winning one: (winning, losing)
IMPOSSIBLE_SCORES = {(1, 1), (1, 0), (2, 1), (3, 1), (4, 1), (5, 1), (7, 1)}


####
# SCORE TABLE
####

def generateScorigamiTable(df):
    # Returns one row per final score that has happened, with its count and the last Tech win/loss by it
    win_scores = []
    lose_scores = []

    # Winning and losing score of each game, regardless of which team was Tech
    df['winScore'] = df[["Tech Score", "Opponent Score"]].max(axis=1)
    df['lossScore'] = df[["Tech Score", "Opponent Score"]].min(axis=1)

    df['TechWin'] = np.where(df["Tech Score"] > df["Opponent Score"], True, False)


    df = df[['winScore','lossScore','Opponent','Date','TechWin']]
    df = df.reset_index()
    print(df)

    # Walk every possible score (0-100 winning, 0-71 losing) and tally the games that ended with it
    numGames = []
    lastWin = []
    lastLoss = []
    for i in range(0,101):
        for j in range(0,72):
            filter = df[(df['winScore'] == i) & (df['lossScore'] == j)]
            if filter.empty:
                numGames.append(0)
                lastWin.append('')
                lastLoss.append('')

            else:
                numGames.append(len(filter))

                # Most recent Tech win with this score, as 'Date: Opponent'
                winFilter = filter[(filter['TechWin'] == True)]
                try: lastWin.append(str(winFilter['Date'].values[-1]) + ": " + str(winFilter['Opponent'].values[-1]))
                except: lastWin.append('')

                # Most recent Tech loss (or tie) with this score
                lossFilter = filter[(filter['TechWin'] == False)]
                try: lastLoss.append(str(lossFilter['Date'].values[-1]) + ": " + str(lossFilter['Opponent'].values[-1]))
                except: lastLoss.append('')

    # Keep only real scores (winner >= loser) that have actually happened
    df = pd.DataFrame({'winScore':np.repeat([*range(0,101)],72), 'lossScore':[*range(0,72)]*101, 'numGames':numGames, 'lastWin':lastWin, 'lastLoss':lastLoss})
    df = df[(df['winScore'] >= df['lossScore']) & (df['numGames'] > 0)]
    return df


####
# CHART
####

def generateScorigamiChart(df, df_wl, ext, win_score, lose_score, fullPath, basicPath):
    # Draws the scorigami grid as a PNG, highlighting the latest game's square (not called at the moment)
    win_min = 0
    win_max = 101
    lose_min = 0
    lose_max = 61
    win_med = (win_min + win_max) / 2
    lose_med = (lose_min + lose_max) / 2

    fig, ax = plt.subplots()
    df_wl = df_wl[['Tech Score','Opponent Score']]

    # One square per score: black if impossible, colored if it has happened, white if not
    for index,row in df.iterrows():
        win = row['Win']
        lose = row['Lose']

        if lose > win:
            rect = patches.Rectangle((win, lose), 1, 1, linewidth=0.01, edgecolor='black', facecolor='black')
            ax.add_patch(rect)

        elif row['isGami'] > 0:

            linewidth = 0.01; edgecolor = 'black'

            # ext colors squares by whether Tech won or lost with that score
            if ext:
                filter_l = df_wl[(df_wl['Tech Score'] == lose) & (df_wl['Opponent Score'] == win)]
                filter_w = df_wl[(df_wl['Tech Score'] == win) & (df_wl['Opponent Score'] == lose)]

                # Tech has both won and lost by this score
                if not filter_l.empty and not filter_w.empty:
                    rect = patches.Rectangle((win, lose), 1, 1, linewidth=linewidth, edgecolor=edgecolor, facecolor='blue')
                    if win == win_score and lose == lose_score:
                        game_color = 'blue'

                # Only wins
                elif filter_l.empty and not filter_w.empty:
                    rect = patches.Rectangle((win, lose), 1, 1, linewidth=linewidth, edgecolor=edgecolor, facecolor='skyblue')
                    if win == win_score and lose == lose_score:
                        game_color = 'skyblue'

                # Only losses
                elif not filter_l.empty and filter_w.empty:
                    rect = patches.Rectangle((win, lose), 1, 1, linewidth=linewidth, edgecolor=edgecolor, facecolor='red')
                    if win == win_score and lose == lose_score:
                        game_color = 'red'
                else:
                    rect = patches.Rectangle((win, lose), 1, 1, linewidth=linewidth, edgecolor=edgecolor, facecolor='green')

            else:
                rect = patches.Rectangle((win, lose), 1, 1, linewidth=linewidth, edgecolor=edgecolor, facecolor='blue')

            ax.add_patch(rect)


            # Number of games with this score, printed in the square
            ax.text(win+0.5,lose+0.5,str(row['isGami']), fontsize=2, ha='center', va='center', color='white')

        else:
            rect = patches.Rectangle((win, lose), 1, 1, linewidth=0.01, edgecolor='black', facecolor='white')
            ax.add_patch(rect)
    # Outline the latest game's square (skipped if it wasn't found above)
    try:
        rect = patches.Rectangle((win_score, lose_score), 1, 1, linewidth=1, edgecolor='black', facecolor=game_color)
        ax.add_patch(rect)
    except:
        0


    # Axis numbers and labels
    plt.xlim([win_min, win_max])
    plt.ylim([lose_max,lose_min])
    for i in range(win_min,win_max):
        ax.text(i+0.5,lose_min-0.5,str(i), fontsize=2, ha='center')
    for i in range(lose_min,lose_max):
        ax.text(win_min-1,i+0.5,str(i), fontsize=2, va='center')

    ax.text(win_med,lose_min-1.5,"Winning Team Score", ha='center', fontsize=4)
    ax.text(win_min-2,lose_med,"Losing Team Score", va='center', fontsize=4, rotation=90)
    ax.axis('off')
    ax.text(win_med, lose_min-3, 'Louisiana Tech Scorigami', ha='center', fontsize=12)

    # Color legend
    ax.text(82,20,'Games Tech Won', color='skyblue', fontsize=5)
    ax.text(82,22,'Games Tech Lost', color='red', fontsize=5)
    ax.text(82,24,'Some Combination/Tie', color='blue', fontsize=5)

    # Full (colored) and basic charts save to different files
    if ext:
        fig_path = fullPath
    else:
        fig_path = basicPath
    plt.savefig(fig_path, bbox_inches='tight', pad_inches = 0, dpi = 1000)

    return 0


####
# SCORIGAMI CHECK
####

def checkIfScorigami(df, techScore, oppoScore):
    # Prints whether a final score is a scorigami, and if not, when it last happened
    forwardGames, forwardLastOppo, forwardLastDate = 0,0,0
    backwardGames, backwardLastOppo, backwardLastDate = 0,0,0
    # 'Forward' games had Tech on the same side of the score; 'backward' games had it flipped
    forward_df = df[(df['Tech Score'] == techScore) & (df['Opponent Score'] == oppoScore)]
    backward_df = df[(df['Tech Score'] == oppoScore) & (df['Opponent Score'] == techScore)]

    # Score has happened both ways round
    if not forward_df.empty and not backward_df.empty:
        forwardGames = len(forward_df)
        forwardLastOppo = forward_df.iloc[-1]['Opponent']
        forwardLastDate = forward_df.iloc[-1]['Date']

        backwardGames = len(backward_df)
        backwardLastOppo = backward_df.iloc[-1]['Opponent']
        backwardLastDate = backward_df.iloc[-1]['Date']

        totalGames = forwardGames + backwardGames
        message = "Saturday's game was not a scorigami.\n\nThis exact score has happened " +  str(totalGames) + " times before in school history.\nThe last time Tech was the team with " + str(techScore) + ", it was on " + forwardLastDate + " against " + forwardLastOppo + ".\nThe last time Tech scored " + str(oppoScore) + " instead, it was on " + backwardLastDate + " against " + backwardLastOppo

    # Only with Tech on the same side
    elif not forward_df.empty and backward_df.empty:
        totalGames = len(forward_df)
        lastOppo = forward_df.iloc[-1]['Opponent']
        lastDate = forward_df.iloc[-1]['Date']
        if totalGames > 1:
            message = "Saturday's game was not a scorigami.\n\nThis exact score has happened " +  str(totalGames) + " times before in school history.\nMost recently, on " + lastDate + ", the final was Tech " + str(techScore) + " - " + lastOppo + " " + str(oppoScore)
        else:
            message = "Saturday's game was not a scorigami.\n\nBut this was only the second time in school history a game ended with this score.\nThe other time was on " + lastDate + ", and the final was Tech " + str(techScore) + " - " + lastOppo + " " + str(oppoScore)

    # Only with Tech on the other side
    elif forward_df.empty and not backward_df.empty:
        totalGames = len(backward_df)
        lastOppo = backward_df.iloc[-1]['Opponent']
        lastDate = backward_df.iloc[-1]['Date']
        if totalGames > 1:
            message = "Saturday's game was not a scorigami.\n\nThis exact score has happened " +  str(totalGames) + " times before in school history.\nBut never has Tech been the team with " + str(techScore) + " points.\nMost recently, on " + lastDate + ", the final was Tech " + str(oppoScore) + " - " + lastOppo + " " + str(techScore)
        else:
            message = "Saturday's game was not a scorigami.\n\nBut this was only the second time in school history a game ended with this score.\nThat time, Tech was the team with " + str(oppoScore) + " points.\nIt was on " + lastDate + ", and the final was Tech " + str(oppoScore) + " - " + lastOppo + " " + str(techScore)

    # Never happened: a scorigami
    else:
        message = "Saturday's game was a scorigami!!\n\nNever before has game ended with the final score of " + str(techScore) + " to " + str(oppoScore) + " in the 120 year history of Louisiana Tech football"

    print(message)


####
# INDEX CARD
####

def readScoreTable(path=DATA_JS):
    # Reads the score table back out of json.js (a JSON string wrapped in a JS module)
    with open(path) as f:
        match = re.search(r"const json = '(.*)';", f.read(), re.S)
    return json.loads(match.group(1).replace("\\'", "'"))['results'] if match else []


def latestGame(results):
    # The most recent game, from the newest 'Month DD, YYYY: Opponent' date: its score cell, result and opponent
    best = None
    for r in results:
        for key in ('lastWin', 'lastLoss'):
            if r.get(key):
                date_text, _, opponent = r[key].partition(': ')
                when = datetime.strptime(date_text, '%B %d, %Y')
                if best is None or when > best['date']:
                    best = {'date': when, 'win': r['winScore'], 'loss': r['lossScore'],
                            'techWon': key == 'lastWin', 'opponent': opponent, 'numGames': r['numGames']}
    return best


def scorigamiCaption(game):
    # 'Tech's 48-3 win over Arkansas State WAS a Scorigami', or 'was NOT' for a score that's happened before
    esc = lambda text: html_escape(str(text), quote=True)
    score = f"{game['win']}-{game['loss']}"
    # Ties sit with the losses in the score table
    if game['win'] == game['loss']:
        result = f"tie with {esc(game['opponent'])}"
    elif game['techWon']:
        result = f"win over {esc(game['opponent'])}"
    else:
        result = f"loss to {esc(game['opponent'])}"
    # The latest game is the only one with its score when it's a first
    verdict = ("<strong class='yes'>WAS</strong>" if game['numGames'] == 1
               else "was <strong class='no'>NOT</strong>")
    return f"Tech's {score} {result} {verdict} a Scorigami"


def cellColor(entry, win, loss):
    # A cell's background, by the same rules as the chart's script.js
    if loss > win or (win, loss) in IMPOSSIBLE_SCORES:
        return 'black'
    if not entry:
        return None
    if entry['lastWin']:
        return 'midnightblue' if entry['lastLoss'] else 'dodgerblue'
    # Only Tech losses by this score; a tie counts as both sides
    return 'midnightblue' if win == loss else 'firebrick'


def zoomGridHtml(results, center, cols=ZOOM_COLS, rows=ZOOM_ROWS):
    # The cols x rows cells around center plus the chart's header row and column, as a table
    win, loss = center
    lookup = {(r['winScore'], r['lossScore']): r for r in results}
    # Centered on the score, shifted inward only when it sits near the chart's edge
    first_win = min(max(win - cols // 2, 0), CHART_WIN_MAX - (cols - 1))
    first_loss = min(max(loss - rows // 2, 0), CHART_LOSS_MAX - (rows - 1))
    wins = range(first_win, first_win + cols)
    losses = range(first_loss, first_loss + rows)

    # Header row: winning scores, zero-padded like the chart
    rows = ["<thead><tr><th class='corner'></th>" + ''.join(f"<th>{w:02d}</th>" for w in wins) + "</tr></thead>"]
    body = []
    for l in losses:
        cells = [f"<th>{l:02d}</th>"]
        for w in wins:
            entry = lookup.get((w, l))
            color = cellColor(entry, w, l)
            style = f" style='background:{color}'" if color else ''
            cls = " class='latest'" if (w, l) == (win, loss) else ''
            # Impossible scores show no count, like the chart's black cells
            count = entry['numGames'] if entry and color != 'black' else ''
            cells.append(f"<td{cls}{style}>{count}</td>")
        body.append("<tr>" + ''.join(cells) + "</tr>")
    rows.append("<tbody>" + ''.join(body) + "</tbody>")
    return "<table>" + ''.join(rows) + "</table>"


def writeIndexCard():
    # Renders the index card image zoomed on the latest score; returns its filename, or None without data or Chrome
    results = readScoreTable()
    game = latestGame(results)
    if game is None:
        return None
    center = (game['win'], game['loss'])
    with open(CARD_TEMPLATE) as f:
        template = Template(f.read())
    os.makedirs(os.path.dirname(CARD_HTML), exist_ok=True)
    with open(CARD_HTML, 'w') as f:
        caption = scorigamiCaption(game)
        # Shrink the caption for long opponent names so it stays on one line
        chars = len(re.sub(r'<[^>]+>', '', caption))
        size = min(CAPTION_FONT_PX, int(CAPTION_FONT_PX * CAPTION_FIT_CHARS / chars))
        f.write(template.substitute(caption=caption, captionSize=size, grid=zoomGridHtml(results, center)))
    # The stats index falls back to the link-preview image when there's no card
    dest = os.path.join(ASSET_DIR, CARD_FILENAME)
    if screenshotPage(CARD_HTML, dest, size=CARD_SIZE, scale=CARD_SCALE, query='') is None:
        return None
    print(f"Wrote {dest} (zoomed on {center[0]}-{center[1]})")
    return CARD_FILENAME


####
# WEB PAGE
####

def writeSite(updated):
    # Writes football/scorigami.html and restores any missing files in its asset folder
    copyMissingFiles(STATIC_DIR, ASSET_DIR)
    os.makedirs(PAGE_DIR, exist_ok=True)

    # Link-preview tags, with the update date so the stats landing page card shows it
    title = "Louisiana Tech Scorigami"
    description = f"Every final score in Louisiana Tech football history. Updated {updated}."
    page_url = f"{SITE_URL}/{SITE_SECTION}/{PAGE_FILENAME}"
    card_image = f"{SITE_URL}/{SITE_SECTION}/{ASSET_DIR_NAME}/{PREVIEW_FILENAME}"
    icon = f"<link rel='icon' href='{PAGE_TO_ASSETS}favicon.png'>\n"

    # Fill the page template; substitute fails the run on an unfilled placeholder
    with open(PAGE_TEMPLATE) as f:
        template = Template(f.read())
    page = template.substitute(
        title=html_escape(title),
        headLinks=(previewMetaTags(title, description, page_url, card_image,
                                   twitter_handle=TWITTER_HANDLE) + icon).rstrip('\n'),
        assets=html_escape(PAGE_TO_ASSETS, quote=True),
    )
    html_path = os.path.join(PAGE_DIR, PAGE_FILENAME)
    with open(html_path, 'w') as f:
        f.write(page)
    print(f"Wrote {html_path}")

    # Refresh this page's card on the stats.gtpdd.dog landing page, with its own card image
    writeIndexCard()
    writeStatsIndex()
    return html_path


####
# MAIN
####

def fbScorigami(platform, year=None):
    # Input and output paths differ between Windows and the AWS box
    if platform == 'Windows':
        df = pd.read_csv(r'in_files/fbScorigamiGames.csv')
        fullPath = r'out_files/fbScorigami.png'
        basicPath = r'out_files/fbScorigamiBasic.png'
    elif platform == 'AWS':
        df = pd.read_csv('csv/fbScorigamiGames.csv')
        fullPath = 'out/fbScorigami.png'
        basicPath = 'out/fbScorigamiBasic.png'

    # Dates as 'September 06, 2025'
    df['Date'] = pd.to_datetime(df['Date'])
    df['Date'] = df['Date'].dt.strftime('%B %d, %Y')

    # This season's games from CFBD
    season = year or currentSeason()
    configuration = cfbd.Configuration( access_token = os.environ["cfbdAuth"] )
    api_instance = cfbd.GamesApi(cfbd.ApiClient(configuration))
    api_response = api_instance.get_games(season, team='Louisiana Tech')

    # Finished games only, oldest first, so the last one is the latest game
    finished = sorted((g for g in api_response
                       if g.completed and g.home_points is not None and g.away_points is not None),
                      key=lambda g: g.start_date)

    # Each finished game from Tech's side
    dates = []
    techs = []
    tech_scores = []
    oppos = []
    oppo_scores = []
    for game in finished:
        awayTeam = game.away_team
        awayScore = game.away_points
        homeTeam = game.home_team
        homeScore = game.home_points
        if awayTeam == 'Louisiana Tech':
            techScore = awayScore
            oppoScore = homeScore
            oppo = homeTeam
        else:
            techScore = homeScore
            oppoScore = awayScore
            oppo = awayTeam

        dates.append(game.start_date)
        techs.append('Louisiana Tech')
        tech_scores.append(techScore)
        oppos.append(oppo)
        oppo_scores.append(oppoScore)
        print(awayTeam, awayScore, homeTeam, homeScore)

    # This season's games, with dates in Central time
    df2 = pd.DataFrame({"Date":dates, "Tech":techs, "Tech Score": tech_scores, "Opponent":oppos, "Opponent Score":oppo_scores})
    df2['Opponent'] = df2['Opponent'].replace('Louisiana', 'Louisiana-Lafayette')
    print(df2)
    if not df2.empty:
        df2['Date'] = pd.to_datetime(df2['Date'], utc=True).dt.tz_convert('US/Central')
        df2['Date'] = df2['Date'].dt.strftime('%B %d, %Y')

    # Add them to the history, keeping the CSV's row for any game that's already in it
    df = pd.concat([df, df2]).drop_duplicates(subset=['Date', 'Tech Score', 'Opponent Score'], keep='first')

    # Save every game, then the score table
    df.to_csv('out/fbScorigamiDataAlt.csv', index=False)
    df_s = generateScorigamiTable(df)
    df_s.to_csv('out/fbScorigamiData.csv', index=False)

    # Write the score table and update date as a JS module for the web page
    jsonString = "const json = '"
    jsonString += '{"results": '
    jsonString += df_s.to_json(index=False, orient="records")
    dateString = datetime.today().strftime('%B %d, %Y')
    jsonString += ',"updated": "' + dateString + '"}' + "';\nexport default json;\n"
    os.makedirs(ASSET_DIR, exist_ok=True)
    with open(DATA_JS, 'w') as f:
        print(jsonString, file=f)
    print(f"Wrote {DATA_JS}")

    # The page and its files; syncScript.sh stats publishes them with the rest of the site
    writeSite(dateString)

    # Nothing to check until a game this season has finished
    if df2.empty:
        print(f"No finished {season} games yet, so there's no score to check.")
        return

    # Check the latest game against every other game, so it doesn't count itself
    latest = df2.iloc[-1]
    isLatest = ((df['Date'] == latest['Date']) & (df['Tech Score'] == latest['Tech Score'])
                & (df['Opponent Score'] == latest['Opponent Score']))
    checkIfScorigami(df[~isLatest], latest['Tech Score'], latest['Opponent Score'])


####
# COMMAND LINE
####

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Update the Louisiana Tech scorigami table and check the latest game's score.")
    parser.add_argument("--year", type=int, help="Season to pull from CFBD (default: the current one)")
    args = parser.parse_args()

    fbScorigami('AWS', year=args.year)
