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
import json

def getPBPData():
    ## CFBD Configuration
    configuration = cfbd.Configuration()
    configuration.api_key['Authorization'] = os.environ["cfbdAuth"]
    configuration.api_key_prefix['Authorization'] = 'Bearer'
    api_instance = cfbd.PlaysApi(cfbd.ApiClient(configuration))

    ## Get the particular game we are interested in
    ## TODO: Grab the most recent game automatically
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
        playDict['gained'] = play.gained
        dictList.append(playDict)

    df = pd.DataFrame(dictList)
    df.to_csv('csv/fbPlaychartPBP.csv') 
    print(df)  

def setupChart():
    fig,ax = plt.subplots()
    #fig.set_size_inches(20, 30)
    ax.set_xlim(-13,113)
    plt.gca().invert_yaxis()
    
    return fig,ax        

i=0
df = pd.read_csv('csv/fbPlaychartPBP.csv')

with open('lib/fbPlaychartColorsTech.txt') as f: 
        data = f.read()
        techColorsDict = json.loads(data)
        print(techColorsDict)
        print(type(techColorsDict))

with open('lib/fbPlaychartColorsOppo.txt') as f: 
        data = f.read()
        oppoColorsDict = json.loads(data)


fig,ax = setupChart()
offense = ''
for index,row in df.iterrows():
    if row['offense'] != offense:
        offense = row['offense']
        i = i+10



    if row['offense'] == 'Louisiana Tech': 
        colorsDict = techColorsDict
        start = row['start']
        pos_gained = row['gained'] - 1.9
        neg_gained = row['gained'] + 1.9
        fg_yards = row['gained'] - 10
        touchback = [0,65]
        endzone=100
        coef = 1
        marker = '>'
        ko_marker = '<'
        ha = 'left'
        zha = 'right'
    
    else:
        colorsDict = oppoColorsDict
        start = row['start']
        pos_gained = -1 * row['gained'] + 1.9
        neg_gained = -1 * row['gained'] - 1.9
        fg_yards = -1 * row['gained'] - 10
        touchback = [100,35]
        endzone=0
        coef = -1
        marker = '<'
        ko_marker = '>'
        ha = 'right'
        zha= 'left'

    ## Get Color for each play
    if row['type'] == 'Pass Reception' or row['type'] == 'Passing Touchdown' or row['type'] == 'Pass Incompletion': color = colorsDict['pass']
    elif row['type'] == 'Rush' or row['type'] == 'Rushing Touchdown': color = colorsDict['run']
    elif row['type'] == 'Penalty': color = colorsDict['penalty']
    elif row['type'] == 'Sack': color = colorsDict['sack']
    elif row['type'] == 'Interception Return Touchdown': color = colorsDict['int']
    else: 
        color = 'green' # Catchall for unlisted. If we see green, there's a problem
        print(row['type'])

    ## KICKOFF
    ### TODO: Implement kickoffs
    if row['type'] == 'Kickoff' or row['type'] == 'Kickoff Return (Offense)':
        0

    ## FIELD GOAL
    elif row['type'] == 'Field Goal Good':
        ax.plot([start,start+fg_yards],[i, i], '--', marker = 'P', markersize = 8, linewidth=4, color='green')
    elif row['type'] == 'Field Goal Missed':
        ax.plot([start,start+fg_yards],[i, i], '--', marker = 'X', markersize = 8, linewidth=4, color='gray')
    
    ## PUNT
    elif row['type'] == 'Punt':
        ax.text(start,i," Punt ", fontsize=3, va='top', ha=ha)
        ax.plot([start,start+pos_gained],[i, i], '--', marker = marker, markersize = 1, linewidth=0.5, color='black')
            
    ## INTERCEPTION
    elif row['type'] == 'Interception':
        ax.text(start, i,'INTERCEPTION',color='purple', fontsize='40', ha=ha)
        #i = i - 2
        
    elif row['type'] == 'Interception Return Touchdown':
        ax.arrow(start,i,-1*(start-touchback[0]),0,width=3.8,head_width=3.8,head_length=0.9, color=color)
        ax.text(touchback[0],i," INT TD! ", fontsize=6, va='center', ha=zha)

    
    ## TIMEOUT
    elif row['type'] == 'Timeout':
        i = i - 1
    
    ## TODO: Fumble Recovery, Fix Kickoffs
    
    # END PERIOD
    elif row['type'] == 'End of Half':
        i = i - 1

    else:        
        if row['gained'] > 0:
            ax.arrow(start,i,pos_gained,0,width=3.8,head_width=3.8,head_length=0.9, color=color)
        elif row['gained'] < 0:
            ax.arrow(start,i,neg_gained,0,width=3.8,head_width=3.8,head_length=0.9, color=color)
        else:
            ax.plot([start,start],[i-0.9, i+0.9], color=color, linewidth=1)
        
        if 'Touchdown' in row['type']:
            ax.text(endzone,i," TD! ", fontsize=6, va='center', ha=ha) 

    ## Adding text where needed
    if row['type'] == 'Safety':
        ax.text(start,i," Safety! ", fontsize=6, va='center', ha=zha)  

          

    
    i=i+4

fig_path = 'out/fbPlaychart.png'
plt.savefig(fig_path, bbox_inches='tight', pad_inches = 0, dpi=1200, transparent = True)
print("Done.")

