from bs4 import BeautifulSoup as Soup
import lxml
import requests
import numpy as np
from pandas import DataFrame
import matplotlib.pyplot as plt
from PIL import Image
import tweepy
import csv
import boto3
from datetime import datetime, timedelta
from lib.common import parseRowStringTd, parseRowStringTextTrue

def getURL(team):
    csvStat = csv.reader(open('csv/bsbStatSites.csv', 'r'), delimiter = ',', quotechar="\"")
    for row in csvStat:
        if row[0] == team: url = row[1]
    return url

def getTeamBatting(url, minPA):
    team_soup = Soup((requests.get(url)).text, features="lxml")
    tables = team_soup.find_all('table')
    bat_table = tables[0]
    
    names = bat_table.find_all('th')
    list_of_parsed_rows = [parseRowStringTextTrue(name) for name in names[1:]]
    name_df = DataFrame(list_of_parsed_rows)
    name_df = name_df.dropna(subset=[1])
    name_df = name_df[[1,3]]
    name_df.columns = ['Name', 'Number']
    
    rows = bat_table.find_all('tr')
    list_of_parsed_rows = [parseRowStringTd(row) for row in rows[1:]]
    df = DataFrame(list_of_parsed_rows)
    df.columns = ['Number', 'AVG', 'OPS', 'GP-GS', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'TB', 'SLG%', 'BB', 'HBP', 'SO', 'GDP', 'OB%', 'SF', 'SH', 'SB-ATT', 'Bio']
    
    df = name_df.join(df.set_index('Number'), on='Number')
    
    df['PA'] = df['AB'].astype(int) + df['BB'].astype(int) + df['HBP'].astype(int)
    df['BB%'] = round((100*(df['BB'].astype(int) + df['HBP'].astype(int))/ (df['BB'].astype(int) + df['HBP'].astype(int) + df['AB'].astype(int))),2)
    
    df = df[~(df['PA'] <= minPA)]
    
    df = df.sort_values(by='OPS',ascending=False)
    df['H%'] = round(((df['H']).astype('int') / df['PA'])*100,2)
    df['OUT%'] = round(100 - df['H%'] - df['BB%'],2)

    df['1B%'] = (df['H'].astype('int') - df['2B'].astype('int') - df ['3B'].astype('int') - df['HR'].astype('int'))/df['H'].astype('int')
    df['2B%'] = df['2B'].astype('int')/df['H'].astype('int')
    df['3B%'] = df['3B'].astype('int')/df['H'].astype('int')
    df['HR%'] = df['HR'].astype('int')/df['H'].astype('int')
    
    df = df[['Number','Name','OPS', 'H%', 'BB%', 'OUT%', '1B%', '2B%', '3B%', 'HR%']]
    return df
     
def getTeamPitching(url, minStarts, minBF):
    team_soup = Soup((requests.get(url)).text, features="lxml")
    tables = team_soup.find_all('table')
    pitch_table = tables[1]

    names = pitch_table.find_all('th')
    list_of_parsed_rows = [parseRowStringTextTrue(name) for name in names[1:]]
    name_df = DataFrame(list_of_parsed_rows)
    name_df = name_df.dropna(subset=[1])
    name_df = name_df[[1,3]]
    name_df.columns = ['Name', 'Number']
    
    rows = pitch_table.find_all('tr')
    list_of_parsed_rows = [parseRowStringTd(row) for row in rows[1:]]
    df = DataFrame(list_of_parsed_rows)
    df.columns = ['Number', 'ERA', 'WHIP', 'W-L', 'APP-GS', 'CG', 'SHO', 'SV', 'IP', 'H', 'R', 'ER', 'BB', 'SO', '2B', '3B', 'HR', 'AB', 'B/AVG', 'WP', 'HBP', 'BK', 'SFA', 'SHA', 'Bio']
    
    df = name_df.join(df.set_index('Number'), on='Number')
    #df[['APP', 'GS']] = df['APP-GS'].str.split('-',1, expand=True)
    df[['APP', 'GS']] = df['APP-GS'].str.split('-',n=1, expand=True)

    df['ERA'] = df['ERA'].astype('float')
    df = df.sort_values(by='ERA', ascending=True)
    
    df['BF'] = df['AB'].astype(int) + df['BB'].astype(int) + df['HBP'].astype(int)
    df = df[~(df['BF'] <= minBF)]
    
    df['H%'] = round(((df['H']).astype('int') / df['BF'])*100,2)
    df['BB%'] = round((100*(df['BB'].astype(int) + df['HBP'].astype(int))/ (df['BB'].astype(int) + df['HBP'].astype(int) + df['BF'].astype(int))),2)
    df['OUT%'] = round(100 - df['H%'] - df['BB%'],2)
    
    df['1B%'] = (df['H'].astype('int') - df['2B'].astype('int') - df ['3B'].astype('int') - df['HR'].astype('int'))/df['H'].astype('int')
    df['2B%'] = df['2B'].astype('int')/df['H'].astype('int')
    df['3B%'] = df['3B'].astype('int')/df['H'].astype('int')
    df['HR%'] = df['HR'].astype('int')/df['H'].astype('int')
    
    df = df.fillna(0)
    
    df_s = df.loc[df['GS'].astype('int') >= minStarts]
    df_r = df.loc[df['GS'].astype('int') < minStarts]
    
    df_s = df_s[['Number','Name','ERA', 'IP', 'H%', 'BB%', 'OUT%', '1B%', '2B%', '3B%', 'HR%']]
    df_r = df_r[['Number','Name','ERA', 'IP', 'H%', 'BB%', 'OUT%', '1B%', '2B%', '3B%', 'HR%']]
    return df_s, df_r

