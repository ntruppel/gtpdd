# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup as Soup
import requests
import numpy as np
import pandas as pd
from pandas import DataFrame
import matplotlib
import matplotlib.pyplot as plt
import six
import csv
from datetime import datetime, timedelta
from PIL import Image, ImageFont, ImageDraw, ImageColor
import re
from lib.bsbCommon import pbpLineByLine, getBoxScore
from lib.common import parseRowStringTextTrue,parseRowStringTdA
#####
# Get PbP Data
####

## Get list of all previous game box scores
games_soup = Soup((requests.get('https://latechsports.com/sports/baseball/schedule')).text, features="lxml")
box_scores = []
lis = games_soup.find_all('li', {"class":"sidearm-schedule-game-links-boxscore"})
for li in lis:
    box_scores.append(li.a.get("href"))
box_scores = list(dict.fromkeys(box_scores))

## Pull down raw data
box_score = box_scores[-1]

awayName,homeName, \
date,startTime,elapsedTime,attendance,location,weather, \
away_df,away_pitcher_df,away_bat,away_runs,away_hits,away_errors,away_lob, \
home_df,home_pitcher_df,home_bat,home_runs,home_hits,home_errors,home_lob = getBoxScore(box_score,'full')


####
# Print on Scorecard
####

## Set some variables
nameWidth = 102
playWidth1 = 403
nameRow1 = 335
playRow1 = 378
rowDelta = 119
colDelta = 126

textColor = 'black'
errColor = 'red'

diamondH = [432,440]
diamond1 = [462,410]
diamond2 = [432,380]
diamond3 = [401,410]

## Open scorecard
## TODO: Get number of innings and open correct scorecard file

img1 = Image.open('img/bsbScorecardBlank9Innings.jpg')
card1 = ImageDraw.Draw(img1)
img2 = Image.open('img/bsbScorecardBlank9Innings.jpg')
card2 = ImageDraw.Draw(img2)
font_path = 'lib/font/fontCassetteTapes.ttf'
font2_path = 'lib/font/fontOswald.ttf'
name_font = ImageFont.truetype(font_path, 40)
play_font = ImageFont.truetype(font_path, 35)
bs_font = ImageFont.truetype(font_path, 30)
title_font = ImageFont.truetype(font2_path, 18)

