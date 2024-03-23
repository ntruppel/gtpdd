import json
from bs4 import BeautifulSoup as Soup
import requests
import numpy as np
import pandas as pd
from pandas import DataFrame
import matplotlib
import matplotlib.pyplot as plt
import six
import csv
import tweepy
from datetime import datetime, timedelta
from PIL import Image, ImageFont, ImageDraw
from lib.bsbCommon import getBoxScore
from lib.common import parseRowStringTextTrue
import boto3

def get_hitting_stats(score):
    ###
    # For each boxscore, we need to grab the hitting stats
    # We do that by grabbing the Composite Stat table from the official box score
    ###
    
    box_url = 'https://latechsports.com' + str(score)
    box_soup = Soup((requests.get(box_url)).text, features="lxml")
    tables = box_soup.find_all('table')
    
    ## Figure out if Tech is home or away
    ### This is more complicated than it probably needs to be
    team_names = tables[0].find_all('span')
    list_of_parsed_span_rows = [parseRowStringTextTrue(row) for row in team_names[1:]]
    list_of_parsed_span_rows = [str(i)[2:-2] for i in list_of_parsed_span_rows]
    list_of_parsed_span_rows = [i for i in list_of_parsed_span_rows if 'Winner' not in i]
    list_of_parsed_span_rows = [i for i in list_of_parsed_span_rows if 'TECH' != i]
    if len(list_of_parsed_span_rows) == 3:
        lens = []
        for row in list_of_parsed_span_rows:
            lens.append(len(row))
        del list_of_parsed_span_rows[lens.index(min(lens))]
    awayName = str(list_of_parsed_span_rows[0])
    homeName = str(list_of_parsed_span_rows[1])
    if homeName in ['LA Tech', 'Louisiana Tech']: bat = tables[-1]
    else: bat = tables[-2]
    
    ## Grab the info from the table and put it in a DataFrame
    rows = bat.find_all('tr')
    list_of_parsed_rows = [parseRowStringTextTrue(row) for row in rows[1:]]
    mod_rows = []
    for p in list_of_parsed_rows:
        p = [i for i in p if i not in '\n' if i not in '\xa0\xa0\xa0\xa0']
        p = p[1:]
        mod_rows.append(p)
    rows = mod_rows[:-1]
    df = DataFrame(rows)

    ## Format the df
    df[1] = df[1].str.split(',', expand=True)[0]
    df.columns = ['POS','Name','AB','R','H','RBI','2B','3B','HR','BB','SB','CS','HBP', 'SH', 'SF', 'SO', 'KL', 'GDP', 'PO', 'A']
        
    df = df.reset_index(drop = True)
    df = df.drop(columns='POS')
    df = df.set_index('Name')
    df = df.apply(pd.to_numeric)
    df = df[df.AB != 0]
    return df