def generateBattingReport(df, long_team, minPA, num):
    fig, ax = plt.subplots(7,3, figsize=(30,45))
    i = 0
    for index, row in df.iterrows():
        if i < 7:
            
            # Print Player Names on Chart
            ax[i,0].axis('off')
            name = row['Name']
            number = row['Number']
            OPS = row['OPS']
            ax[i,0].annotate(name, (0,0.4), fontsize=60)
            ax[i,0].annotate('#' + number, (0,0.2), fontsize=40)
            ax[i,0].annotate('OPS: ' + str(OPS), (0.3,0.2), fontsize=40, fontweight='bold')

            # Get Hitwalk Pie Data ready for Chart
            hitwalk_pie = [row['H%'], row['BB%'], row['OUT%']]
            hitwalk_pie_labels = []
            for x in hitwalk_pie:
                if x < 10:
                    hitwalk_pie_labels.append(str(x*100)[0:1]+'%')
                else:
                    hitwalk_pie_labels.append(str(x*100)[0:2]+'%')
            
            # Create HitWalk Pie Charts
            patches1, texts1 = ax[i,1].pie(hitwalk_pie, startangle=90, colors=['tab:blue','tab:red','aliceblue'], labels = hitwalk_pie_labels, labeldistance=1.2)
            
            # Change Hitwalk Pie Label Font Size
            texts1[0].set_fontsize(40)
            texts1[0].set_color('tab:blue')
            texts1[1].set_fontsize(40)
            texts1[1].set_color('tab:red')
            texts1[2].set_fontsize(0)
            
            # Get HitOutcome Pie Data ready for Chart
            hitoutcome_pie = [row['1B%'], row['2B%'], row['3B%'], row['HR%']]
            hitoutcome_pie_labels = []
            for x in hitoutcome_pie:
                if x == 1:
                    hitoutcome_pie_labels.append('100%')
                elif x < 0.1:
                    hitoutcome_pie_labels.append(str(x*100)[0:1]+'%')
                else:
                    hitoutcome_pie_labels.append(str(x*100)[0:2]+'%')
            
            # Creat HitOutcome Pie Charts
            patches2, texts2 = ax[i,2].pie(hitoutcome_pie, startangle=90, colors=['tab:green','goldenrod','tab:cyan','tab:purple'], labels = hitoutcome_pie_labels, labeldistance=1.2)
            
            # Change Hitwalk Pie Label Font Size
            for j in range(4):
                if hitoutcome_pie[j] > 0:
                    texts2[j].set_fontsize(40)
                else:
                    texts2[j].set_fontsize(0)
            texts2[2].set_fontsize(0)
            
            texts2[0].set_color('tab:green')
            texts2[1].set_color('goldenrod')
            texts2[3].set_color('tab:purple')
            
            i = i + 1
            
    plt.figtext(0.15,0.91,'Name', fontsize=80, color='black')
    plt.figtext(0.34,0.91,'Plate Outcome', fontsize=80, color='black')
    plt.figtext(0.67,0.91,'Hit Outcome', fontsize=80, color='black')
    
    plt.figtext(0.47,0.89,'Hits', ha='right', fontsize=43, color='tab:blue')
    plt.figtext(0.49,0.89,'Walks', ha='left', fontsize=43, color='tab:red')
    
    plt.figtext(0.63,0.89,'Singles', ha='left', fontsize=40, color='tab:green')
    plt.figtext(0.705,0.89,'Doubles', ha='left', fontsize=40, color='goldenrod') 
    plt.figtext(0.785,0.89,'Triples', ha='left', fontsize=40, color='tab:cyan')
    plt.figtext(0.85,0.89,'Home Runs', ha='left', fontsize=40, color='tab:purple')

    
    fig.suptitle(long_team + ' Batting Report', fontsize=110)
    
    #plt.figtext(0.1,0.93,'Players listed in order of OPS (Min. 30 PA)', ha='left', fontsize=40, color='black')
    plt.figtext(0.07,0.1,'Top Seven Players, by OPS, in order (Min. ' + str(minPA) + ' PA)', ha='left', fontsize=40, color='black')
    plt.figtext(1,0.1,'Data from team websites', ha='right', fontsize=40, color='black')
    plt.figtext(0,1,' ', ha='right', fontsize=40, color='black')
    
    fig.patch.set_facecolor('aliceblue')
    
    im = Image.open('img/bsbNotebookPaper.png')
    height = im.size[1]
    im = np.array(im).astype(float) / 255
    
    fig.figimage(im, -60, 8)

    fig_path = 'out/bsbPlayerPreviewBatting' + num + '.png'
    plt.savefig(fig_path, dpi=71, bbox_inches='tight', facecolor = 'aliceblue', pad_inches = 0)

