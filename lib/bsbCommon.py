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
import tweepy
from datetime import datetime, timedelta
from PIL import Image, ImageFont, ImageDraw, ImageColor
import re
import boto3

def parse_row(row):
    return [str(x.string) for x in row.find_all(string=True)]

def parse_row_0(row):
    return [str(x.string) for x in row.find_all(string=True)][0]

def parse_tda_row(row):
    return [str(x.string) for x in row.find_all(['td','a'])]

def getBoxScore(box_score, returnType):
    box_url = 'https://latechsports.com' + str(box_score)
    oppo = box_score.split('2024/')[1].split('/boxscore')[0]
    box_soup = Soup((requests.get(box_url)).text, features="lxml")
    tables = box_soup.find_all('table')
    
    ## Figure out home and away
    away_bat = tables[len(tables) - 2]
    home_bat = tables[len(tables) - 1]
    awayPitch = tables[4]
    homePitch = tables[5]
    team_names = tables[0].find_all('span')
    list_of_parsed_rows = [parse_row(row) for row in team_names[1:]]
    
    list_of_parsed_rows = [str(i)[2:-2] for i in list_of_parsed_rows]
    list_of_parsed_rows = [i for i in list_of_parsed_rows if 'Winner' not in i]
    list_of_parsed_rows = [i for i in list_of_parsed_rows if 'TECH' != i]
    
    if len(list_of_parsed_rows) == 3:
        lens = []
        for row in list_of_parsed_rows:
            lens.append(len(row))
        del list_of_parsed_rows[lens.index(min(lens))]
    
    awayName = str(list_of_parsed_rows[0])
    homeName = str(list_of_parsed_rows[1])
    
    print(awayName,homeName)
    
    ## Download Team Logos
    s3 = boto3.client('s3')
    s3.download_file('gtpdd', 'espnTeamIDs.csv', '/tmp/espnTeamIDs.csv')
    color_csv = csv.reader(open('/tmp/espnTeamIDs.csv', 'r'), delimiter = ',', quotechar="\"")
    
    for row in color_csv:
        if row[0] == awayName: awayCode = row[1]
        elif row[0] == homeName: homeCode = row[1]
    
    vlogo = 'https://a.espncdn.com/i/teamlogos/ncaa/500/' + awayCode + '.png'
    vlogo_r = r = requests.get(vlogo)
    hlogo = 'https://a.espncdn.com/i/teamlogos/ncaa/500/' + homeCode + '.png'
    hlogo_r = r = requests.get(hlogo)
    
    open( '/tmp/' + awayName + '.png', 'wb').write(vlogo_r.content)
    open( '/tmp/' + homeName + '.png', 'wb').write(hlogo_r.content)
    
    ## Get game info
    dls = box_soup.find_all('dl', {"class": "special-stats emphasize inline text-right"})
    info_dl = box_soup.find_all('dl')[1]
    rows = info_dl.find_all('dd')
    list_of_parsed_rows = [parse_row_0(row) for row in rows]
    
    date = list_of_parsed_rows[0]
    startTime = list_of_parsed_rows[1]
    elapsedTime = list_of_parsed_rows[2]
    
    if list_of_parsed_rows[3][0].isdigit():
        attendance = list_of_parsed_rows[3]
        location = list_of_parsed_rows[4]
        weather = list_of_parsed_rows[5]
        
    else:
        attendance = ''
        location = list_of_parsed_rows[3]
        weather = list_of_parsed_rows[4]
    
    ## Grab the correct PBP and inning stat frames
    away_tables = []
    home_tables = []
    away_dls = []
    home_dls = []
    
    innings = int((len(tables)-8)/2)
    for i in range(7,innings+7):
        if (i % 2): away_tables.append(tables[i])
        else: home_tables.append(tables[i])
    for i in range(0,len(dls)):
        if (i % 2): home_dls.append(dls[i])
        else: away_dls.append(dls[i])
        
    ## Get pitcher stats
    def getPitcherStats(pitch):
        pitchstat_rows = pitch.find_all('tr')
        list_of_parsed_rows = [parse_row(row) for row in pitchstat_rows[1:]]
        pitcher_df = DataFrame(list_of_parsed_rows)
        pitcher_df = pitcher_df.replace(r'\r','',regex=True)
        pitcher_df = pitcher_df.replace(r'\n','',regex=True)
        pitcher_df.dropna(inplace=True, axis=1, how='all')
        for i in range(0,len(pitcher_df.columns)):
            pitcher_df[i] = pitcher_df[i].str.strip()
        pitcher_df[1] =  pitcher_df[1] + ' ' + pitcher_df[2]
        pitcher_df =  pitcher_df.drop(pitcher_df.columns[[0,2]],axis = 1)
        pitcher_df =  pitcher_df.drop(pitcher_df.columns[[-1,-3,-5,-7,-9,-11,-13,-15,-17,-19,-21,-23,-25,-27,-29]],axis = 1)
        if len(pitcher_df.columns) == 17:
            pitcher_df =  pitcher_df.drop(pitcher_df.columns[1],axis = 1)
        pitcher_df = pitcher_df[:-1]
        return pitcher_df
        
    away_pitcher_df = getPitcherStats(awayPitch)
    home_pitcher_df = getPitcherStats(homePitch)
    
    
    ## Create inning stat lists for both teams
    home_runs = []; home_hits = []; home_errors = []; home_lob = []
    away_runs = []; away_hits = []; away_errors = []; away_lob = []
    
    for dl in home_dls:
        try:
            rows = dl.find_all('dd')
            list_of_parsed_rows = [parse_row_0(row) for row in rows]
            home_runs.append(int(list_of_parsed_rows[0]))
            home_hits.append(int(list_of_parsed_rows[1]))
            home_errors.append(int(list_of_parsed_rows[2]))
            home_lob.append(int(list_of_parsed_rows[3]))
        except: 0
        
    for dl in away_dls:
        try:
            rows = dl.find_all('dd')
            list_of_parsed_rows = [parse_row_0(row) for row in rows]
            away_runs.append(int(list_of_parsed_rows[0]))
            away_hits.append(int(list_of_parsed_rows[1]))
            away_errors.append(int(list_of_parsed_rows[2]))
            away_lob.append(int(list_of_parsed_rows[3]))
        except: 0
        
    ## Create dataframes
    home_dfs = []
    away_dfs = []
    
    for table in home_tables:
        rows = table.find_all('tr')
        list_of_parsed_rows = [parse_tda_row(row) for row in rows[1:]]
        try:home_dfs.append(DataFrame(list_of_parsed_rows)[0])
        except:0
    for table in away_tables:
        rows = table.find_all('tr')
        list_of_parsed_rows = [parse_tda_row(row) for row in rows[1:]]
        away_dfs.append(DataFrame(list_of_parsed_rows)[0])
        
    ## Go line-by-line through dfs
    home_df = pbpLineByLine(home_dfs)
    away_df = pbpLineByLine(away_dfs)
    
    if returnType == 'full':
        return awayName,homeName, \
        date,startTime,elapsedTime,attendance,location,weather, \
        away_df,away_pitcher_df,away_bat,away_runs,away_hits,away_errors,away_lob, \
        home_df,home_pitcher_df,home_bat,home_runs,home_hits,home_errors,home_lob
    
    elif returnType == 'batter':
        return awayName,homeName,away_df,home_df

