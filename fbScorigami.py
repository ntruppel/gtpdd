# -*- coding: utf-8 -*-
"""
Created on Sun Sep 11 20:24:42 2022

@author: ntrup
"""


import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import cfbd
import os
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
    
def generateScorigamiTable(df):
    win_scores = []
    lose_scores = []

    df['winScore'] = df[["Tech Score", "Opponent Score"]].max(axis=1)
    df['lossScore'] = df[["Tech Score", "Opponent Score"]].min(axis=1)

    df['TechWin'] = np.where(df["Tech Score"] > df["Opponent Score"], True, False)


    df = df[['winScore','lossScore','Opponent','Date','TechWin']]
    df = df.reset_index()
    print(df)
        
    numGames = []
    lastWin = []
    lastLoss = []
    for i in range(0,101):
        for j in range(0,72):
            filter = df[(df['winScore'] == i) & (df['lossScore'] == j)]
            if filter.empty:
                numGames.append(0)
                lastWin.append('')
                lastLoss.append('')
            
            else:
                numGames.append(len(filter))

                winFilter = filter[(filter['TechWin'] == True)]
                try: lastWin.append(str(winFilter['Date'].values[-1]) + ": " + str(winFilter['Opponent'].values[-1]))
                except: lastWin.append('')

                lossFilter = filter[(filter['TechWin'] == False)]
                try: lastLoss.append(str(lossFilter['Date'].values[-1]) + ": " + str(lossFilter['Opponent'].values[-1]))
                except: lastLoss.append('')
    
    df = pd.DataFrame({'winScore':np.repeat([*range(0,101)],72), 'lossScore':[*range(0,72)]*101, 'numGames':numGames, 'lastWin':lastWin, 'lastLoss':lastLoss})
    df = df[(df['winScore'] >= df['lossScore']) & (df['numGames'] > 0)]
    return df

def generateScorigamiChart(df, df_wl, ext, win_score, lose_score, fullPath, basicPath):
    win_min = 0
    win_max = 101
    lose_min = 0
    lose_max = 61
    win_med = (win_min + win_max) / 2
    lose_med = (lose_min + lose_max) / 2

    fig, ax = plt.subplots()    
    df_wl = df_wl[['Tech Score','Opponent Score']]
    
    for index,row in df.iterrows():
        win = row['Win']
        lose = row['Lose']
        
        if lose > win:
            rect = patches.Rectangle((win, lose), 1, 1, linewidth=0.01, edgecolor='black', facecolor='black')
            ax.add_patch(rect)
        
        elif row['isGami'] > 0:
        
            linewidth = 0.01; edgecolor = 'black'
            
            ## ext adds the red and skyblue colors to show wins/loses
            if ext:
                filter_l = df_wl[(df_wl['Tech Score'] == lose) & (df_wl['Opponent Score'] == win)]
                filter_w = df_wl[(df_wl['Tech Score'] == win) & (df_wl['Opponent Score'] == lose)]
                
                ## If Both
                if not filter_l.empty and not filter_w.empty:
                    rect = patches.Rectangle((win, lose), 1, 1, linewidth=linewidth, edgecolor=edgecolor, facecolor='blue')
                    if win == win_score and lose == lose_score:
                        game_color = 'blue'
                
                ## If Just Win
                elif filter_l.empty and not filter_w.empty:
                    rect = patches.Rectangle((win, lose), 1, 1, linewidth=linewidth, edgecolor=edgecolor, facecolor='skyblue')
                    if win == win_score and lose == lose_score:
                        game_color = 'skyblue'
                
                ## If Just Lose
                elif not filter_l.empty and filter_w.empty:
                    rect = patches.Rectangle((win, lose), 1, 1, linewidth=linewidth, edgecolor=edgecolor, facecolor='red')
                    if win == win_score and lose == lose_score:
                        game_color = 'red'
                else:
                    rect = patches.Rectangle((win, lose), 1, 1, linewidth=linewidth, edgecolor=edgecolor, facecolor='green')
            
            else:
                rect = patches.Rectangle((win, lose), 1, 1, linewidth=linewidth, edgecolor=edgecolor, facecolor='blue')
                
            ax.add_patch(rect)
            
            
            ## Add counts to squares
            ax.text(win+0.5,lose+0.5,str(row['isGami']), fontsize=2, ha='center', va='center', color='white')
            
        else:
            rect = patches.Rectangle((win, lose), 1, 1, linewidth=0.01, edgecolor='black', facecolor='white')
            ax.add_patch(rect)
    try:
        rect = patches.Rectangle((win_score, lose_score), 1, 1, linewidth=1, edgecolor='black', facecolor=game_color)
        ax.add_patch(rect)
    except:
        0


    plt.xlim([win_min, win_max])
    plt.ylim([lose_max,lose_min])
    for i in range(win_min,win_max):
        ax.text(i+0.5,lose_min-0.5,str(i), fontsize=2, ha='center')
    for i in range(lose_min,lose_max):
        ax.text(win_min-1,i+0.5,str(i), fontsize=2, va='center')
    
    ax.text(win_med,lose_min-1.5,"Winning Team Score", ha='center', fontsize=4)
    ax.text(win_min-2,lose_med,"Losing Team Score", va='center', fontsize=4, rotation=90)
    ax.axis('off')
    ax.text(win_med, lose_min-3, 'Louisiana Tech Scorigami', ha='center', fontsize=12)
    
    ax.text(82,20,'Games Tech Won', color='skyblue', fontsize=5)
    ax.text(82,22,'Games Tech Lost', color='red', fontsize=5)
    ax.text(82,24,'Some Combination/Tie', color='blue', fontsize=5)
    
    if ext:
        fig_path = fullPath
    else:
        fig_path = basicPath
    plt.savefig(fig_path, bbox_inches='tight', pad_inches = 0, dpi = 1000)
    
    return 0
    