def generateScorecardSquare(card,card_draw,color,play_list,w,h,sw,sh):

    ## List plays that reach bases
    listHome = ['HR', 'x4WP', 'x4', 'z4', 'z4WP', 'SB4']
    listThird = listHome + ['3B', 'x3', 'x3WP', 'z3', 'z3WP', 'SB3']
    listSecond = listThird + ['2B', 'x2', 'x2WP', 'z2', 'z2WP', 'SB2']
    listFirst = listSecond + ['1B', 'BB', 'HBP', 'E2', 'E', 'FC', 'IBB']

    ###
    # GET COLOR SPECIFICS
    ###
    if color == 'blue':
        single = Image.open('/tmp/bsbScorecardSingleBlue.jpg')
        textColor = 'black'
        errColor = '#A20000'
    elif color == 'gray':
        single = Image.open('/tmp/bsbScorecardSingleGrey.jpg')
        textColor = '#2C4997'
        errColor = '#A20000'
    elif color == 'red':
        single = Image.open('/tmp/bsbScorecardSingleRed.jpg')
        textColor = '#2C4997'
        errColor = '#A20000'
    elif color == 'sky':
        single = Image.open('/tmp/bsbScorecardSingleSky.jpg')
        textColor = 'black'
        errColor = '#A20000'
    elif color == 'white':
        single = Image.open('/tmp/bsbScorecardSingleWhite.jpg')
        textColor = '#2C4997'
        errColor = '#A20000'
    elif color == 'pinstripe':
        single = Image.open('/tmp/bsbScorecardSinglePinstripe.jpg')
        textColor = '#2C4997'
        errColor = '#A20000'

    card.paste(single, (w,h))

    ###
    # ITERATE THROUGH PLAYLIST
    ###

    for row in play_list:
        
        ## If out at base, print an 'x'
        if row['Play'].startswith('x'): 
            if row['Play'].startswith('x1'):
                x,y = w+97,h+56
            if row['Play'].startswith('x2'):
                x,y = w+67,h+26
            if row['Play'].startswith('x3'):
                x,y = w+36,h+56
            if row['Play'].startswith('x4'):
                x,y = w+66,h+86
            card_draw.text((x,y), 'x', font=name_font,fill=errColor)
            
            ## We can ignore other baserunning for now
        elif row['Play'].startswith(('z','SB')): 0
        
        ## Everything remaining is a batting play
        else:
            
            ## Calculate the width and height of the text to be drawn, given font size
            w1 = card_draw.textlength(row['Play'], font=play_font)
            h1 = 35
            x = (sw - 15 - w1)/2 + w + 15
            y = (sh - 35 - h1)/2 + h + 35
            
            ## Record play text
            if row['Play'] in listFirst:
                card_draw.text((x, y), row['Play'], font=play_font,fill=textColor, align='center')
            else:
                card_draw.text((x, y), row['Play'], font=play_font,fill=errColor, align='center')
                
            ## Set up Balls and Strikes (if they exist)
            try:
                count = str(row['Count'])[:3]
                if count[0].isdigit():
                    balls = count[0]
                    strikes = count[-1]
                ## Loop through balls
                b_w = w+13
                b_h = h+5
                i = 0
                while int(balls) > 0:
                    card_draw.text((b_w + i, b_h), '/', font=bs_font,fill=textColor)
                    balls = int(balls) - 1
                    i = i + 22
                    
                ## Loop through strikes
                s_w = w+13
                s_h = h+25
                i = 0
                while int(strikes) > 0:
                    card_draw.text((s_w + i, s_h), '/', font=bs_font,fill=textColor)
                    strikes = int(strikes) - 1
                    i = i + 22
            except: print("No Balls and Strikes")
        
        ## Record basepath movement to first
        x1,y1 = w+101,h+82
        x2,y2 = w+70,h+54
        x3,y3 = w+40,h+82
        x4,y4 = w+70,h+112
        if row['Play'] in listFirst:
            card_draw.line(([(x4,y4),(x1,y1)]), fill=textColor, width = 5)
        if row['Play'] in listSecond:
            card_draw.line(([(x1,y1),(x2,y2)]), fill=textColor, width = 5)
        if row['Play'] in listThird:
            card_draw.line(([(x2,y2),(x3,y3)]), fill=textColor, width = 5)
        if row['Play'] in listHome:
            card_draw.line(([(x3,y3),(x4,y4)]), fill=textColor, width = 5)



sw = 131                    # Width of the boxscore box
sh = 126                    # Height of the boxscore box

## Set up fonts
s3 = boto3.client('s3')
s3.download_file('gtpdd', 'bsbScorecardTemplate.jpg', '/tmp/bsbScorecardTemplate.jpg')
s3.download_file('gtpdd', 'fontCassetteTapes.ttf', '/tmp/fontCassetteTapes.ttf')
s3.download_file('gtpdd', 'fontOswald.ttf', '/tmp/fontOswald.ttf')


font_path = '/tmp/fontCassetteTapes.ttf'
font2_path = '/tmp/fontOswald.ttf'
global large_name_font
global large_title_font
global name_font
global play_font
global bs_font
global title_font
large_name_font = ImageFont.truetype(font2_path, 50)
large_title_font = ImageFont.truetype(font2_path, 70)
name_font = ImageFont.truetype(font_path, 40)
play_font = ImageFont.truetype(font_path, 35)
bs_font = ImageFont.truetype(font_path, 30)
title_font = ImageFont.truetype(font2_path, 18)

###
# GET THE GAMES WE NEED TO INCLUDE
###

## FUTURE: Right now, this just looks back x number of days. 
### In the future, it needs to see autograb just games from the same series

## Get list of all previous game box scores
games_soup = Soup((requests.get('https://latechsports.com/sports/baseball/schedule')).text, features="lxml")
box_scores = []
box_dates = []
lis = games_soup.find_all('li', {"class":"sidearm-schedule-game-links-boxscore"})
for li in lis:
    box_scores.append(li.a.get("href"))
    box_dates.append(li.a.get("aria-label"))
box_scores = list(dict.fromkeys(box_scores))
box_dates = list(dict.fromkeys(box_dates))

