# -*- coding: utf-8 -*-
"""
Created on Mon Aug 14 10:38:58 2023

@author: ntrup
"""
import requests
import pandas as pd
from dateutil import parser, tz

def getFBSchedule(teamID):
    from_zone = tz.tzutc()
    
    schedule_url = 'https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams/'+ teamID + '/schedule'
    r = requests.get(schedule_url)
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

def getTeamInfo(teamID):
    url = 'https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams/'+ teamID
    r = requests.get(url)
    x = r.json()
    
    name = x['team']['location']
    color1 = x['team']['color']
    color2 = x['team']['alternateColor']
    
    return name, color2, color1
