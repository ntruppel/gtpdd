# -*- coding: utf-8 -*-
"""
Created on Fri Aug 18 20:33:00 2023

@author: ntrup
"""


import requests
import numpy as np
from datetime import datetime, timezone
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image
from lib.common import createTweet
from lib.fbCommon import getFBSchedule, getTeamInfo

def getSeasonStats(teamId):
    stats_url = 'https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams/'+ teamId +'/statistics'
    r = requests.get(stats_url)
    x = r.json()
    
    statNames= []
    statValues=[]
    statRanks=[]
    for statCategory in x['results']['stats']['categories']:
        for stat in statCategory['stats']:
            statNames.append(stat['name'])
            statValues.append(stat['displayValue'])
    stats = dict(zip(statNames, statValues))
    
    oppoNames = []
    oppoValues = []
    oppoRanks = []
    for statCategory in x['results']['opponent']:
        for stat in statCategory['stats']:
            oppoNames.append(stat['name'])
            oppoValues.append(stat['displayValue'])
    oppos = dict(zip(oppoNames, oppoValues))

    df = pd.DataFrame({teamId+'_o':pd.Series(stats),teamId+'_d':pd.Series(oppos)})
    df = df[df[teamId+'_d'].notna()]
    print(df)
    return(df)

present = datetime.now(timezone.utc)
teamID = "2348"
schedule_df, record = getFBSchedule(teamID)

for index,row in schedule_df.iterrows():
    if present < row['date']:    
        team1_df = getSeasonStats(row['away'])
        team2_df = getSeasonStats(row['home'])

team1_df = getSeasonStats('2229')
team2_df = getSeasonStats('2348')