# -*- coding: utf-8 -*-
"""
Created on Wed Jul 12 21:55:37 2023

@author: ntrup
"""
import requests
import pandas as pd
from dateutil import parser, tz

def getHoopsSchedule():
    from_zone = tz.tzutc()
    
    url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams/latech/schedule'

    r = requests.get(url)
    x = r.json()
    
    record = x['team']['recordSummary']
    
    gameIDs = []
    dates = []
    away = []
    home = []
    for game in x['events']:
        gameIDs.append(game['id'])
        z_date = game['date']
        z_datetime = parser.parse(z_date)
        utc = z_datetime.replace(tzinfo=from_zone)
        dates.append(utc)
        away.append(game['competitions'][0]['competitors'][0]['team']['id'])
        home.append(game['competitions'][0]['competitors'][1]['team']['id'])

        
    df = pd.DataFrame({'gameID': gameIDs,'date': dates, 'away':away, 'home':home})
    return df, record

def getESPNAPI(platform, gameId):
    url = 'http://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary?event=' + gameId
    r = requests.get(url)
    x = r.json()
    
    visitorId = x['boxscore']['teams'][0]['team']['id']
    homeId = x['boxscore']['teams'][1]['team']['id']
    
    visitor = x['boxscore']['teams'][0]['team']['location']
    home = x['boxscore']['teams'][1]['team']['location']
    
    v_color = '#' + x['boxscore']['teams'][0]['team']['color']
    v_color2 = '#' + x['boxscore']['teams'][0]['team']['alternateColor']
    h_color = "#" + x['boxscore']['teams'][1]['team']['color']
    h_color2 = '#' + x['boxscore']['teams'][1]['team']['alternateColor']
    
    ## Download Team Logos
    vlogo = x['boxscore']['teams'][0]['team']['logo']
    vlogo_r = r = requests.get(vlogo)
    hlogo = x['boxscore']['teams'][1]['team']['logo']
    hlogo_r = r = requests.get(hlogo)
    
    if platform == 'Windows':
        if visitor not in ['Rice', 'Florida International']:
            open( 'C:\\Users\\ntrup\\Google Drive\\GTPDD\\\\Coding\\in_files\\team_logos\\' + visitor + '.png', 'wb').write(vlogo_r.content)
        if home not in ['Rice', 'Florida International']:
            open( 'C:\\Users\\ntrup\\Google Drive\\GTPDD\\\\Coding\\in_files\\team_logos\\' + home + '.png', 'wb').write(hlogo_r.content)
    
    elif platform == 'AWS':
        open( '/tmp/' + visitor + '.png', 'wb').write(vlogo_r.content)
        open( '/tmp/' + home + '.png', 'wb').write(hlogo_r.content)
        
    elif platform == 'Chrome':
        open( 'in_files/' + visitor + '.png', 'wb').write(vlogo_r.content)
        open( 'in_files/' + home + '.png', 'wb').write(hlogo_r.content)
        
    ## Get scores over time
    plays = x['plays']
    awayScores = []
    homeScores = []
    times = []

    for play in plays:
        awayScores.append(play['awayScore'])
        homeScores.append(play['homeScore'])
        
        clock = play['clock']['displayValue']
        half = play['period']['number']
        time = int(clock.split(':')[0])*60 + int(clock.split(':')[1])
        if half == 1: time = time + 1200
        times.append(time)
        
    scores_df = pd.DataFrame(list(zip(awayScores, homeScores, times)),
                   columns =['Away', 'Home', 'Time'])

    return x,visitorId,homeId,visitor,home,v_color,v_color2,h_color,h_color2,scores_df
    
    
    