def printScorecard(card,df,bat, runs, hits, errors, lobs, homeName, awayName, homeAway, pitcher_df):
    order = 0
    batters = []
    p_counter_list = [0]*9
    ## FUTURE: Replace the 9 with the number of innings
    inning_batter_counter = [0]*20
    bat_around_index = 100
    ## List plays that reach bases
    listHome = ['HR', 'x4WP', 'x4', 'z4', 'z4WP', 'SB4']
    listThird = listHome + ['3B', 'x3', 'x3WP', 'z3', 'z3WP', 'SB3']
    listSecond = listThird + ['2B', 'x2', 'x2WP', 'z2', 'z2WP', 'SB2']
    listFirst = listSecond + ['1B', 'BB', 'HBP', 'E2', 'E', 'FC', 'IBB']
    
    for index, row in df.iterrows():
        ## Check if batter or runner action
        if row['Play'].startswith('z'): 
            orderVar = batters.index(row['Name'])
            
            ## If we hit around later in the inning, need to make sure baserunning is reported in right frame
            ## FUTURE: Right now this only cheks if the batter is the one to first bat around. This logic needs to be improved
            if orderVar != bat_around_index:
                currentInning = row['Inning']
                
        elif row['Play'].startswith('x'): 
            try: orderVar = batters.index(row['Name'])
            except: 0
            ## Print x on chart
            if row['Play'].startswith('x'):
                if row['Play'].startswith('x1'):
                    a1 = diamond1[0] + colDelta*(row['Inning'] - 1) - 7
                    a2 = diamond1[1] + rowDelta*orderVar - 25
                if row['Play'].startswith('x2'):
                    a1 = diamond2[0] + colDelta*(row['Inning'] - 1) - 7
                    a2 = diamond2[1] + rowDelta*orderVar - 25
                if row['Play'].startswith('x3'):
                    a1 = diamond3[0] + colDelta*(row['Inning'] - 1) - 7
                    a2 = diamond3[1] + rowDelta*orderVar - 25
                if row['Play'].startswith('x4'):
                    a1 = diamondH[0] + colDelta*(row['Inning'] - 1) - 7
                    a2 = diamondH[1] + rowDelta*orderVar - 25
                card.text((a1, a2), 'x', font=name_font,fill=errColor)   
                
        elif row['Play'].startswith('SB'): orderVar = batters.index(row['Name'])
        
        ## FUTURE: Remove pitching substitutions earlier        
        elif row['Play'].startswith('to'):
            print(row)
            
        ## We don't need to do anything with pinch hitters, they get recorded anyway
        elif row['Play'].startswith('pinch hit'):
            0
            
        elif row['Play'].startswith('pinch ran'):
            words = row['Play'].split()
            try: o = batters.index(words[-1][:-1])
            except: 
                try: o = batters.index(words[-1])
                except: o = batters.index(words[-2] + '-' + words[-1][:-1])
            batters[o] = row['Name']
            p_counter_list[o] = p_counter_list[o] + 39
            if row['Inning'] > 3:
                card.text((nameWidth, nameRow1+rowDelta*o+p_counter_list[o]), row['Name'] + ' / ' + str(row['Inning']) + 'th', font=name_font,fill=textColor)
            elif row['Inning'] == 3:
                card.text((nameWidth, nameRow1+rowDelta*o+p_counter_list[o]), row['Name'] + ' / ' + str(row['Inning']) + 'rd', font=name_font,fill=textColor)
            elif row['Inning'] == 2:
                card.text((nameWidth, nameRow1+rowDelta*o+p_counter_list[o]), row['Name'] + ' / ' + str(row['Inning']) + 'nd', font=name_font,fill=textColor)
            elif row['Inning'] == 1:
                card.text((nameWidth, nameRow1+rowDelta*o+p_counter_list[o]), row['Name'] + ' / ' + str(row['Inning']) + 'st', font=name_font,fill=textColor)
             
            
        else:
            ## Increase inning batter counter
            inning_batter_counter[row['Inning']] = inning_batter_counter[row['Inning']] + 1
            
            ## If a team bats around, get the index of the switch
            if inning_batter_counter[row['Inning']] == 10:
                bat_around_index = batters.index(row['Name'])
                                
            ## If a team bats around, we need to record on the next inning's column
            if inning_batter_counter[row['Inning']] > 18:
                currentInning = row['Inning'] + 2
                if order == 9: order2 = 0
                else: order2 = order
                card.text((playWidth1+colDelta*(currentInning-1)-50,  playRow1+rowDelta*order2), '<<<<', font=name_font,fill='blue')
            
            elif inning_batter_counter[row['Inning']] > 9:
                currentInning = row['Inning'] + 1
                if order == 9: order2 = 0
                else: order2 = order
                card.text((playWidth1+colDelta*(currentInning-1)-50,  playRow1+rowDelta*order2), '<<<<', font=name_font,fill='blue')
                if row['Inning'] > 3:
                    card.text((playWidth1+colDelta*(currentInning-1)+50,  playRow1+rowDelta*order2-40), str(row['Inning']) + "th", font=bs_font,fill='blue')
                elif row['Inning'] == 3:
                    card.text((playWidth1+colDelta*(currentInning-1)+50,  playRow1+rowDelta*order2-40), str(row['Inning']) + "rd", font=bs_font,fill='blue')
                elif row['Inning'] == 2:
                    card.text((playWidth1+colDelta*(currentInning-1)+50,  playRow1+rowDelta*order2-40), str(row['Inning']) + "nd", font=bs_font,fill='blue')
                elif row['Inning'] == 1:
                    card.text((playWidth1+colDelta*(currentInning-1)+50,  playRow1+rowDelta*order2-40), str(row['Inning']) + "st", font=bs_font,fill='blue')
                
                
            
            
            elif inning_batter_counter[row['Inning']] + inning_batter_counter[row['Inning']-1] > 18:
                currentInning = row['Inning'] + 1
                if order == 9: order2 = 0
                else: order2 = order
                card.text((playWidth1+colDelta*(currentInning-1)-50,  playRow1+rowDelta*order2), '<<<<', font=name_font,fill='blue')
                card.text((playWidth1+colDelta*(currentInning-1)+50,  playRow1+rowDelta*order2-40), str(row['Inning']) + "th", font=bs_font,fill='blue')

            
            else:
                currentInning = row['Inning']
            
            ## Reset order counter if needed
            if order == 9: order = 0
            orderVar = order
    
            ## Check Name
            ## TODO: Find a way to include defensive subs that don't bat
            if row['Name'] not in batters:
                name = row['Name'].split('-')[0]
                if len(batters) < 9:
                    card.text((nameWidth, nameRow1+rowDelta*order), name, font=name_font,fill=textColor)
                    batters.append(row['Name'])
                else:
                    if p_counter_list[order] < 78:
                        p_counter_list[order] = p_counter_list[order] + 39
                        card.text((nameWidth, nameRow1+rowDelta*order+p_counter_list[order]), name + ' / ' + str(row['Inning']) + 'th', font=name_font,fill=textColor)
                    else:
                        card.text((nameWidth-65, nameRow1+rowDelta*order+p_counter_list[order]), '*', font=name_font,fill=textColor)
                        ## 4TH BATTER IN FRAME, removed for now
                        #card.text((nameWidth, nameRow1+rowDelta*10), name + ' / ' + str(currentInning) + 'th', font=name_font,fill=textColor)
                        #card.text((nameWidth-65, nameRow1+rowDelta*10), '*', font=name_font,fill=textColor)

                    batters[order] = row['Name']
                    
            else:
                p_counter = 0
                
            ## Record play
            # Calculate the width and height of the text to be drawn, given font size
            w = card.textlength(row['Play'], font=play_font)
            h = 35

            # Calculate the mid points and offset by the upper left corner of the bounding box
            x1 = playWidth1+colDelta*(currentInning-1)
            x2 = playWidth1+61+colDelta*(currentInning-1)
            y1 = playRow1+rowDelta*order
            y2 = playRow1+61+rowDelta*order
            x = (x2 - x1 - w)/2 + x1
            y = (y2 - y1 - h)/2 + y1
            if row['Play'] in listFirst:
                card.text((x, y), row['Play'], font=play_font,fill=textColor, align='center')
            else:
               card.text((x, y), row['Play'], font=play_font,fill=errColor, align='center') 
            
            ## Increment order counter
            order = order+1
        
        ## Record basepath movement to first
        if row['Play'] in listFirst:
            a1 = diamondH[0] + colDelta*(currentInning - 1)
            a2 = diamondH[1] + rowDelta*orderVar
            b1 = diamond1[0] + colDelta*(currentInning - 1)
            b2 = diamond1[1] + rowDelta*orderVar
            card.line(([(a1,a2),(b1,b2)]), fill=textColor, width = 5)
            
        ## Record basepath movement to second
        if row['Play'] in listSecond:
            a1 = diamond1[0] + colDelta*(currentInning - 1)
            a2 = diamond1[1] + rowDelta*orderVar
            b1 = diamond2[0] + colDelta*(currentInning - 1)
            b2 = diamond2[1] + rowDelta*orderVar
            card.line(([(a1,a2),(b1,b2)]), fill=textColor, width = 5)  
            
        ## Record basepath movement to third
        if row['Play'] in listThird:
            a1 = diamond2[0] + colDelta*(currentInning - 1)
            a2 = diamond2[1] + rowDelta*orderVar
            b1 = diamond3[0] + colDelta*(currentInning - 1)
            b2 = diamond3[1] + rowDelta*orderVar
            card.line(([(a1,a2),(b1,b2)]), fill=textColor, width = 5) 
            
        ## Record basepath movement to home
        if row['Play'] in listHome:
            a1 = diamond3[0] + colDelta*(currentInning - 1)
            a2 = diamond3[1] + rowDelta*orderVar
            b1 = diamondH[0] + colDelta*(currentInning - 1)
            b2 = diamondH[1] + rowDelta*orderVar
            card.line(([(a1,a2),(b1,b2)]), fill=textColor, width = 5)  
            
        ## Set up Balls and Strikes (if they exist)
        try:
            count = str(row['Count'])[:3]
            if count[0].isdigit():
                balls = count[0]
                strikes = count[-1]
        
            ## Loop through balls
            b_w = 370 + colDelta*(currentInning - 1)
            b_h = 330 + rowDelta*orderVar
            i = 0
            while int(balls) > 0:
                card.text((b_w + i, b_h), '/', font=bs_font,fill=textColor)
                balls = int(balls) - 1
                i = i + 22
                
            ## Loop through strikes
            s_w = 370 + colDelta*(currentInning - 1)
            s_h = 351 + rowDelta*orderVar
            i = 0
            while int(strikes) > 0:
                card.text((s_w + i, s_h), '/', font=bs_font,fill=textColor)
                strikes = int(strikes) - 1
                i = i + 22
        except: 0
    
    
    ## Add Player positions and stats
    rows = bat.find_all('tr')
    list_of_parsed_rows = [parseRowStringTdA(row) for row in rows[1:]]
    df = DataFrame(list_of_parsed_rows)
    if len(df.columns) == 21:
        df = df.drop(columns=[2])
    
    df.columns = ['POS','NONE','AB', 'R', 'H', 'RBI', '2B', '3B', 'HR', 'BB', 'SB', 'CS', 'HBP', 'SH', 'SF', 'SO', 'KL', 'GDP', 'PO', 'A']
    
    pos_list = df['POS'].tolist()
    pos_list.remove('None')
    pos_list = [value for value in pos_list if value != 'p']

    ab_list = df['AB'].tolist()[:len(pos_list)]
    r_list = df['R'].tolist()[:len(pos_list)]
    h_list = df['H'].tolist()[:len(pos_list)]
    bb_list = df['BB'].tolist()[:len(pos_list)]
    rbi_list = df['RBI'].tolist()[:len(pos_list)]
    
    
    ## Get which players were subs
    rows = bat.find_all('tr')
    list_of_parsed_rows = [parseRowStringTextTrue(row) for row in rows[1:]]
    df = DataFrame(list_of_parsed_rows)
    
    nosubs_list = df[3].to_list()
    nosubs_list = [i.strip() for i in nosubs_list]

    pos_order = 0
    p_counter = 0
    
    innings_count = 9
    if innings_count in [9,10]:
        ab_length = 1415
        r_length = 1464
        h_length = 1513
        bb_length = 1562
        rbi_length = 1611
    elif innings_count == 11:
        ab_length = 1664
        r_length = 1714
        h_length = 1764
        bb_length = 1814
        rbi_length = 1863

    
    for i in range(0,len(pos_list)):
        if pos_list[i] != nosubs_list[i]:
            if p_counter < 78:
                p_counter = p_counter + 39
                if len(pos_list[i]) < 3:
                    card.text((nameWidth+220, nameRow1+rowDelta*(pos_order-1)+p_counter+5), pos_list[i].upper(), font=play_font,fill=textColor, ha='center')
                else:
                    card.text((nameWidth+215, nameRow1+rowDelta*(pos_order-1)+p_counter+5), pos_list[i].upper(), font=bs_font,fill=textColor, ha='center')

                card.text((nameWidth+ab_length, nameRow1+rowDelta*(pos_order-1)+p_counter), ab_list[i], font=name_font,fill=textColor)
                card.text((nameWidth+r_length, nameRow1+rowDelta*(pos_order-1)+p_counter), r_list[i], font=name_font,fill=textColor)
                card.text((nameWidth+h_length, nameRow1+rowDelta*(pos_order-1)+p_counter), h_list[i], font=name_font,fill=textColor)
                card.text((nameWidth+bb_length, nameRow1+rowDelta*(pos_order-1)+p_counter), bb_list[i], font=name_font,fill=textColor)
                card.text((nameWidth+rbi_length, nameRow1+rowDelta*(pos_order-1)+p_counter), rbi_list[i], font=name_font,fill=textColor)
            
            ## 4TH BATTER ISSUE
            '''
            else:
                if len(pos_list[i]) < 3:
                    card.text((nameWidth+220, nameRow1+rowDelta*10+5), pos_list[i].upper(), font=play_font,fill=textColor)
                else:
                    card.text((nameWidth+215, nameRow1+rowDelta*10+5), pos_list[i].upper(), font=bs_font,fill=textColor)
                card.text((nameWidth+ab_length, nameRow1+rowDelta*10), ab_list[i], font=name_font,fill=textColor)
                card.text((nameWidth+r_length, nameRow1+rowDelta*10), r_list[i], font=name_font,fill=textColor)
                card.text((nameWidth+h_length, nameRow1+rowDelta*10), h_list[i], font=name_font,fill=textColor)
                card.text((nameWidth+bb_length, nameRow1+rowDelta*10), bb_list[i], font=name_font,fill=textColor)
                card.text((nameWidth+rbi_length, nameRow1+rowDelta*10), rbi_list[i], font=name_font,fill=textColor)
            '''
        else:
            p_counter = 0
            if len(pos_list[i]) < 3:
                card.text((nameWidth+220, nameRow1+rowDelta*pos_order+5), pos_list[i].upper(), font=play_font,fill=textColor)
            else:
                card.text((nameWidth+215, nameRow1+rowDelta*pos_order+5), pos_list[i].upper(), font=bs_font,fill=textColor)

            card.text((nameWidth+ab_length, nameRow1+rowDelta*pos_order), ab_list[i], font=name_font,fill=textColor)
            card.text((nameWidth+r_length, nameRow1+rowDelta*pos_order), r_list[i], font=name_font,fill=textColor)
            card.text((nameWidth+h_length, nameRow1+rowDelta*pos_order), h_list[i], font=name_font,fill=textColor)
            card.text((nameWidth+bb_length, nameRow1+rowDelta*pos_order), bb_list[i], font=name_font,fill=textColor)
            card.text((nameWidth+rbi_length, nameRow1+rowDelta*pos_order), rbi_list[i], font=name_font,fill=textColor)
            pos_order = pos_order + 1
            
    ## Add inning stats
    for i in range(0,len(runs)):
        if int(runs[i]) > 0:
            card.text((playWidth1+colDelta*(i)+20, 1450), str(runs[i]), font=name_font,fill=textColor)
        else:
            card.text((playWidth1+colDelta*(i)+20, 1450), str(runs[i]), font=name_font,fill=errColor)
        card.text((playWidth1+colDelta*(i)+20, 1498), str(hits[i]), font=play_font,fill=textColor)
        card.text((playWidth1+colDelta*(i)+20, 1529), str(errors[i]), font=play_font,fill=textColor)
        card.text((playWidth1+colDelta*(i)+20, 1560), str(lobs[i]), font=play_font,fill=textColor)
    
    
    header_rh = 36
    
    ## Add Template Text
    card.text((64, 125), 'Location:', font=title_font, fill=textColor)
    card.text((64, 125 + header_rh * 1), 'Attendance:', font=title_font, fill=textColor)
    card.text((64, 125 + header_rh * 2), 'Weather:', font=title_font, fill=textColor)
    
    card.text((1261, 125), 'Date:', font=title_font, fill=textColor)
    card.text((1261, 125 + header_rh * 1), 'Time:', font=title_font, fill=textColor)
    card.text((1261, 125 + header_rh * 2), 'Game Length:', font=title_font, fill=textColor)
    
    
    ## Add Game Info
    card.text((160, 120), location, font=name_font,fill=textColor)
    card.text((160, 120 + header_rh * 1), attendance, font=name_font,fill=textColor)
    card.text((160, 120 + header_rh * 2), weather, font=name_font,fill=textColor)
    
    card.text((1357, 120), date, font=name_font,fill=textColor)
    card.text((1357, 120 + header_rh * 1), startTime.upper(), font=name_font,fill=textColor)
    card.text((1357, 120 + header_rh * 2), elapsedTime, font=name_font,fill=textColor)
    
    ## FUTURE: Better center this text
    card.text((760 + (14 - len(awayName))*4.5, 224), awayName, font=title_font,fill=textColor)
    card.text((930 + (14 - len(homeName))*4.5, 224), homeName, font=title_font,fill=textColor)
    
    ## Paste logos on card
    away_logo = Image.open('logo/' + awayName + '.png')
    home_logo = Image.open('logo/' + homeName + '.png')
    
    away_logo = away_logo.resize((100,100))
    home_logo = home_logo.resize((100,100))
    
    if homeAway == 'away':        
        img1.paste(away_logo, (764,119), away_logo)
        img1.paste(home_logo.convert('L'), (929,118), home_logo)
        card.text((738, 154), 'X', font=name_font,fill=errColor)

    else:
        img2.paste(away_logo.convert('L'), (764,119), away_logo)
        img2.paste(home_logo, (929,118), home_logo)
        card.text((1047, 153), 'X', font=name_font,fill=errColor)
        
        
        
    ## Print Pitcher Info and Stats
    i = 0
    try:
        pitcher_names = pitcher_df[0].to_list()
    except:
        pitcher_names = pitcher_df[1].to_list()
        
    
    pitcher_df.columns = ['Pitcher', 'IP', 'H', 'R', 'ER', 'BB', 'SO', 'WP', 'BK', 'HBP', 'IBB', 'AB', 'BF', 'FO', 'GO', 'NP']
    p_start_height = 1656

    for pitcher in pitcher_names:
        try: wls = re.search('\(([^)]+)', pitcher).group(1); pitcher = pitcher.split('(')[0]
        except: wls = ""
        ip = pitcher_df.iloc[i]['IP']
        h = pitcher_df.iloc[i]['H']
        r = pitcher_df.iloc[i]['R']
        er = pitcher_df.iloc[i]['ER']
        bb= pitcher_df.iloc[i]['BB']
        so = pitcher_df.iloc[i]['SO']
        wp = pitcher_df.iloc[i]['WP']
        bk = pitcher_df.iloc[i]['BK']
        hbp = pitcher_df.iloc[i]['HBP']
        nump = pitcher_df.iloc[i]['NP']

        card.text((105, p_start_height+i*36), pitcher, font=name_font,fill=textColor)
        if wls.startswith('S'):
            card.text((400, p_start_height+i*36), wls, font=name_font,fill=textColor)
        else:
            card.text((390, p_start_height+i*36), wls, font=name_font,fill=textColor)
        card.text((535, p_start_height+i*36), ip, font=name_font,fill=textColor)
        card.text((673, p_start_height+i*36), h, font=name_font,fill=textColor)
        card.text((673 + 126*1, p_start_height+i*36), r, font=name_font,fill=textColor)
        card.text((673 + 126*2, p_start_height+i*36), er, font=name_font,fill=textColor)
        card.text((673 + 126*3, p_start_height+i*36), bb, font=name_font,fill=textColor)
        card.text((673 + 126*4, p_start_height+i*36), so, font=name_font,fill=textColor)
        card.text((673 + 126*5, p_start_height+i*36), hbp, font=name_font,fill=textColor)
        card.text((673 + 126*6, p_start_height+i*36), bk, font=name_font,fill=textColor)
        card.text((673 + 126*7, p_start_height+i*36), wp, font=name_font,fill=textColor)
        if len(str(nump)) == 3:
            card.text((1671, p_start_height+i*36), nump, font=name_font,fill=textColor)
        elif len(str(nump)) == 2:
            card.text((1676, p_start_height+i*36), nump, font=name_font,fill=textColor)
        else:
            card.text((1683, p_start_height+i*36), nump, font=name_font,fill=textColor)
        i = i + 1
        
    ## Print Template Text
    card.text((nameWidth, 302), 'Player', font=title_font,fill=textColor)
    card.text((nameWidth+220, 302), 'POS', font=title_font,fill=textColor)
    card.text((427, 302), '1', font=title_font,fill=textColor)
    card.text((427 + colDelta*1, 302), '2', font=title_font,fill=textColor)
    card.text((427 + colDelta*2, 302), '3', font=title_font,fill=textColor)
    card.text((427 + colDelta*3, 302), '4', font=title_font,fill=textColor)
    card.text((427 + colDelta*4, 302), '5', font=title_font,fill=textColor)
    card.text((427 + colDelta*5, 302), '6', font=title_font,fill=textColor)
    card.text((427 + colDelta*6, 302), '7', font=title_font,fill=textColor)
    card.text((427 + colDelta*7, 302), '8', font=title_font,fill=textColor)
    card.text((427 + colDelta*8, 302), '9', font=title_font,fill=textColor)
    #card.text((427 + colDelta*9, 302), '10', font=title_font,fill=textColor)
    #card.text((427 + colDelta*10, 302), '11', font=title_font,fill=textColor)
    
    card.text((nameWidth+ab_length-3, 302), 'AB', font=title_font,fill=textColor)
    card.text((nameWidth+r_length, 302), 'R', font=title_font,fill=textColor)
    card.text((nameWidth+h_length, 302), 'H', font=title_font,fill=textColor)
    card.text((nameWidth+bb_length-3, 302), 'BB', font=title_font,fill=textColor)
    card.text((nameWidth+rbi_length-6, 302), 'RBI', font=title_font,fill=textColor)
    
    
    card.text((nameWidth, 1453), 'Runs', font=title_font,fill=textColor)
    card.text((nameWidth, 1501), 'Hits', font=title_font,fill=textColor)
    card.text((nameWidth, 1532), 'Errors', font=title_font,fill=textColor)
    card.text((nameWidth, 1563), 'LOB', font=title_font,fill=textColor)
    
    card.text((nameWidth-32, 1453), 'T\nO\nT\nA\nL', font=title_font,fill=textColor)
 
    p_template_height = 1627
    card.text((105, p_template_height), 'Pitcher', font=title_font,fill=textColor)
    card.text((395, p_template_height), 'W/L/S', font=title_font,fill=textColor)
    card.text((540, p_template_height), 'IP', font=title_font,fill=textColor)
    card.text((673, p_template_height), 'H', font=title_font,fill=textColor)
    card.text((673 + 126*1, p_template_height), 'R', font=title_font,fill=textColor)
    card.text((673 + 126*2 - 5, p_template_height), 'ER', font=title_font,fill=textColor)
    card.text((673 + 126*3 - 5, p_template_height), 'BB', font=title_font,fill=textColor)
    card.text((673 + 126*4 - 5, p_template_height), 'SO', font=title_font,fill=textColor)
    card.text((673 + 126*5 - 10, p_template_height), 'HBP', font=title_font,fill=textColor)
    card.text((673 + 126*6 - 5, p_template_height), 'BK', font=title_font,fill=textColor)
    card.text((673 + 126*7 - 5, p_template_height), 'WP', font=title_font,fill=textColor)
    card.text((1635, p_template_height), 'Pitches Thrown', font=title_font,fill=textColor)
    
    
printScorecard(card1,away_df, away_bat, away_runs, away_hits, away_errors, away_lob, homeName, awayName, 'away', away_pitcher_df)
img1.save('out/bsbScorecardAway.png')
printScorecard(card2,home_df, home_bat, home_runs, home_hits, home_errors, home_lob, homeName, awayName, 'home', home_pitcher_df)
img2.save('out/bsbScorecardHome.png')