def pbpLineByLine(dfs):
    for i in range(0,len(dfs)):

        dfs[i] =  dfs[i].to_frame()
        dfs[i] =  dfs[i].replace(to_replace=r"[A-Z]\. ([A-Za-z]+) Jr\.", value=r"\1", regex=True)
        dfs[i] =  dfs[i].replace(to_replace=r"[A-Z]\. ([A-Z]+)", value=r"\1", regex=True)
        dfs[i] =  dfs[i].replace(to_replace=r"([A-Za-z]+), ([A-Z])\.", value=r"\1-\2", regex=True)
        dfs[i] =  dfs[i].replace(to_replace=r"([A-Za-z]+), ([A-Z])", value=r"\1-\2", regex=True)
        dfs[i] =  dfs[i].replace(to_replace=r"([A-Za-z]+) ([A-Z]) ", value=r"\1-\2 ", regex=True)         ## Required for ULM 3/15/2022
        dfs[i] =  dfs[i].replace(to_replace=r"([A-Za-z]+) Jr., [A-Z]\.", value=r"\1", regex=True)
        dfs[i] =  dfs[i].replace(to_replace=r"([A-Za-z]+), [A-Z][a-z]", value=r"\1", regex=True)
        
        dfs[i] = dfs[i][dfs[i][0].str.contains("Additional")==False]
        dfs[i] = dfs[i][dfs[i][0].str.contains("No play")==False]
        dfs[i] = dfs[i][dfs[i][0].str.contains("Dropped foul ball")==False]
        dfs[i] = dfs[i][dfs[i][0].str.contains("pinch hit for")==False]
        dfs[i] = dfs[i][dfs[i][0].str.contains("to [0-9a-z]+ for")==False]
        dfs[i] = dfs[i][dfs[i][0].str.contains("Mound Visit")==False]
        dfs[i] = dfs[i][dfs[i][0].str.contains("wearing")==False]
        dfs[i] = dfs[i][dfs[i][0].str.contains("/  for")==False]
        dfs[i] = dfs[i][dfs[i][0].str.contains("/ for")==False]

        ## Split out columns for name and play
        dfs[i]['Inning'] = i+1
        dfs[i]['Name'] = dfs[i][0].str.split(" ",n=1).str[0]
        dfs[i]['Play'] = dfs[i][0].str.split(" ",n=1).str[1]
        dfs[i] = dfs[i].drop(columns=[0])
        
        ## Split rows where more than one action happens
        dfs[i]['Play'] = dfs[i]['Play'].str.split('; ')
        dfs[i] = dfs[i].explode('Play').reset_index()
        dfs[i] = dfs[i].drop('index', axis=1)
                            
        ## Try to split out Count and Pitches columns if possible
        try: dfs[i]['Count'] = dfs[i]['Play'].str.split("(",n=1).str[1]
        except: dfs[i]['Count'] = ''
        
        try: dfs[i]['Pitches'] = dfs[i]['Count'].str.split(" ",n=1).str[1]
        except: dfs[i]['Pitches'] = ''
                
        ## Do some cleanup
        dfs[i]['Play'] = dfs[i]['Play'].str.replace(r'\(.*', '', regex=True)
        try: dfs[i]['Count'] = dfs[i]['Count'].str.replace(r' .*', '', regex=True)
        except: 0
        try: dfs[i]['Pitches'] = dfs[i]['Pitches'].str.replace(r'\).*', '', regex=True)
        except: 0
            
    ## Combine the inning dfs    
    df = pd.concat(dfs)
    
    ## Do some more cleanup    
    for index, row in df.iterrows():
        if ');' in str(row['Count']): row['Count'] = row['Count'][:3]; row['Pitches'] = ''
        if ').' in str(row['Count']): row['Count'] = row['Count'][:3]; row['Pitches'] = ''
        
    ## Standardize playcalling
    df = df.replace(to_replace ='struck out looking.*', value = '!K', regex = True)
    df = df.replace(to_replace ='struck out swinging.*', value = 'K', regex = True)
    df = df.replace(to_replace ='struck out.*', value = 'K', regex = True)
    df = df.replace(to_replace ='singled.*', value = '1B', regex = True)
    df = df.replace(to_replace ='doubled.*', value = '2B', regex = True)
    df = df.replace(to_replace ='tripled.*', value = '3B', regex = True)
    df = df.replace(to_replace ='flied out to p.*', value = 'F1', regex = True)
    df = df.replace(to_replace ='flied out to c.*', value = 'F2', regex = True)
    df = df.replace(to_replace ='flied out to 1b.*', value = 'F3', regex = True)
    df = df.replace(to_replace ='flied out to 2b.*', value = 'F4', regex = True)
    df = df.replace(to_replace ='flied out to 3b.*', value = 'F5', regex = True)
    df = df.replace(to_replace ='flied out to ss.*', value = 'F6', regex = True)
    df = df.replace(to_replace ='flied out to lf.*', value = 'F7', regex = True)
    df = df.replace(to_replace ='flied out to cf.*', value = 'F8', regex = True)
    df = df.replace(to_replace ='flied out to rf.*', value = 'F9', regex = True)
    df = df.replace(to_replace ='popped up to p.*', value = 'F1', regex = True)
    df = df.replace(to_replace ='popped up to c.*', value = 'F2', regex = True)
    df = df.replace(to_replace ='popped up to 1b.*', value = 'F3', regex = True)
    df = df.replace(to_replace ='popped up to 2b.*', value = 'F4', regex = True)
    df = df.replace(to_replace ='popped up to 3b.*', value = 'F5', regex = True)
    df = df.replace(to_replace ='popped up to ss.*', value = 'F6', regex = True)
    df = df.replace(to_replace ='popped up to lf.*', value = 'F7', regex = True)
    df = df.replace(to_replace ='popped up to cf.*', value = 'F8', regex = True)
    df = df.replace(to_replace ='popped up to rf.*', value = 'F9', regex = True)
    df = df.replace(to_replace ='fouled out to p.*', value = 'f1', regex = True)
    df = df.replace(to_replace ='fouled out to c.*', value = 'f2', regex = True)
    df = df.replace(to_replace ='fouled out to 1b.*', value = 'f3', regex = True)
    df = df.replace(to_replace ='fouled out to 2b.*', value = 'f4', regex = True)
    df = df.replace(to_replace ='fouled out to 3b.*', value = 'f5', regex = True)
    df = df.replace(to_replace ='fouled out to ss.*', value = 'f6', regex = True)
    df = df.replace(to_replace ='fouled out to lf.*', value = 'f7', regex = True)
    df = df.replace(to_replace ='fouled out to cf.*', value = 'f8', regex = True)
    df = df.replace(to_replace ='fouled out to rf.*', value = 'f9', regex = True)
    df = df.replace(to_replace ='lined out to p.*', value = 'L1', regex = True)
    df = df.replace(to_replace ='lined out to c.*', value = 'L2', regex = True)
    df = df.replace(to_replace ='lined out to 1b.*', value = 'L3', regex = True)
    df = df.replace(to_replace ='lined out to 2b.*', value = 'L4', regex = True)
    df = df.replace(to_replace ='lined out to 3b.*', value = 'L5', regex = True)
    df = df.replace(to_replace ='lined out to ss.*', value = 'L6', regex = True)
    df = df.replace(to_replace ='lined out to lf.*', value = 'L7', regex = True)
    df = df.replace(to_replace ='lined out to cf.*', value = 'L8', regex = True)
    df = df.replace(to_replace ='lined out to rf.*', value = 'L9', regex = True)
    df = df.replace(to_replace ='grounded out to p unassisted.*', value = '1u', regex = True)
    df = df.replace(to_replace ='grounded out to c unassisted.*', value = '2u', regex = True)
    df = df.replace(to_replace ='grounded out to 1b unassisted.*', value = '3u', regex = True)
    df = df.replace(to_replace ='grounded out to 2b unassisted.*', value = '4u', regex = True)
    df = df.replace(to_replace ='grounded out to 3b unassisted.*', value = '5u', regex = True)
    df = df.replace(to_replace ='grounded out to ss unassisted.*', value = '6u', regex = True)
    df = df.replace(to_replace ='grounded out to lf unassisted.*', value = '7u', regex = True)
    df = df.replace(to_replace ='grounded out to cf unassisted.*', value = '8u', regex = True)
    df = df.replace(to_replace ='grounded out to rf unassisted.*', value = '9u', regex = True)
    df = df.replace(to_replace ='grounded out to p.*', value = '1-3', regex = True)
    df = df.replace(to_replace ='grounded out to c.*', value = '2-3', regex = True)
    df = df.replace(to_replace ='grounded out to 1b.*', value = '3u', regex = True)
    df = df.replace(to_replace ='grounded out to 2b.*', value = '4-3', regex = True)
    df = df.replace(to_replace ='grounded out to 3b.*', value = '5-3', regex = True)
    df = df.replace(to_replace ='grounded out to ss.*', value = '6-3', regex = True)
    df = df.replace(to_replace ='grounded out to lf.*', value = '7-3', regex = True)
    df = df.replace(to_replace ='grounded out to cf.*', value = '8-3', regex = True)
    df = df.replace(to_replace ='grounded out to rf.*', value = '9-3', regex = True)
    df = df.replace(to_replace ='grounded into double play 2b to ss to 1b.*', value = '4-6-3', regex = True)
    df = df.replace(to_replace ='grounded into double play ss to 2b to 1b.*', value = '6-4-3', regex = True)
    df = df.replace(to_replace ='grounded into double play 3b to 2b to 1b.*', value = '5-4-3', regex = True)
    df = df.replace(to_replace ='grounded into double play 3b to ss to 1b.*', value = '5-6-3', regex = True)
    df = df.replace(to_replace ='grounded into double play ss to 1b.*', value = '6-3', regex = True)
    df = df.replace(to_replace ='grounded into double play 2b to 1b.*', value = '4-3', regex = True)
    df = df.replace(to_replace ='grounded into double play 3b to 1b.*', value = '5-3', regex = True)
    df = df.replace(to_replace ='grounded into double play 2b to ss.*', value = '4-6', regex = True)
    df = df.replace(to_replace ='grounded into double play 1b to ss.*', value = '3-6', regex = True)
    df = df.replace(to_replace ='grounded into double play 1b to 2b.*', value = '3-4', regex = True)
    df = df.replace(to_replace ='grounded into double play ss to 2b to c to 2b.*', value = '6-4-2-4', regex = True)
    df = df.replace(to_replace ='hit into double play 2b to ss to 1b.*', value = '4-6-3', regex = True)
    df = df.replace(to_replace ='hit into double play ss to 2b to 1b.*', value = '6-4-3', regex = True)
    df = df.replace(to_replace ='hit into double play 3b to 2b to 1b.*', value = '5-4-3', regex = True)
    df = df.replace(to_replace ='hit into double play 3b to ss to 1b.*', value = '5-6-3', regex = True)
    df = df.replace(to_replace ='hit into double play ss to 1b.*', value = '6-3', regex = True)
    df = df.replace(to_replace ='hit into double play 2b to 1b.*', value = '4-3', regex = True)
    df = df.replace(to_replace ='hit into double play 3b to 1b.*', value = '5-3', regex = True)
    df = df.replace(to_replace ='lined into double play 3b to 1b.*', value = '5-3', regex = True)
    df = df.replace(to_replace ='lined into double play cf to 1b.*', value = '8-3', regex = True)
    df = df.replace(to_replace ='lined into double play ss to 1b.*', value = '6-3', regex = True)
    df = df.replace(to_replace ='out at first 2b to p.*', value = '4-1', regex = True)
    df = df.replace(to_replace ='out at first 1b to p.*', value = '3-1', regex = True)
    df = df.replace(to_replace ='out at first.*bunt.*', value = 'SH', regex = True)
    df = df.replace(to_replace ="out on batter's interference.*", value = 'BI', regex = True)
    df = df.replace(to_replace ="reached on catcher's interference.*", value = 'E2', regex = True)
    df = df.replace(to_replace ='homered.*', value = 'HR', regex = True)
    df = df.replace(to_replace ='walked.*', value = 'BB', regex = True)
    df = df.replace(to_replace ='intentionally BB.*', value = 'IBB', regex = True)
    df = df.replace(to_replace ='hit by pitch.*', value = 'HBP', regex = True)
    df = df.replace(to_replace ="reached on a fielder's choice.*", value = 'FC', regex = True)
    df = df.replace(to_replace ="reached.*error.*", value = 'E', regex = True)
    df = df.replace(to_replace ="stole second, advanced to third.*", value = 'SB3', regex = True)
    df = df.replace(to_replace ="stole second.*", value = 'SB2', regex = True)
    df = df.replace(to_replace ="stole third.*", value = 'SB3', regex = True)
    df = df.replace(to_replace ="stole home.*", value = 'SB4', regex = True)
    df = df.replace(to_replace ="out at first.*", value = 'x1', regex = True)
    df = df.replace(to_replace ='picked off, out at second.*', value = 'x2', regex = True)
    df = df.replace(to_replace ="out at second.*", value = 'x2', regex = True)
    df = df.replace(to_replace ="out at third.*", value = 'x3', regex = True)
    df = df.replace(to_replace ="reached.*advanced to second.*", value = 'E', regex = True)
    df = df.replace(to_replace ="reached.*", value = 'E', regex = True)       
    df = df.replace(to_replace ="scored on a wild pitch.*", value = 'z4WP', regex = True)
    df = df.replace(to_replace ="scored.*", value = 'z4', regex = True)
    df = df.replace(to_replace ="flied into double play rf to 1b .*", value = 'F9', regex = True)
    df = df.replace(to_replace ="lined into double play 1b unassisted.*", value = '3u', regex = True)
    df = df.replace(to_replace ="lined into double play 2b unassisted.*", value = '4u', regex = True)
    df = df.replace(to_replace ="lined into double play 3b unassisted.*", value = '5u', regex = True)
    df = df.replace(to_replace ="lined into double play ss unassisted.*", value = '6u', regex = True)
    df = df.replace(to_replace ="lined into double play p to 1b.*", value = '1-3', regex = True)
    
    df = df[df['Play'].notna()]
    df = df[~df.Play.str.startswith('to',  na=False)]
    #df = df[~df.Play.str.contains(' for ',  na=False)]
    
    ## This should leave just runner actions
    ## Get name from runner action into Name column
    df = df.reset_index(drop=True)
    name = ""
    for index, row in df.iterrows():
        if row['Name'] == name:
            try: 
                tempName = row['Play'].split(' ',1)[0]
                if tempName not in ['advanced']:
                    df.loc[index,'Name'], df.loc[index,'Play'] = row['Play'].split(' ', 1)
            except: 0
        name = row['Name']
    
        
    ## Standardize playcalling
    df = df.replace(to_replace ="advanced to second on a wild pitch.*", value = 'z2WP', regex = True)
    df = df.replace(to_replace ="advanced to third on a wild pitch.*", value = 'z3WP', regex = True)
    df = df.replace(to_replace ="scored on a wild pitch.*", value = 'z4WP', regex = True)
    
    df = df.replace(to_replace ="advanced to second.*", value = 'z2', regex = True)
    df = df.replace(to_replace ="advanced to third.*", value = 'z3', regex = True)
    df = df.replace(to_replace ="scored.*", value = 'z4', regex = True)
    
    df = df.replace(to_replace ="picked off.*", value = 'x1', regex = True)
    df = df.replace(to_replace ="out at second.*", value = 'x2', regex = True)
    df = df.replace(to_replace ="out on the play.*", value = 'x2', regex = True)
    df = df.replace(to_replace ="out at third.*", value = 'x3', regex = True)
    df = df.replace(to_replace ="out at home.*", value = 'x4', regex = True)
        
    return df