def generateStartingPitchingReport(df, long_team, numStarters, num):    
    fig, ax = plt.subplots(numStarters,3, figsize=(30,45))
    i = 0
    for index, row in df.iterrows():
        if i < numStarters:
            
            # Print Player Names on Chart
            ax[i,0].axis('off')
            name = row['Name']
            number = row['Number']
            ERA = "{:.2f}".format(row['ERA'])
            IP = row['IP']
            ax[i,0].annotate(name, (0,0.4), fontsize=60)
            ax[i,0].annotate('#' + number, (0,0.5), fontsize=40)
            ax[i,0].annotate('IP: ' + IP, (0,0.3), fontsize=40)
            ax[i,0].annotate('ERA: ' + str(ERA), (0.35,0.3), fontsize=40, fontweight='bold')


            # Get Hitwalk Pie Data ready for Chart
            hitwalk_pie = [row['H%'], row['BB%'], row['OUT%']]
            hitwalk_pie_labels = []
            for x in hitwalk_pie:
                if x < 10:
                    hitwalk_pie_labels.append(str(x*100)[0:1]+'%')
                else:
                    hitwalk_pie_labels.append(str(x*100)[0:2]+'%')
            
            # Create HitWalk Pie Charts
            patches1, texts1 = ax[i,1].pie(hitwalk_pie, startangle=90, colors=['tab:blue','tab:red','aliceblue'], labels = hitwalk_pie_labels, labeldistance=1.2)
            
            # Change Hitwalk Pie Label Font Size
            texts1[0].set_fontsize(40)
            texts1[0].set_color('tab:blue')
            texts1[1].set_fontsize(40)
            texts1[1].set_color('tab:red')
            texts1[2].set_fontsize(0)
            
            # Get HitOutcome Pie Data ready for Chart
            hitoutcome_pie = [row['1B%'], row['2B%'], row['3B%'], row['HR%']]
            hitoutcome_pie_labels = []
            for x in hitoutcome_pie:
                if x == 1:
                    hitoutcome_pie_labels.append('100%')
                elif x < 0.1:
                    hitoutcome_pie_labels.append(str(x*100)[0:1]+'%')
                else:
                    hitoutcome_pie_labels.append(str(x*100)[0:2]+'%')
            
            # Creat HitOutcome Pie Charts
            patches2, texts2 = ax[i,2].pie(hitoutcome_pie, startangle=90, colors=['tab:green','goldenrod','tab:cyan','tab:purple'], labels = hitoutcome_pie_labels, labeldistance=1.2)
            
            # Change Hitwalk Pie Label Font Size
            for j in range(4):
                if hitoutcome_pie[j] > 0:
                    texts2[j].set_fontsize(40)
                else:
                    texts2[j].set_fontsize(0)
            texts2[2].set_fontsize(0)
            
            texts2[0].set_color('tab:green')
            texts2[1].set_color('goldenrod')
            texts2[2].set_color('tab:cyan')
            texts2[3].set_color('tab:purple')
            
            i = i + 1
            
    plt.figtext(0.15,0.91,'Name', fontsize=80, color='black')
    plt.figtext(0.34,0.91,'Plate Outcome', fontsize=80, color='black')
    plt.figtext(0.67,0.91,'Hit Outcome', fontsize=80, color='black')
    
    plt.figtext(0.47,0.89,'Hits', ha='right', fontsize=43, color='tab:blue')
    plt.figtext(0.49,0.89,'Walks', ha='left', fontsize=43, color='tab:red')
    
    plt.figtext(0.63,0.89,'Singles', ha='left', fontsize=40, color='tab:green')
    plt.figtext(0.705,0.89,'Doubles', ha='left', fontsize=40, color='goldenrod') 
    plt.figtext(0.785,0.89,'Triples', ha='left', fontsize=40, color='tab:cyan')
    plt.figtext(0.85,0.89,'Home Runs', ha='left', fontsize=40, color='tab:purple')

    
    fig.suptitle(long_team + ' Starting Pitching Report', fontsize=90)
    
    plt.figtext(0.07,0.1,str(numStarters) + ' Top Starters, ranked by ERA', ha='left', fontsize=40, color='black')
    plt.figtext(1,0.1,'Data from team websites', ha='right', fontsize=40, color='black')
    plt.figtext(0,1,' ', ha='right', fontsize=40, color='black')
    
    fig.patch.set_facecolor('aliceblue')
    
    im = Image.open('img/bsbNotebookPaper.png')
    height = im.size[1]
    im = np.array(im).astype(float) / 255
    
    fig.figimage(im, -60, 8)
    
    fig_path = 'out/bsbPlayerPreviewStartingPitching' + num + '.png'
    plt.savefig(fig_path, dpi=71, bbox_inches='tight', facecolor = 'aliceblue', pad_inches = 0)