def checkIfScorigami(df, techScore, oppoScore):
    forwardGames, forwardLastOppo, forwardLastDate = 0,0,0
    backwardGames, backwardLastOppo, backwardLastDate = 0,0,0
    forward_df = df[(df['Tech Score'] == techScore) & (df['Opponent Score'] == oppoScore)]
    backward_df = df[(df['Tech Score'] == oppoScore) & (df['Opponent Score'] == techScore)]
    
    ## If forward and backward
    if not forward_df.empty and not backward_df.empty:
        forwardGames = len(forward_df)
        forwardLastOppo = forward_df.iloc[-1]['Opponent']
        forwardLastDate = forward_df.iloc[-1]['Date']
        
        backwardGames = len(backward_df)
        backwardLastOppo = backward_df.iloc[-1]['Opponent']
        backwardLastDate = backward_df.iloc[-1]['Date']
        
        totalGames = forwardGames + backwardGames
        message = "Saturday's game was not a scorigami.\n\nThis exact score has happened " +  str(totalGames) + " times before in school history.\nThe last time Tech was the team with " + str(techScore) + ", it was on " + forwardLastDate + " against " + forwardLastOppo + ".\nThe last time Tech scored " + str(oppoScore) + "instead, it was on " + backwardLastDate + " against " + backwardLastOppo    

    ## If just forward
    elif not forward_df.empty and backward_df.empty:
        totalGames = len(forward_df)
        lastOppo = forward_df.iloc[-1]['Opponent']
        lastDate = forward_df.iloc[-1]['Date']
        if totalGames > 1:
            message = "Saturday's game was not a scorigami.\n\nThis exact score has happened " +  str(totalGames) + " times before in school history.\nMost recently, on " + lastDate + ", the final was Tech " + str(techScore) + " - " + lastOppo + " " + str(oppoScore)    
        else:    
            message = "Saturday's game was not a scorigami.\n\nBut this was only the second time in school history a game ended with this score.\nThe other time was on " + lastDate + ", and the final was Tech " + str(techScore) + " - " + lastOppo + " " + str(oppoScore)
    
    elif forward_df.empty and not backward_df.empty:
        totalGames = len(backward_df)
        lastOppo = backward_df.iloc[-1]['Opponent']
        lastDate = backward_df.iloc[-1]['Date']
        if totalGames > 1:
            message = "Saturday's game was not a scorigami.\n\nThis exact score has happened " +  str(totalGames) + " times before in school history.\nBut never has Tech been the team with " + str(techScore) + " points.\nMost recently, on " + lastDate + ", the final was Tech " + str(oppoScore) + " - " + lastOppo + " " + str(techScore)    
        else:    
            message = "Saturday's game was not a scorigami.\n\nBut this was only the second time in school history a game ended with this score.\nThat time, Tech was the team with " + str(oppoScore) + " points.\nIt was on " + lastDate + ", and the final was Tech " + str(oppoScore) + " - " + lastOppo + " " + str(techScore)
    
    else:
        message = "Saturday's game was a scorigami!!\n\nNever before has game ended with the final score of " + str(techScore) + " to " + str(oppoScore) + " in the 120 year history of Louisiana Tech football"