## Find the last box score
last_box = box_scores[-1]
last_date = box_dates[-1]

## Get the team and date listed in the most recent game
last_team = (last_box.split('2024/'))[1].split('/boxscore')[0]
last_date = (last_date.split(' on '))[1].split(' at')[0]

## Make sure the last game played was from this past weekend
today = datetime.now()
last_datetime = datetime.strptime(last_date, "%B %d, %Y")
time_dif = today - last_datetime
if time_dif.days > 5:
    quit()

## Reverse the order of the list
box_scores.reverse()
box_dates.reverse()

## Add all the games from this week
last_scores = []
today = datetime.now()

i = 0
for box_date in box_dates:
    date = (box_date.split(' on '))[1].split(' at')[0]
    date_datetime = datetime.strptime(date, "%B %d, %Y")
    time_dif = today - date_datetime
    if time_dif.days < 5:
        last_scores.append(box_scores[i])
    i = i + 1
    
###
# GET DATA FROM BOXSCORES
###
    
## Create a list of dataframes, one for each game of the series for both hitting stats and pbp
hit_stat_dfs = []
pbp_dfs = []
last_scores.reverse()
for score in last_scores:
    hit_stat_dfs.append(get_hitting_stats(score))
    awayName,homeName,away_df,home_df = getBoxScore(score,'batter')
    if awayName in ['LA TECH', 'Louisiana Tech', 'LA Tech']:
        pbp_dfs.append(away_df)
        opponent = homeName
    elif homeName in ['LA TECH', 'Louisiana Tech', 'LA Tech']:
        pbp_dfs.append(home_df)
        opponent = awayName
    else:
        print('Tech not found. Team names are: ' + awayName + ' ' + homeName)
        quit()


## Combine the hitting stats dataframes into one for the weekend
weekend_df = hit_stat_dfs[0]
for x in range(1,len(hit_stat_dfs)):
    weekend_df = weekend_df.add(hit_stat_dfs[x], fill_value=0)
weekend_df['AVG'] = weekend_df['H'] / weekend_df['AB']
weekend_df['XBH'] = weekend_df['2B'] + weekend_df['3B'] + weekend_df['HR']
weekend_df['PA'] = (weekend_df['AB'] + weekend_df['BB'] + weekend_df['HBP'])
weekend_df['OBP'] = (weekend_df['H'] + weekend_df['BB'] + weekend_df['HBP']) / (weekend_df['AB'] + weekend_df['BB'] + weekend_df['HBP'])
weekend_df['SLG'] = ((weekend_df['H']-weekend_df['2B']-weekend_df['3B']-weekend_df['HR']) + (2*weekend_df['2B']) + (3*weekend_df['3B']) + (4*weekend_df['HR']))/weekend_df['AB']
weekend_df['OPS'] = weekend_df['OBP'] + weekend_df['SLG']
weekend_df = weekend_df.fillna(0)
weekend_df['AVG'] = weekend_df['AVG'].map('{:,.3f}'.format)
weekend_df['OBP'] = weekend_df['OBP'].map('{:,.3f}'.format)
weekend_df['SLG'] = weekend_df['SLG'].map('{:,.3f}'.format)
weekend_df['OPS'] = weekend_df['OPS'].map('{:,.3f}'.format)
weekend_df = weekend_df.astype({"AB": int, "H": int, "BB": int, "2B": int, "3B": int, "HR": int, "RBI": int})
weekend_df = weekend_df[['OPS','PA','AB','H','BB','2B','3B','HR','RBI','AVG','OBP','SLG',]]
weekend_df = weekend_df.sort_values(by='OPS', ascending=False)

## Combine the pbp dataframes into one for the series
for i in range(0,len(pbp_dfs)):
    pbp_dfs[i]['Game'] = i

pbp_df = pd.concat(pbp_dfs)
pbp_df = pbp_df.reset_index(drop=True)
pbp_df['Name'] = pbp_df['Name'].str.split('-').str[0]
pbp_df['Name'] = pbp_df['Name'].str.split(',').str[0]
print(pbp_df.loc[pbp_df['Name'] == 'Furr'])


## Grab the individual pbp dfs for each player, in order of OPS (from weekend_df)
names = []
indv_dfs = []
for index,row in weekend_df.iterrows():
    name = str(index)#.upper()
    print(name)
    names.append(name)
    indv_dfs.append(pbp_df.loc[pbp_df['Name'] == name])