def generateReliefPitchingReport(df, long_team, numRelievers, minBF, num):    
    fig, ax = plt.subplots(numRelievers,3, figsize=(30,45))
    i = 0
    for index, row in df.iterrows():
        if i < numRelievers:
            
            # Print Player Names on Chart
            ax[i,0].axis('off')
            name = row['Name']
            number = row['Number']
            ERA = "{:.2f}".format(row['ERA'])
            IP = row['IP']
            ax[i,0].annotate(name, (0,0.4), fontsize=60)
            ax[i,0].annotate('#' + number, (0,0.6), fontsize=40)
            ax[i,0].annotate('IP: ' + IP, (0,0.2), fontsize=40)
            ax[i,0].annotate('ERA: ' + str(ERA), (0.3,0.2), fontsize=40, fontweight='bold')


            # Get Hitwalk Pie Data ready for Chart
            hitwalk_pie = [row['H%'], row['BB%'], row['OUT%']]
            hitwalk_pie_labels = []
            for x in hitwalk_pie:
                if x < 10:
                    hitwalk_pie_labels.append(str(x*100)[0:1]+'%')
                else:
                    hitwalk_pie_labels.append(str(x*100)[0:2]+'%')
            
            # Create HitWalk Pie Charts
            patches1, texts1 = ax[i,1].pie(hitwalk_pie, startangle=90, colors=['tab:blue','tab:red','aliceblue'], labels = hitwalk_pie_labels, labeldistance=1.2)
            
            # Change Hitwalk Pie Label Font Size
            texts1[0].set_fontsize(40)
            texts1[0].set_color('tab:blue')
            texts1[1].set_fontsize(40)
            texts1[1].set_color('tab:red')
            texts1[2].set_fontsize(0)
            
            # Get HitOutcome Pie Data ready for Chart
            hitoutcome_pie = [row['1B%'], row['2B%'], row['3B%'], row['HR%']]
            hitoutcome_pie_labels = []
            for x in hitoutcome_pie:
                if x == 1:
                    hitoutcome_pie_labels.append('100%')
                elif x < 0.1:
                    hitoutcome_pie_labels.append(str(x*100)[0:1]+'%')
                else:
                    hitoutcome_pie_labels.append(str(x*100)[0:2]+'%')
            
            # Creat HitOutcome Pie Charts
            patches2, texts2 = ax[i,2].pie(hitoutcome_pie, startangle=90, colors=['tab:green','goldenrod','tab:cyan','tab:purple'], labels = hitoutcome_pie_labels, labeldistance=1.2)
            
            # Change Hitwalk Pie Label Font Size
            for j in range(4):
                if hitoutcome_pie[j] > 0:
                    texts2[j].set_fontsize(40)
                else:
                    texts2[j].set_fontsize(0)
            texts2[2].set_fontsize(0)
            
            texts2[0].set_color('tab:green')
            texts2[1].set_color('goldenrod')
            texts2[2].set_color('tab:cyan')
            texts2[3].set_color('tab:purple')
            
            i = i + 1
            
    plt.figtext(0.15,0.91,'Name', fontsize=80, color='black')
    plt.figtext(0.34,0.91,'Plate Outcome', fontsize=80, color='black')
    plt.figtext(0.67,0.91,'Hit Outcome', fontsize=80, color='black')
    
    plt.figtext(0.47,0.89,'Hits', ha='right', fontsize=43, color='tab:blue')
    plt.figtext(0.49,0.89,'Walks', ha='left', fontsize=43, color='tab:red')
    
    plt.figtext(0.63,0.89,'Singles', ha='left', fontsize=40, color='tab:green')
    plt.figtext(0.705,0.89,'Doubles', ha='left', fontsize=40, color='goldenrod') 
    plt.figtext(0.785,0.89,'Triples', ha='left', fontsize=40, color='tab:cyan')
    plt.figtext(0.85,0.89,'Home Runs', ha='left', fontsize=40, color='tab:purple')

    
    fig.suptitle(long_team + ' Relief Pitching Report', fontsize=90)
    
    plt.figtext(0.07,0.1,'Top ' + str(numRelievers) + ' Relievers, ranked by ERA (Min ' + str(minBF) + ' BF)', ha='left', fontsize=40, color='black')
    plt.figtext(1,0.1,'Data from team websites', ha='right', fontsize=40, color='black')
    plt.figtext(0,1,' ', ha='right', fontsize=40, color='black')
    
    fig.patch.set_facecolor('aliceblue')
    
    im = Image.open('img/bsbNotebookPaper.png')
    height = im.size[1]
    im = np.array(im).astype(float) / 255
    
    fig.figimage(im, -60, 8)
    
    fig_path = 'out/bsbPlayerPreviewReliefPitching' + num + '.png'
    plt.savefig(fig_path, dpi=71, bbox_inches='tight', facecolor = 'aliceblue', pad_inches = 0)
    
