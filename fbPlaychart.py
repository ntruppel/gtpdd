# -*- coding: utf-8 -*-
"""
Created on Wed Nov  2 18:06:08 2022

@author: ntrup
"""


import cfbd
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import re
import os
from dotenv import load_dotenv
load_dotenv()
from pandas import json_normalize

def getPBPData():
    ## CFBD Configuration
    configuration = cfbd.Configuration()
    configuration.api_key['Authorization'] = os.environ["cfbdAuth"]
    configuration.api_key_prefix['Authorization'] = 'Bearer'
    api_instance = cfbd.PlaysApi(cfbd.ApiClient(configuration))

    ## Get the particular game we are interested in
    ## FUTURE: Grab the most recent game automatically
    api_response = api_instance.get_plays(2024, week=1, team='Louisiana Tech')

    dictList = []
    for play in api_response:
        playDict = {}
        playDict ['offense'] = play.offense
        playDict['clock'] = "Q" + str(play.period) + " " + str(play.clock.minutes) + ":" + str(play.clock.seconds)
        playDict['down'] = play.down
        playDict['distance'] = play.distance
        playDict['type'] = play.play_type
        playDict['start'] = play.yard_line
        playDict['gained'] = play.yards_gained
        dictList.append(playDict)

    df = pd.DataFrame(dictList)
    df.to_csv('csv/fbPlaychartPBP.csv') 
    print(df)             

df = pd.read_csv('csv/fbPlaychartPBP.csv')
for index,row in df.iterrows():

    if row['offense'] == 'Louisiana Tech': 
        color_pass = 'tab:blue'
        color_rush = 'tab:red'
        start = row['start_yards']
        pos_yards_gained = row['yards_gained'] - 0.9
        neg_yards_gained = row['yards_gained'] + 0.9
        fg_yards = row['yards_gained'] - 10
        touchback = [0,65]
        endzone=100
        coef = 1
        marker = '>'
        ko_marker = '<'
        ha = 'left'
        zha = 'right'
    
    else:
        color_pass = 'black'
        color_rush = 'silver'
        start = row['start_yards']
        pos_yards_gained = -1 * row['yards_gained'] + 0.9
        neg_yards_gained = -1 * row['yards_gained'] - 0.9
        fg_yards = -1 * row['yards_gained'] - 10
        touchback = [100,35]
        endzone=0
        coef = -1
        marker = '<'
        ko_marker = '>'
        ha = 'right'
        zha= 'left'