def fbScorigami(platform):
    if platform == 'Windows':
        df = pd.read_csv(r'in_files/fbScorigamiGames.csv')
        fullPath = r'out_files/fbScorigami.png'
        basicPath = r'out_files/fbScorigamiBasic.png'
    elif platform == 'AWS':
        df = pd.read_csv('csv/fbScorigamiGames.csv')
        fullPath = 'out/fbScorigami.png'
        basicPath = 'out/fbScorigamiBasic.png' 
    
    df['Date'] = pd.to_datetime(df['Date'])
    df['Date'] = df['Date'].dt.strftime('%B %d, %Y')

    
    configuration = cfbd.Configuration( access_token = os.environ["cfbdAuth"] )
    api_instance = cfbd.GamesApi(cfbd.ApiClient(configuration))
    api_response = api_instance.get_games(2025, team='Louisiana Tech')
    
    dates = []
    techs = []
    tech_scores = []
    oppos = []
    oppo_scores = []
    for game in api_response:
        h_temp = game.home_points
        a_temp = game.away_points

        if h_temp or a_temp:
            awayTeam = game.away_team
            awayScore = game.away_points
            homeTeam = game.home_team
            homeScore = game.home_points
            if awayTeam == 'Louisiana Tech':
                techScore = awayScore
                oppoScore = homeScore
                oppo = homeTeam
            else:
                techScore = homeScore
                oppoScore = awayScore
                oppo = awayTeam
            
            dates.append(game.start_date)
            techs.append('Louisiana Tech')
            tech_scores.append(techScore)
            oppos.append(oppo)
            oppo_scores.append(oppoScore)
            print(awayTeam, awayScore, homeTeam, homeScore)
    
    
    df2 = pd.DataFrame({"Date":dates, "Tech":techs, "Tech Score": tech_scores, "Opponent":oppos, "Opponent Score":oppo_scores})
    df2['Date'] = df2['Date'].dt.tz_convert('US/Central')
    df2['Date'] = df2['Date'].dt.strftime('%B %d, %Y')
    df = pd.concat([df, df2])


        
    df.to_csv('out/fbScorigamiDataAlt.csv', index=False)
    df_s = generateScorigamiTable(df)
    df_s.to_csv('out/fbScorigamiData.csv', index=False)

    jsonString = "const json = '"
    jsonString += '{"results": '
    jsonString += df_s.to_json(index=False, orient="records")
    dateString = datetime.today().strftime('%B %d, %Y')
    jsonString += ',"updated": "' + dateString + '"}' + "';\nexport default json;\n"
    print(jsonString)
    print(jsonString,  file=open('html/fbScorigami/json.js', 'w'))

    import boto3
    s3 = boto3.resource("s3")
    s3.meta.client.upload_file('html/fbScorigami/json.js', 'amazon-cloudfront-secure-static-site--s3bucketroot-zadkhrqvgyxq', 'json.js',
    ExtraArgs={
        'ContentType': 'application/javascript',})

    #df_s.to_json('out/fbScorigamiData.json', index=False, orient="records")

    #df = df[:-1]      
    #checkIfScorigami(df, techScore, oppoScore)  

    #try:generateScorigamiChart(df_s, df_new, 1, winScore, loseScore, fullPath, basicPath)
    #except:generateScorigamiChart(df_s, df_new, 1, 101, 100, fullPath, basicPath)
    
    #print(message)
    #createTweet(message,[fullPath])

    #if platform == 'AWS':
    #    import boto3
    #    s3 = boto3.resource("s3")
    #    s3.meta.client.upload_file(fullPath, 'gtpdd-public-files', 'fbScorigami.png')
    
fbScorigami('AWS')