###
# GENERATE EMPTY SCORECARD
###

l_gap = 220
t_gap = 220
players = len(weekend_df.index)
pa = weekend_df['PA'].max()    
s3.download_file('gtpdd', 'bsbScorecardSingle.jpg', '/tmp/bsbScorecardSingle.jpg')
single = Image.open('/tmp/bsbScorecardSingle.jpg')
card = Image.new(single.mode, (int(l_gap+sw*pa), int(t_gap+sh*players)), 'black')      
card_draw = ImageDraw.Draw(card)


###
# PRINT ON SCORECARD
###

## Set some iterable variables
r = 0
start_w = l_gap
start_h = t_gap
colors = ['pinstripe','white','blue']

## Print title info
card_draw.text((l_gap,5),'Baseball Series Recap', font=large_title_font)
card_draw.text((l_gap,80),'Scorecard Abomination', font=large_name_font)

## Print Team Logo
box = [(950, 28), (950+111, 28+111)] 
card_draw.rectangle(box, fill ='black', outline ="white", width=5)
logo = Image.open('/tmp/' + opponent + '.png')
logo = logo.resize((111,111))
card.paste(logo, (950,28),logo)
card_draw.text((948,144),'GAMES AGAINST', font=title_font)

## Print the Sample Squares
for i in range(0,len(colors)):
    if colors[i] == 'blue':
        s3.download_file('gtpdd', 'bsbScorecardSingleBlue.jpg', '/tmp/bsbScorecardSingleBlue.jpg')
        single = Image.open('/tmp/bsbScorecardSingleBlue.jpg')
    elif colors[i] == 'gray':
        s3.download_file('gtpdd', 'bsbScorecardSingleGrey.jpg', '/tmp/bsbScorecardSingleGrey.jpg')
        single = Image.open('/tmp/bsbScorecardSingleGrey.jpg')
    elif colors[i] == 'red':
        s3.download_file('gtpdd', 'bsbScorecardSingleRed.jpg', '/tmp/bsbScorecardSingleRed.jpg')
        single = Image.open('/tmp/bsbScorecardSingleRed.jpg')
    elif colors[i] == 'sky':
        s3.download_file('gtpdd', 'bsbScorecardSingleSky.jpg', '/tmp/bsbScorecardSingleSky.jpg')
        single = Image.open('/tmp/bsbScorecardSingleSky.jpg')
    elif colors[i] == 'white':
        s3.download_file('gtpdd', 'bsbScorecardSingleWhite.jpg', '/tmp/bsbScorecardSingleWhite.jpg')
        single = Image.open('/tmp/bsbScorecardSingleWhite.jpg')
    elif colors[i] == 'pinstripe':
        s3.download_file('gtpdd', 'bsbScorecardSinglePinstripe.jpg', '/tmp/bsbScorecardSinglePinstripe.jpg')
        single = Image.open('/tmp/bsbScorecardSinglePinstripe.jpg')

    single = single.resize((115,111))
    card.paste(single, (1100+115*i,28))
    card_draw.text((1130+115*i,144),'GAME '+ str(i+1), font=title_font)

## Print the lines
for r in range(0,players):
#for r in range(0,2):
    
    ## Print player name
    card_draw.text((10,t_gap+r*sh),weekend_df.index.values[r], font=large_name_font)
    card_draw.text((10,t_gap+r*sh+69),'OPS: ' + weekend_df['OPS'][r], font=title_font)
    card_draw.text((10,t_gap+r*sh+90),weekend_df['AVG'][r]+'/'+weekend_df['OBP'][r]+'/'+weekend_df['SLG'][r], font=title_font)
        
    h = start_h + sh * r
    df = indv_dfs[r]
    play_list = []
    w = start_w
    color = colors[0]
    
    for index, row in df.iterrows():            
        
        # Check if hit or movement. Iterate the coordinates if hit
        if not row['Play'].startswith(('z','x','SB')):
            if play_list: 
                generateScorecardSquare(card,card_draw,color,play_list,w,h,sw,sh)
                w = w + sw
            play_list = []
            play_list.append(row)
    
        else:
            play_list.append(row)
        color = colors[row['Game']]

            
    ## We need to run it one more time to get the last square    
    #generateScorecardSquare(card,card_draw,color,play_list,w,h,sw,sh)

card.save('/tmp/bsbWeeklyRecap.png')
s3.upload_file('/tmp/bsbWeeklyRecap.png', 'gtpdd', 'bsbWeeklyRecap.png')