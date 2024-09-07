# -*- coding: utf-8 -*-
"""
Created on Tue Aug 15 12:43:51 2023

@author: ntrup
"""

import pandas as pd
import matplotlib.pyplot as plt
from bs4 import BeautifulSoup as Soup
from pandas import DataFrame 
import numpy
import requests
import csv
import cfbd
from pandas import json_normalize 
import json 
import os
from dotenv import load_dotenv

def statLookup(statName,adv_df):
    s_list = [
        statName,
        adv_df.loc[team1]['offense.'+statName]-adv_df.loc['Average']['offense.'+statName], 
        adv_df.loc[team1]['defense.'+statName]-adv_df.loc['Average']['defense.'+statName],
        adv_df.loc[team2]['offense.'+statName]-adv_df.loc['Average']['offense.'+statName],
        adv_df.loc[team2]['defense.'+statName]-adv_df.loc['Average']['defense.'+statName],
        adv_df.loc['Min']['offense.'+statName]-adv_df.loc['Average']['offense.'+statName],
        adv_df.loc['Max']['offense.'+statName]-adv_df.loc['Average']['offense.'+statName]]
    
    if statName == 'stuffRate':
        s_list[1] = -s_list[1]
        s_list[2] = -s_list[2]
        s_list[3] = -s_list[3]
        s_list[4] = -s_list[4]
    return s_list

def generateAdvancedPreview(team1,team2,t1c1,t1c2,t2c1,t2c2):
    api_instance = cfbd.StatsApi(cfbd.ApiClient(configuration))
    api = api_instance.get_advanced_team_season_stats(year=2022)
    dicts = []
    for api_team in api:
        try: dicts.append(json.loads(str(api_team).replace("'", "\"")))
        except:0
    adv_df = pd.json_normalize(dicts)
    adv_df = adv_df.set_index('team')
    adv_df.drop(columns=['conference'], inplace=True)
    adv_df.loc['Average'] = adv_df.mean()
    adv_df.loc['Min'] = adv_df.min()
    adv_df.loc['Max'] = adv_df.max()
    adv_df = adv_df.loc[[team1, team2, "Average", "Min", "Max"]]

    adv_df.to_csv('out/temp.csv')
    
    stat_list = ['explosiveness','ppa','successRate','pointsPerOpportunity','fieldPosition.averagePredictedPoints','havoc.db','lineYards','openFieldYards','powerSuccess','secondLevelYards','stuffRate','havoc.frontSeven','rushingPlays.explosiveness','rushingPlays.ppa','rushingPlays.successRate','passingPlays.explosiveness','passingPlays.ppa','passingPlays.successRate','standardDowns.explosiveness','standardDowns.ppa','standardDowns.successRate','passingDowns.explosiveness','passingDowns.ppa','passingDowns.successRate',]
    print(len(stat_list))
    aa_list = []
    for stat in stat_list:
        try: aa_list.append(statLookup(stat, adv_df))
        except: 0
    
    fig1,ax1 = plt.subplots(6,4)
    fig2,ax2 = plt.subplots(6,4)
    fig1.set_size_inches(20, 10)
    fig2.set_size_inches(20, 10)

    print(aa_list)
    
    i = 0; j = 0
    for k in range(0,23):
        print(i,j,k)
        if i>5: i=0;j=j+1
        ax1[i][j].set_title(aa_list[k][0], fontsize=8)
        
        if aa_list[k][1] > 0: color = t1c1 
        else: color = t1c2
        ax1[i][j].barh(0,aa_list[k][1], color=color, height=1)
        
        if aa_list[k][4] < 0: color = t2c1 
        else: color = t2c2
        ax1[i][j].barh(1,aa_list[k][4], color=color, height=1)
        ax1[i][j].axvline(x=0, color='k', linewidth=3)
        if abs((aa_list[k][5]) > abs(aa_list[k][6])): ax1[i][j].set_xlim(aa_list[k][5],-aa_list[k][5])
        else: ax1[i][j].set_xlim(-aa_list[k][6],aa_list[k][6])
        ax1[i][j].axis('off')
    
        
        ax2[i][j].set_title(aa_list[k][0], fontsize=8)
        
        if aa_list[k][2] < 0: color = t1c1 
        else: color = t1c2
        ax2[i][j].barh(0,-aa_list[k][2], color=color, height=1)
        
        if aa_list[k][3] > 0: color = t2c1 
        else: color = t2c2
        ax2[i][j].barh(1,-aa_list[k][3], color=color, height=1)
        ax2[i][j].axvline(x=0, color='k', linewidth=3)
        if abs((aa_list[k][5]) > abs(aa_list[k][6])): ax2[i][j].set_xlim(aa_list[k][5],-aa_list[k][5])
        else: ax2[i][j].set_xlim(-aa_list[k][6],aa_list[k][6])
        ax2[i][j].axis('off')
        i=i+1
    
    fig1.suptitle('Tech Offense', fontsize=16)
    fig2.suptitle('Tech Defense', fontsize=16)


team1 = 'Louisiana Tech'
t1c1 = '#002F8B'
t1c2 = '#E31B23'
team2 = 'Florida International'
t2c1 = '#081E3F'
t2c2='#B6862C'

load_dotenv()

configuration = cfbd.Configuration()
configuration.api_key['Authorization'] = os.environ["cfbdAuth"]
configuration.api_key_prefix['Authorization'] = 'Bearer'
generateAdvancedPreview(team1,team2,t1c1,t1c2,t2c1,t2c2)