def saveImages(team1, team2):
    
    s3 = boto3.client('s3')
    s3.upload_file('/tmp/' + team1 + '_batting.png', 'gtpdd', 'bsb_team1_batting.png')
    s3.upload_file('/tmp/' + team2 + '_batting.png', 'gtpdd', 'bsb_team2_batting.png')
    s3.upload_file('/tmp/' + team1 + '_starting_pitching.png', 'gtpdd', 'bsb_team1_starting_pitching.png')
    s3.upload_file('/tmp/' + team2 + '_starting_pitching.png', 'gtpdd', 'bsb_team2_starting_pitching.png')
    s3.upload_file('/tmp/' + team1 + '_relief_pitching.png', 'gtpdd', 'bsb_team1_relief_pitching.png')
    s3.upload_file('/tmp/' + team2 + '_relief_pitching.png', 'gtpdd', 'bsb_team2_relief_pitching.png')


team1 = 'Louisiana Tech'
team2 = 'ULM'

minPA = 10
minStarts = 2
minBF = 5

#minPA = int(gameNumber) * 1.5
#minStarts = int(gameNumber) / 10
#minBF = int(gameNumber) / 2

numStarters = 3
numRelievers = 7

team1URL = getURL(team1)
team2URL = getURL(team2)

team1Short = team1.replace(' ','')
team2Short = team2.replace(' ','')

df = getTeamBatting(team1URL, minPA)
generateBattingReport(df, team1, minPA,'1')

df = getTeamBatting(team2URL, minPA)
generateBattingReport(df, team2, minPA,'2')

df_s, df_r = getTeamPitching(team1URL, minStarts, minBF)
generateStartingPitchingReport(df_s, team1, numStarters,'1')
generateReliefPitchingReport(df_r, team1, numRelievers, minBF,'1')

df_s, df_r = getTeamPitching(team2URL, minStarts, minBF)
generateStartingPitchingReport(df_s, team2, numStarters,'2')
generateReliefPitchingReport(df_r, team2, numRelievers, minBF,'2')
    
#saveImages(team2Short, team1Short)
